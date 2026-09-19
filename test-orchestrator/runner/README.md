# Controlled client runner

The Linux environment the acceptance items in W20/W30/W40 have been waiting for:
a real Minecraft 1.21.4 client, in a virtual display, on the platform the launch
plan targets. Nothing here is a product artifact — the image ships in neither the
wheel nor the Bridge jar, and the runner never reads the test oracle.

```text
bash test-orchestrator/runner/run.sh doctor
bash test-orchestrator/runner/run.sh init --kin-id kin-01
bash test-orchestrator/runner/run.sh session start --profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json
bash test-orchestrator/runner/run.sh --shell 'glxinfo -B'   # or any other command
```

`doctor` passes every check inside the image, which is the point of it: python
3.12.3, Java 21, protobuf 6.33.6 and SQLite 3.53.4. The same command fails on a
stock Ubuntu container on the SQLite check alone.

The repository is mounted read-only at `/src` and the CLI runs from the source
tree rather than from an installed wheel, because `find_workspace_root` needs to
see `bridge/` and `proto/` together and a wheel does not carry them. The data
root is the `minekin-runner-data` volume, so a session's overlay, ledger and
artifact store outlive the container.

## Filling the store before a session can start

`session start` refuses when an artifact it needs is not in the store, and the
store is empty in a fresh volume. `tools/fetch_bundle.py` is what fills it:
about 3,970 artifacts and 386 MB for p0-core, plus the fetched fixed mods, which
are loaded from the game directory rather than the classpath and so are not in
the plan's artifact list. Read `--dry-run` first.

Measured here, over the real bundle: a sequential pass took about 2.9 seconds
per artifact — nearly three hours — at roughly 35 KB/s, meaning it was waiting
on round trips rather than on the link. With the default bound of eight in
flight the same pass moves about 4.1 artifacts per second and finishes in around
a quarter of an hour. `--jobs` changes the bound; nothing else about the pass
changes with it, since every artifact is still verified by the store before it
is published and a part-filled store still resumes.

## Why this base image and not a distribution one

The frozen WAL safety gate requires SQLite 3.51.3 or newer, or one of the
backports 3.50.7 / 3.44.6. Measured on the obvious candidates:

| Base image | SQLite its Python uses |
| --- | --- |
| `ubuntu:24.04` | 3.45.1 |
| `debian:trixie` | 3.46.1 |
| `alpine` | 3.53.4 |

So the common distributions fail the gate out of the box and only the rolling
one passes — and Alpine is musl while Minecraft's LWJGL natives are built for
glibc, which is the wrong side of the same trade. This image therefore takes the
glibc base and supplies the newer SQLite itself: the amalgamation tarball is
fetched during the build and checked against the SHA3-256 that sqlite.org
publishes for it, before any object file is produced from it.

The library lands in `/opt/sqlite` and is deliberately **not** on the system
loader path. `run.sh` sets `LD_LIBRARY_PATH` for the command it runs, so which
SQLite a session is using is visible in the command rather than implied by the
image.

`LIBGL_ALWAYS_SOFTWARE=1` with Mesa's `llvmpipe` is what makes rendering possible
without a GPU. Measured in this image under Xvfb:

```text
bash test-orchestrator/runner/run.sh --shell 'xvfb-run -a --server-args="-screen 0 1280x720x24" glxinfo -B'
    Device: llvmpipe (LLVM 20.1.2, 256 bits)
    Version: 25.2.8
    Max core profile version: 4.5
```

Minecraft 1.21.4 requires OpenGL 3.2 core, so the client has a renderer to talk
to. Whether it reaches a *playable frame rate* under software rasterisation is
still open, and the prototype contract asks for tick and frame stability numbers
rather than a promise.

## What it does

Measured on this image, `session start` brings up a real 1.21.4 client under
Xvfb and the Bridge handshake is accepted:

```text
bash test-orchestrator/runner/run.sh --shell   'xvfb-run -a --server-args="-screen 0 1280x720x24" /opt/minekin/bin/python -m minekin_core      session start --profile /src/tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json'
```

The client reaches its main menu and builds its texture atlases; the ledger for
that run holds `SessionProcessStarted` followed by `BridgeHelloAccepted`. The
session then stays supervised, because nothing yet tells it to connect to a
world, so the command runs until the client exits or is stopped.

Before the client starts, the assets it reads are materialised out of the store
into `bundle/assets`: measured here, 4,040 files and 412 MB, read-only, once per
run rather than once per generation. That step is what stops the client logging
`Can't open the resource index file` — the store's layout is content-addressed
and the client's is not, so nothing but that step turns one into the other.

Two errors remain in the client's log and neither is a defect to fix here: the
narrator cannot load, and `AudioSystem` cannot open an OpenAL device, so the
client turns sounds off. A container has no sound device.

## What it does not do yet

It starts no server, and the client is not driven: the vanilla 1.21.4 dedicated
server, the isolated account and the per-run directories named alongside the
runner in the environment gate are separate pieces of the same work package.

The materialised assets view is also still missing — the plan names
`bundle/assets` and nothing publishes it, so the client logs `Can't open the
resource index file` for the asset index. It renders anyway, out of the assets
its own jar carries, which is why this is a missing contract step rather than a
broken client.
