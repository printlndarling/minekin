# A Linux runner for the managed Minecraft client.
#
# This is the environment the W20/W30/W40 acceptance items have been waiting
# for: a real client, in a virtual display, on the platform the launch plan
# targets. It is deliberately *not* a product artifact — nothing here ships in
# the wheel or the Bridge jar, and it never reads the test oracle.
#
# Why a base image plus a vendored SQLite rather than a rolling distribution:
# the frozen WAL safety gate wants SQLite >= 3.51.3 (or a backported fix), and
# the SQLite that comes with each candidate base image is 3.45.1 on Ubuntu
# 24.04, 3.46.1 on Debian trixie and 3.53.4 on Alpine. Only Alpine satisfies it
# out of the box, and Alpine is musl while Minecraft's LWJGL natives are built
# for glibc — so the two requirements point at different images. Taking the
# glibc image and supplying the newer SQLite keeps both, and adds one build step
# that is pinned by the digest upstream publishes for the tarball.
#
# The library is installed under /opt and is *not* put on the system loader
# path. The runner script sets LD_LIBRARY_PATH when it starts the CLI, so which
# SQLite is in use is visible in the command that runs rather than implied by
# the image.

FROM eclipse-temurin:21-jdk-noble

# The amalgamation tarball for SQLite 3.53.4, with the SHA3-256 published on
# https://www.sqlite.org/download.html. Pinned here rather than fetched by
# "latest" for the same reason every other artifact in this repository is.
ARG SQLITE_ARCHIVE=sqlite-autoconf-3530400.tar.gz
ARG SQLITE_DIRECTORY=sqlite-autoconf-3530400
ARG SQLITE_SHA3=454e45f61c6bd75b7420e7190732dea03ce6639c63ada47bbc592f67fc340338
ARG SQLITE_YEAR=2026

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      libgl1-mesa-dri \
      libglx-mesa0 \
      libx11-6 \
      libxcursor1 \
      libxi6 \
      libxinerama1 \
      libxrandr2 \
      libxxf86vm1 \
      mesa-utils \
      openssl \
      python3-venv \
      xvfb \
 && rm -rf /var/lib/apt/lists/*

# Build SQLite and verify the tarball against the digest upstream publishes,
# before a single object file is produced from it.
RUN curl -fsSL -o /tmp/sqlite.tar.gz \
      "https://www.sqlite.org/${SQLITE_YEAR}/${SQLITE_ARCHIVE}" \
 && test "$(openssl dgst -sha3-256 /tmp/sqlite.tar.gz | awk '{print $NF}')" = "${SQLITE_SHA3}" \
 && tar -C /tmp -xzf /tmp/sqlite.tar.gz \
 && cd "/tmp/${SQLITE_DIRECTORY}" \
 && ./configure --prefix=/opt/sqlite --disable-static --enable-fts5 >/dev/null \
 && make -j"$(nproc)" >/dev/null \
 && make install >/dev/null \
 && rm -rf "/tmp/${SQLITE_DIRECTORY}" /tmp/sqlite.tar.gz

# The virtual display the client renders into. 1280x720x24 is enough for the
# client window and keeps the software rasteriser's fill rate honest.
ENV DISPLAY=:99 \
    LIBGL_ALWAYS_SOFTWARE=1

# The one runtime dependency the CLI needs, pinned to the version `uv.lock`
# resolves so the module that parses generated protobuf is the same here as in
# CI. The package itself is not installed: the runner runs the CLI from the
# source tree, because `find_workspace_root` needs to see `bridge/` and `proto/`
# and an installed wheel does not carry them.
RUN python3 -m venv /opt/minekin \
 && /opt/minekin/bin/pip install --no-cache-dir --disable-pip-version-check \
      "protobuf==6.33.6" >/dev/null
ENV PATH=/opt/minekin/bin:$PATH

WORKDIR /work
