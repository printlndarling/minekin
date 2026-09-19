# Controlled runner

The Linux environment the acceptance items in W20/W30/W40 have been waiting for:
a real Minecraft 1.21.4 client, in a virtual display, on the platform the launch
plan targets — plus the isolated vanilla server it is supposed to connect to.
Nothing here is a product artifact — the image ships in neither the wheel nor the
Bridge jar, and the runner never reads the test oracle.

```text
bash test-orchestrator/runner/run.sh doctor
bash test-orchestrator/runner/run.sh init --kin-id kin-01
bash test-orchestrator/runner/run.sh session start --profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json
MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/run.sh server --accept-eula --allow-player Kin
MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/run.sh domain \
    session start --profile <bundle> --server-profile <server profile>
bash test-orchestrator/runner/run.sh --shell 'glxinfo -B'   # or any other command
```

## The whole domain in one container

The `domain` mode is the three file modes above with both halves running at once:
it starts the isolated server on a fresh run directory, waits for the server to
say it is ready, runs the session against it, and stops the server.

Both halves have to be in *this* container. The frozen Server Profile schema
admits only `127.0.0.1` and `::1`, and loopback is per container — so a server
started by `run.sh server` is in a different network namespace from a client
started by `run.sh session`, and the two can never see each other however
correct the address is. The only shape compatible with that policy is two
processes in one container (`--network host` is not available on Docker Desktop
for Windows). `run.sh domain` is that shape; `domain.sh` is the part of it that
runs inside.

`timeout` goes *inside* `xvfb-run`, not outside. Signal it from the outside and
the signal lands on the X server, which takes the client's display away and ends
the client through `X connection to :99 broken` — a client death that has
nothing to do with the session, and one that quietly contaminates any conclusion
about how the run went.

```text
$ MINEKIN_SERVER_JAR=.tmp/vanilla/server.jar bash test-orchestrator/runner/run.sh domain \
      session start --profile /src/tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json \
                     --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server.json
domain: server run directory /data/server-runs/run-4
domain: server ready
domain: session exited 124
```

The session's exit code is 124 because a client that has joined sits in the world
and only the window ends it; the ledger is what says how the run went.

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

## The server half

```text
uv run python tools/verify_supply_chain.py --save-server <path> --max-bytes 60000000
MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/run.sh server \
    --accept-eula --allow-player Kin
```

The first command is where the server jar comes from, because nothing else was
that step: the supply-chain check already fetches those bytes to compare them
against the pin, so `--save-server` keeps the payload it has just verified at the
path the operator names. It fetches 59,531,345 bytes — the six smallest artifacts
on the plan, fabric-api, and the 54 MB server — and prints that number before it
starts. A file already at that path is replaced only if it is the same bytes.

The second runs `tools/run_controlled_server.py` inside the runner. The jar is
mounted read-only from a host path rather than copied, so which jar a run used is
answerable from the command that ran. Each run gets a fresh directory under the
data volume at `/data/server-runs/run-<n>`, and `n` skips everything already
there, so an earlier run's world, log and settings are never overwritten. A run
that is refused leaves nothing behind: the EULA check happens before the
directory is created.

**The EULA is the operator's to accept**, so this passes `--accept-eula` through
and never supplies it. Without it the tool exits 2 and writes nothing at all,
which is what the runner shows you if you try:

```text
$ MINEKIN_SERVER_JAR=.tmp/vanilla/server.jar bash test-orchestrator/runner/run.sh server
server run directory: /data/server-runs/run-1
the Minecraft EULA must be accepted by the operator: pass --accept-eula
```

### Measured

```text
$ MINEKIN_SERVER_JAR=.tmp/vanilla/server.jar bash test-orchestrator/runner/run.sh server \
      --accept-eula --allow-player Kin
server run directory: /data/server-runs/run-1
started 9; waiting for 'Done (' in /data/server-runs/run-1/server.log
Controlled server: OK (ready, then stopped; /data/server-runs/run-1/server.log holds the run)
```

The isolation held in the started server, not just in the file the tool wrote —
the settings are quoted back from `server.properties` after vanilla rewrote it on
first run: `online-mode=false`, `white-list=true` with `enforce-whitelist=true`,
`gamemode=survival`, `force-gamemode=true`, `spawn-protection=0`, and
`enable-rcon`/`enable-query`/`enable-command-block`/`broadcast-console-to-ops`
all false. `whitelist.json` names one account, the Kin's, under the offline UUID
`8f40376b-c23f-3ef1-b553-5564eea75639`, and `ops.json` is empty. The log says
where it bound and that it saw the trade it was making:

```text
[Server thread/INFO]: Starting Minecraft server on 127.0.0.1:25565
[Server thread/WARN]: **** SERVER IS RUNNING IN OFFLINE/INSECURE MODE!
[Server thread/INFO]: Done (0.512s)! For help, type "help"
[Server thread/INFO]: Stopping the server
[Server thread/INFO]: ThreadedAnvilChunkStorage: All dimensions are saved
```

Per-run isolation comes for free: a modern server jar is a bundler that unpacks
the server and 44 MB of libraries into its working directory, so each run gets
its own copy rather than sharing one. That is also the cost — `run-1` is 64 MB on
disk (44 MB libraries, 18 MB server, 3.5 MB world) and nothing prunes it. Runs
are evidence, so they are appended to and never rewritten; when they should be
collected is the same open question the session markers are.

One `ERROR` is in the log and is not a defect to fix here:
`No key layers in MapLike[{}]` is vanilla's flat generator saying that
`level-type=minecraft:flat` arrived without a `layers` key. It falls back to the
default layer set and the world generates; the alternative would be inventing a
generator preset the profile does not name.

## What it does not do yet

The client reaches the server and the login fails, about three seconds later,
without a word from either side. The server records nothing at all — its
`usercache.json` is empty, and vanilla only writes that on a successful login —
and the client records nothing either, because vanilla draws a disconnect reason
on the `DisconnectedScreen` rather than logging it. TCP is not the problem: a
connection to `127.0.0.1:25565` from inside the same container reaches
ESTABLISHED, and the server process is healthy, parked in its ordinary 50 ms tick
wait.

What is *not* the problem has been measured rather than assumed: disabling
vanilla's `pause-when-empty-seconds` does not change it (the domain no longer
pauses, which is right for its own reasons, and the login still fails).

The next move is to make the failure visible — the bridge may keep redacted
diagnostics outside the product event payload, so a local log line at the login
disconnect would say what the server said — and then to diagnose it.
