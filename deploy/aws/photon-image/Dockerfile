# syntax=docker/dockerfile:1
# DRAFT Photon runtime image: pinned Temurin 21 JRE plus the pinned Photon 1.3.0 JAR. It holds
# no index; the sealed index arrives through the data image. Not built or pushed yet.
#
# Build (the JAR is a named context, so it never enters the repository):
#   docker build --build-context photon_jar=<dir containing photon-1.3.0.jar> \
#     -t ot-t5-photon:local deploy/aws/photon-image
#
# Both pins equal opentransit.core.artifacts.JAVA_21_IMAGE_DIGEST / PHOTON_130_JAR_SHA256,
# which generation verification already requires; a unit test keeps them in step.
FROM eclipse-temurin:21.0.12.1_1-jre@sha256:628467024d428251da635661936d6180717b1ac1119d41c76d28a03b7293c43c

ARG PHOTON_JAR_SHA256=a89707c0045e4807b2a1180e132e68e108d998709f48b6c94b98a6e281f571a5
COPY --from=photon_jar --chmod=0444 photon-1.3.0.jar /opt/photon/photon-1.3.0.jar
RUN echo "${PHOTON_JAR_SHA256}  /opt/photon/photon-1.3.0.jar" | sha256sum -c -

USER 10001:10001
# The task definition supplies the same command; heap and ports live there so the memory budget
# is reviewed in one place.
CMD ["java", "-Xms256m", "-Xmx512m", "-jar", "/opt/photon/photon-1.3.0.jar", \
     "-data-dir", "/photon_data", "serve", "-listen-ip", "127.0.0.1", "-listen-port", "2322"]
