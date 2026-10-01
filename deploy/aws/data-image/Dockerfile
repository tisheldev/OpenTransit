# syntax=docker/dockerfile:1
# DRAFT data-initialization image: one complete generation, verified and copied by the task's
# `init` container into task-local volumes. Not built or pushed by any automation yet.
#
# Build (named context produced by deploy/aws/tools/stage_bundle.py; see deploy/aws/README.md):
#   docker build --build-context bundle=<staged dir> -t ot-t5-data:local deploy/aws/data-image
#
# Same pinned Python base as services/api/Dockerfile, so the base layers are pulled once per
# task. One COPY per artifact class keeps the large layers independent for parallel pull.
FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --chmod=0555 init_generation.py /usr/local/bin/init-generation

COPY --from=bundle payload/reference/ /payload/reference/
COPY --from=bundle payload/graph/ /payload/graph/
COPY --from=bundle payload/photon/ /payload/photon/
COPY --from=bundle payload/small/ /payload/small/
COPY --from=bundle payload-manifest.json /payload/payload-manifest.json

# Runs as root only to chown the task-local volumes; the task definition drops every other
# default capability, mounts the root filesystem read-only and publishes no port.
USER 0
ENTRYPOINT ["python", "/usr/local/bin/init-generation"]
