"""Loopback TCP forwarder with a file-controlled request delay and a request log.

Used only by the activation Compose harness to hold a real request in flight on the old
engine while the generation is switched, and to expose each generation's loopback-only
Photon to the API's network namespace (``name:listen:host:target`` routes). The log records
method, path (never the query or body), connection-relative request ids and wall-clock
timestamps; it holds no coordinates.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path


def delay_for(control: Path, name: str) -> float:
    try:
        return max(0.0, float((control / f"delay-{name}").read_text().strip()))
    except OSError, ValueError:
        return 0.0


async def serve(
    name: str, listen: int, host: str, target: int, control: Path, log, listen_host: str
) -> None:
    counter = iter(range(1, 1 << 62))

    def record(**fields):
        log.write(json.dumps({"route": name, **fields}) + "\n")
        log.flush()

    async def handle(client_reader, client_writer):
        try:
            backend_reader, backend_writer = await asyncio.open_connection(host, target)
        except OSError:
            record(ev="backend_unavailable", t=time.time())
            client_writer.close()
            return
        state = {"id": None, "last": None}

        def finish():
            if state["id"] is not None and state["last"] is not None:
                record(ev="resp_end", id=state["id"], t=state["last"])
            state["id"] = state["last"] = None

        async def upstream():
            while data := await client_reader.read(65536):
                finish()
                line = data.split(b"\r\n", 1)[0].decode("latin-1", "replace").split(" ")
                path = line[1].split("?", 1)[0] if len(line) > 1 else "?"
                state["id"] = f"{name}-{next(counter)}"
                delay = delay_for(control, name)
                record(
                    ev="req", id=state["id"], method=line[0], path=path, t=time.time(), delay=delay
                )
                if delay:
                    await asyncio.sleep(delay)
                backend_writer.write(data)
                await backend_writer.drain()
            backend_writer.close()

        async def downstream():
            while data := await backend_reader.read(65536):
                state["last"] = time.time()
                client_writer.write(data)
                await client_writer.drain()
            finish()
            client_writer.close()

        await asyncio.gather(upstream(), downstream(), return_exceptions=True)
        finish()

    server = await asyncio.start_server(handle, listen_host, listen)
    async with server:
        await server.serve_forever()


async def main(argv) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", action="append", required=True, help="name:listen:[host:]target")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    routes = []
    for item in args.route:
        parts = item.split(":")
        if len(parts) == 3:
            parts.insert(2, "127.0.0.1")
        name, listen, host, target = parts
        routes.append((name, int(listen), host, int(target)))
    with args.log.open("a", encoding="utf-8") as log:
        await asyncio.gather(
            *(
                serve(name, listen, host, target, args.control, log, args.listen_host)
                for name, listen, host, target in routes
            )
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
