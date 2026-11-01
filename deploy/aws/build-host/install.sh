#!/bin/bash
# OpenTransit H-1 build host: install the pinned tools and the systemd units (idempotent).
# Run by user-data.sh at launch and by run-refresh.sh after the pinned repository ref changes.
# Every download is checked against the SHA-256 below; a mismatch stops the install.
set -euxo pipefail

UV_VERSION=0.11.26          # same uv as services/api/Dockerfile
UV_SHA256=6426a73c3837e6e2483ee344cbc00f36394d179afcba6183cb77437e67db4af0
BUILDX_VERSION=v0.37.2      # docker build --build-context needs BuildKit through buildx
BUILDX_SHA256=982ca20490b45ed1ec8d99795974d3d874a358f75938c9c237305010e6b7e548
PHOTON_SHA256=a89707c0045e4807b2a1180e132e68e108d998709f48b6c94b98a6e281f571a5  # = PHOTON_130_JAR_SHA256
OSMIUM_WHEEL=osmium-4.3.1-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
OSMIUM_SHA256=ad0caea456c56b058305967f3bb3037517e0e1357aea5106cefa5b2be660d759
PYTHON_VERSION=3.14.6       # services/api/.python-version

here=$(cd "$(dirname "$0")" && pwd)
opt=/opt/opentransit
install -d "$opt/bin" "$opt/photon" "$opt/osm-reader" /srv/ot/src /srv/ot/generations \
  /srv/ot/logs /srv/ot/releases /usr/local/lib/docker/cli-plugins
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

fetch() {  # url sha256 destination
  curl -fsSL --retry 3 -o "$tmp/download" "$1"
  echo "$2  $tmp/download" | sha256sum -c -
  install -m "${4:-0644}" "$tmp/download" "$3"
}

if [ "$("$opt/bin/uv" --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
  curl -fsSL --retry 3 -o "$tmp/uv.tgz" \
    "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz"
  echo "$UV_SHA256  $tmp/uv.tgz" | sha256sum -c -
  tar -xzf "$tmp/uv.tgz" -C "$tmp"
  install -m 0755 "$tmp/uv-x86_64-unknown-linux-gnu/uv" "$tmp/uv-x86_64-unknown-linux-gnu/uvx" "$opt/bin/"
fi
[ -x /usr/local/lib/docker/cli-plugins/docker-buildx ] && \
  echo "$BUILDX_SHA256  /usr/local/lib/docker/cli-plugins/docker-buildx" | sha256sum -c - || \
  fetch "https://github.com/docker/buildx/releases/download/$BUILDX_VERSION/buildx-$BUILDX_VERSION.linux-amd64" \
    "$BUILDX_SHA256" /usr/local/lib/docker/cli-plugins/docker-buildx 0755
[ -f "$opt/photon/photon-1.3.0.jar" ] && \
  echo "$PHOTON_SHA256  $opt/photon/photon-1.3.0.jar" | sha256sum -c - || \
  fetch https://github.com/komoot/photon/releases/download/1.3.0/photon-1.3.0.jar \
    "$PHOTON_SHA256" "$opt/photon/photon-1.3.0.jar"

export UV_CACHE_DIR=/var/cache/uv UV_PYTHON_INSTALL_DIR=$opt/python
"$opt/bin/uv" python install "$PYTHON_VERSION"
if [ ! -d "$opt/osm-reader/osmium" ]; then
  echo "osmium==4.3.1 --hash=sha256:$OSMIUM_SHA256" > "$tmp/osm-reader.txt"
  "$opt/bin/uv" pip install --python "$PYTHON_VERSION" --target "$opt/osm-reader" \
    --no-deps --require-hashes --only-binary :all: -r "$tmp/osm-reader.txt"
fi
"$opt/bin/uv" run --no-project --python "$PYTHON_VERSION" python -I -c \
  "import sys; sys.path.insert(0, '$opt/osm-reader'); import osmium; print('osmium', osmium.__version__)"

install -m 0755 "$here/run-refresh.sh" /usr/local/libexec/opentransit-run-refresh
install -m 0644 "$here/opentransit-refresh.service" "$here/opentransit-backstop.service" \
  "$here/opentransit-backstop.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable opentransit-refresh.service opentransit-backstop.timer
git -C "$opt/repo" rev-parse HEAD > "$opt/installed-ref"
echo "install complete at $(cat "$opt/installed-ref")"
