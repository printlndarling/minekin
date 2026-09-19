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
MINEKIN_SERVER_JAR=<path> MINEKIN_DOMAIN_SUMMON=minecraft:pig \
    bash test-orchestrator/runner/run.sh domain session start --profile <bundle> --server-profile <profile>
MINEKIN_SERVER_JAR=<path> MINEKIN_DOMAIN_PROBE=Kin \
    bash test-orchestrator/runner/run.sh domain session start --profile <bundle> --server-profile <profile> \
        --hold-forward-seconds 8
MINEKIN_SERVER_JAR=<path> MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_SILENCE=1 \
    bash test-orchestrator/runner/run.sh domain session start --profile <bundle> --server-profile <profile> \
        --hold-forward-seconds 60
MINEKIN_SERVER_JAR=<path> MINEKIN_DOMAIN_NO_SERVER=1 \
    bash test-orchestrator/runner/run.sh domain session start --profile <bundle> --server-profile <profile>
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

The session is ended by stopping it, not by a clock. A `timeout` around
`session start` kills a CLI that then never prints the **run document**, and the
document is the only place Core's own verdicts live — how many entities it
admitted, how many snapshots it refused. A windowed run could show what the
Bridge sent and never what Core made of it. So `domain.sh` waits for this run's
own ledger to reach `PlayableEstablished` and then calls `session stop`, which
ends the client it recorded and lets the CLI return normally.

That wait is for the join, not for a duration: a clock long enough for this
machine is a clock that is wrong on a slower one. The obvious condition does not
work — `session status`'s `last_event_type` is the *Kin's* ledger, and every
earlier domain run already ended at `PlayableEstablished`, so it is true before
the session even starts. What makes it this run's playable is the ledger having
*grown*, which is what the script now asks.

```text
$ MINEKIN_SERVER_JAR=.tmp/vanilla/server.jar bash test-orchestrator/runner/run.sh domain \
      session start --profile /src/tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json \
                     --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server.json
domain: server run directory /data/server-runs/run-26
domain: server ready
domain: the session is playable
domain: stopping the session
domain: session stop said {"command": "session stop", "kin_id": "kin-01", "terminated": [201], …}
{"argv_digest": …"run": {"connection_state": "PLAYABLE", "entities_admitted": 2, "entities_rejected": 0,
                         "snapshots_admitted": 1, "snapshot_rejections": [], "session_state": "STOPPED", …}}
domain: session exited 14
```

The exit code is the session's own outcome, and `14` is `BRIDGE_LOST`: the
harness stopped the client, so the Bridge went with it. A run that did everything
asked of it therefore ends non-zero, which is the harness's doing and not the
run's — the document is what says how the run went.

Two signals were involved in getting there and both were wrong in the same way —
looking like they worked:

* `kill -INT` on a background job of a non-interactive shell is a **no-op**. That
  job inherits SIGINT set to `SIG_IGN`; measured in this image, `SIGINT SIG_IGN`
  and `SIGTERM SIG_DFL`. So the "stop the server cleanly" trap sent nothing and
  the server ran until the container was killed — eight minutes of a run that had
  already finished, hidden by an outer `timeout`. `run_controlled_server.py` now
  installs handlers for SIGINT *and* SIGTERM (both take the clean-stop path that
  saves the world), the script sends SIGTERM, and the whole run takes 44 seconds
  instead of 560+.
* `session stop`'s answer is kept in the log rather than discarded. "Stopped" and
  "failed to stop" look identical from the outside, and only one of them means the
  run's ending had anything to do with the run.

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

## What it does now

A managed client joins the isolated domain. Three independent pieces of evidence
agree:

```text
client   bridge asked vanilla to connect to 127.0.0.1:25565 for generation 1
client   Connecting to 127.0.0.1, 25565
client   bridge reporting CONNECTION_PHASE_LOGIN_NEGOTIATING for generation 1
client   bridge reporting CONNECTION_PHASE_PLAY_INIT for generation 1
client   bridge reporting CONNECTION_PHASE_JOIN_SEEN for generation 1

ledger   SessionProcessStarted  LAUNCHER
ledger   BridgeHelloAccepted    CORE
ledger   JoinObserved           BRIDGE   {"phase":"JOIN_SEEN"}

server   Kin[/127.0.0.1:42662] logged in with entity id 1 at (-9.5, -60.0, 2.5)
server   Kin joined the game
```

The server line is read by hand after the run, which is the only way the contract
allows server truth to be used.

The session then goes all the way to playable, because the Bridge sends the first
authoritative snapshot and **Core** admits it:

```text
ledger   JoinObserved         BRIDGE  {"phase":"JOIN_SEEN"}
ledger   PlayableEstablished  CORE    {"phase":"PLAYABLE"}
```

The two entries have different sources on purpose. The join is the Bridge
reporting what its client did; being playable is Core's own conclusion from a
snapshot it validated, and §6 does not allow a trust class to be self-declared —
so naming the Bridge as the source of Core's verdict would put the wrong name on
the strongest fact in the session.

The snapshot carries the client's own state and the entities this client can
confirm it can see. `visible_entities` holds every entity within 64 blocks, each
with vanilla's own `canSee` verdict, its UUID as a stable token, and its offset
from the player — and a candidate the client could *not* see is sent rather than
dropped, because Core counts those rejections and a silent omission would be the
Bridge deciding policy it does not own.

The world has to contain something for that to mean anything, so `--summon` puts
one entity at the world spawn:

```text
$ MINEKIN_SERVER_JAR=.tmp/vanilla/server.jar MINEKIN_DOMAIN_SUMMON=minecraft:pig \
      bash test-orchestrator/runner/run.sh domain session start --profile … --server-profile …
server   [16:17:03] Summoned new Pig
client   bridge knows of 1 entity candidate(s) 1 tick(s) after joining
client   bridge collected 1 entity candidate(s) within 64.0 blocks, 1 confirmed visible
run      "entities_admitted": 2, "entities_rejected": 0
```

The count varies between runs because it is a real world: two entities near spawn
on one run, six on another. That is the point — these are numbers about a world,
not a constant the Bridge was told to produce.

**The join is not the moment to take it.** The first version collected the
snapshot from the join event and reported zero entities for a world that had a
summoned pig in it: `JOIN_SEEN` comes from the game-join packet, and the server's
entity-tracker packets arrive after it. The numbers were true about the client and
false about the world, which is the one thing a snapshot may not be. The
collection now waits on the client tick for vanilla's own "the player is in
control" signal — no screen up, which is the terrain-download screen having been
dismissed — bounded at 100 ticks so a screen that never clears cannot starve the
session.

Getting there was a one-line bug with a loud lesson. The client was sending
`next_state=3` — `TRANSFER`, not `LOGIN` — because vanilla decides that from
whether the cookie storage is null, and `new CookieStorage(Map.of())` is not
null. An empty cookie storage is not "no cookies"; it is *a transfer with no
cookies in it*, and a vanilla server refuses a transfer it did not start by
closing the socket without a word.

What found it was not another exclusion. It was standing a small capture server
on 25565 in this container and reading the bytes the client put on the wire —
no server jar, no bridge change, no re-recorded pin. `next_state=3` appears in
no log anywhere. When both ends are silent, read the bytes.

### The Kin walks, and the server is asked where it is

`--hold-forward-seconds` makes Core hold the forward key from the moment the
session is playable, under a `control.move.v1` lease, and let it lapse when the
lease's own deadline passes. The acceptance for input is the
server's own observation of the displacement, and a server does not log where
anyone walks — so the run asks it, with `data get entity <name> Pos` on the
console, and reads the answer out of the server's log.

```text
$ MINEKIN_SERVER_JAR=.tmp/vanilla/server.jar MINEKIN_DOMAIN_PROBE=Kin \
      bash test-orchestrator/runner/run.sh domain \
      session start --profile … --server-profile … --hold-forward-seconds 8
server   [18:02:59] Kin joined the game
server   [18:03:02] Kin has the following entity data: [-2.5d, -60.0d, 12.01d]
server   [18:03:07] Kin has the following entity data: [-2.5d, -60.0d, 33.60d]
server   [18:03:12] Kin has the following entity data: [-2.5d, -60.0d, 39.03d]
server   [18:03:17] Kin has the following entity data: [-2.5d, -60.0d, 39.03d]
client   bridge applied a5b9a84b…: holding [move.forward]        (18:03:01)
client   bridge released 1 input(s) after CORE_REQUEST (TIMEOUT)  (18:03:09)
ledger   InputLeaseGranted → InputReleased{reason: TIMEOUT}
```

21.6 blocks in five seconds is walking speed, and a teleport would be a jump
rather than a rate — which is what makes "no teleport" a measurement here
instead of a promise. The last two positions agreeing is the other half: the
Kin stopped **eight seconds after the grant** while the session stayed alive
for another ten, so what ended the walk was the lease and not the run. Those
two look identical in a log that simply stops, which is why the harness waits
for both.

`--hold-strafe`, `--hold-jump` and `--hold-sneak` add to what the hold holds, and
each is checked against a number vanilla publishes rather than against "something
happened":

| Held | The server saw |
| --- | --- |
| forward (`--hold-forward-seconds N`) | 4.32 blocks/s (walking is 4.317) |
| `--hold-sneak` | 1.30 blocks/s (4.317 × 0.3 = 1.295) |
| `--hold-jump` | a height range of 1.25 blocks (a jump is 1.2522) |
| `--hold-strafe 1` | X and Z changing equally — a 45° diagonal |

That is the one thing unit tests cannot decide: whether the binding the Bridge
presses for a name is what vanilla calls that name. A `KeyBinding` mapped to the
wrong field passes every test in the repository and walks the Kin sideways.

The run waits for **two positions that differ horizontally, and then for the
last two to agree**: a Kin standing still at spawn can be reported twice with
different `Y`, so counting any two positions would accept a fall at spawn as a
walk, and stopping at the first change would accept a session that ended as a
lease that lapsed. Each wait has its own budget, because a slow boot must not
spend the walk's allowance — the first version shared one deadline and read a
Kin that had walked 780 blocks as one that never moved.

That wait asks the ledger rather than `session status`, which shows only the
*last* event type: `InputLeaseGranted` lands milliseconds after
`PlayableEstablished`, so "the last event is playable" is true for a window too
short to poll. The question is instead whether a playable was recorded after
this run started.

The hold lasts as long as the lease says. `domain/lease_watchdog.py` holds the
granted lease and reports once when its deadline passes, the runtime watches a
caller-owned awaitable beside the client watcher, and Core withdraws the lease
and sends `ReleaseAllInputs(TIMEOUT)` — the same call the wind-down makes, which
is why the ledger record of it lives in that one path rather than in both.

### A Kin that turns

`--look-yaw-degrees` asks the client to turn, and the server is the only side that
can say whether it did: a turn is not a movement, so no position reading shows
one. The probe asks for `Rotation` alongside `Pos`, and a run that wants a reading
on both sides of the turn asks more often than the default.

```text
$ MINEKIN_SERVER_JAR=… MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_PROBE_SECONDS=1 \
      MINEKIN_DOMAIN_LOOK=90 bash test-orchestrator/runner/run.sh domain \
      session start --profile … --server-profile … --look-yaw-degrees 90
domain: the server saw the Kin turn by 90.000 degrees (asked for 90)
domain: the turn is the one that was asked for, and the Kin stayed put
server   [18:48:28] Kin has the following entity data: [5.5d, -60.0d, 6.5d]
server   [18:48:28] Kin has the following entity data: [0.0f, 0.0f]
server   [18:48:31] Kin has the following entity data: [5.5d, -60.0d, 6.5d]
server   [18:48:31] Kin has the following entity data: [90.0f, 0.0f]
client   [18:48:29] bridge turned the view by 90.0 yaw, 0.0 pitch degrees
ledger   InputLeaseGranted{capability: control.look.v1}
```

The same place and a different heading: the position readings agreeing is the
"no teleport" half, and the heading landing exactly on the requested 90 is what
makes this the client's own look path rather than a written angle. That number is
the check on the scale factor: `Entity.changeLookDirection` takes the cursor
delta the mouse would have handed it and multiplies by 0.15 degrees per unit —
read out of the compiled method, and confirmed here by the result.

The two kinds of reading are told apart by shape, not by wording: the server
answers both probes with the same words, and only a position has three
components.

### When Core stops answering

`MINEKIN_DOMAIN_SILENCE=1` takes Core out of the scheduler — SIGSTOP, not a kill,
because the session has to survive to be stopped afterwards — once the Kin is
walking and holding forward. The Bridge has to let go on its own: §12 puts that
guarantee in the process holding the keys, and it needs nobody's permission.

The first run of this did not verify the guarantee, it found a defect: **two
seconds of silence stopped the client** rather than releasing the keys. The two
responses to silence had the same tolerance — the input watchdog's three missed
heartbeats and the transport read's three missed heartbeats are both 1.5 s — so
stopping the client always won the race and the release never ran. Releasing is
now the first response (three intervals) and giving up on the channel the last
(60 intervals, 30 s by default), with a test pinning the order.

```text
$ MINEKIN_SERVER_JAR=… MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_SILENCE=1 \
      bash test-orchestrator/runner/run.sh domain \
      session start --profile … --server-profile … --hold-forward-seconds 60
domain: the session is playable
domain: Core has gone quiet; the Bridge should let go
domain: the server saw the Kin walk and then stop
domain: Core is running again
server   [18:31:11] Kin has the following entity data: [-0.82d, -60.0d, 19.99d]
server   [18:31:16] Kin has the following entity data: [-0.82d, -60.0d, 19.99d]
client   [18:31:02] bridge applied 0ba1ec4b…: holding [move.forward]
client   [18:31:08] bridge released move.forward
client   [18:31:08] bridge released input after TIMEOUT
```

No death, no disconnect, no `failing closed`: the Kin stopped because the keys
came up and the session carried on. The two sides are independent — the server
watches the displacement and the client reports its own hand — and Core says
nothing throughout, which is the point: this run's ledger has no
`InputReleased` at all, that being Core's event and Core being absent.

### When Core is killed rather than paused

`MINEKIN_DOMAIN_KILL_CORE=1` uses SIGKILL where `MINEKIN_DOMAIN_SILENCE` uses
SIGSTOP, and the difference is not just severity: a killed Core closes its
sockets, and a closed socket is not a peer that went quiet.

```text
$ MINEKIN_SERVER_JAR=… MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_KILL_CORE=1 \
      bash test-orchestrator/runner/run.sh domain session start --profile … --server-profile … \
      --hold-forward-seconds 60
domain: the session is playable
domain: Core has been killed; the Bridge should let go
domain: the Kin left the game after Core died
client   [19:00:55] bridge applied ce6f8f83…: holding [move.forward]
client   [19:00:58] bridge is failing closed (IPC_LOST); the client will be stopped by its next tick
client   [19:00:58] bridge released move.forward
client   [19:00:58] bridge released 1 input(s) after IPC_LOST
ledger   InputLeaseGranted                                   (and nothing after it)
```

The ledger stopping at the grant is the point of the run: `InputReleased` is
Core's event, and Core was not there to write it, so the absent line is itself
the evidence that something else lifted the keys.

The two switches also draw a line the contract draws but nothing had measured:
**silence** releases the keys and the client keeps running, because the peer may
come back; **a closed socket** releases them and stops the client too, because it
will not. A run therefore accepts either ending as proof that the release took
effect — the Kin stopped walking, or the Kin is gone, and a process that has
exited cannot be holding a key.

### After a crash, a restart

The data volume outlives the container, so the crash and the restart that follows
it are two runs of the same command — the second one checking what the first left
behind:

```text
$ MINEKIN_SERVER_JAR=… MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_KILL_CORE=1 \
      bash test-orchestrator/runner/run.sh domain session start --profile … --server-profile … \
      --hold-forward-seconds 60                       # the Kin is walking when Core dies
$ MINEKIN_SERVER_JAR=… MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_STILL=1 \
      bash test-orchestrator/runner/run.sh domain session start --profile … --server-profile …
domain: the session is playable
domain: the Kin moved 0.000 blocks across 12 readings and did not walk
run      "actions_applied": 0, "snapshots_admitted": 1, "recovery": {"invalidated": [], "waiting": []}
```

The second run admits a **new** snapshot, so the world state is re-verified rather
than reused, and it asks for nothing — yet the Kin, which the first run left
walking, does not move a block. Nothing the dead run asked for survives it.

Stillness is measured by distance and not by equality, because the world is not
empty: a summoned pig that wanders into the Kin shoves it, and a Kin shoved 1.5
blocks in three seconds has not walked anywhere. Walking is 4.3 blocks per
second, so a two-block threshold separates a shove from a step by an order of
magnitude rather than by tuning.

What this pair does **not** cover is the window where a crash leaves a pending
outbox item — between recording the intent and settling the effect, which is the
second a client spends starting. The harness cannot land there from where it
waits, so that branch is covered against a real ledger by unit tests instead, and
that is the honest boundary rather than a claim.

### When nothing is listening

`MINEKIN_DOMAIN_NO_SERVER=1` stops the server again as soon as it has proved
it can start, so the address in the frozen profile has nothing behind it. It
is how a refused connection is produced without a second fixture: the target
is wrong at the moment the client dials it, and everything else about the run
is unchanged.

This is the one failure the Bridge still says nothing about. A refusal, an
unknown host and a connect timeout all happen before a login handler exists,
so every Fabric event the Bridge listens to stays silent and the ledger ends
at the phase before negotiation. The obvious hook — the screen vanilla shows
for it — was tried twice and does not work; `docs/development-todo.md` records
both attempts and what the second one measured.

### When the server ends the session

`MINEKIN_DOMAIN_KICK=Kin` has the server kick the Kin a few seconds after it
joins, while it is holding forward. A kick ends the *session*; a death leaves the
session running with a screen owning the keyboard. The contract names them as
separate release triggers, so a run has to be able to produce both.

```text
$ MINEKIN_SERVER_JAR=… MINEKIN_DOMAIN_PROBE=Kin MINEKIN_DOMAIN_KICK=Kin bash test-orchestrator/runner/run.sh domain \
      session start --profile … --server-profile … --hold-forward-seconds 60
domain: the server ended the session while the client kept running
server   [19:11:48] Kicked Kin: Kicked by an operator
server   [19:11:48] Kin lost connection: Kicked by an operator
client   [19:11:48] bridge released move.forward
client   [19:11:48] bridge released 1 input(s) after LEFT_PLAYABLE (PLAY_ENDED)
ledger   SessionInterrupted{phase: FAILED, reason: ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT}
```

The client keeps running after the kick — the session ended, not the process — so
this run still ends with a document, unlike the killed-Core one.

Getting there found a real defect of the kind this file keeps producing: the play
disconnect arrives on the **network** thread, and the key sink refuses to touch
bindings anywhere but the client thread. Releasing inline therefore threw
`Minecraft input may only change on the client thread`, which the Bridge's own
error handling turned into a stopped client — on the one path that exists to let
go of the keys. The release is now dispatched with `client.execute(...)`, and the
sink's assertion is what caught it rather than a run that merely looked wrong.

### When the keyboard stops being the world's

A held key has to come up when the client stops taking input, and the run can
make that happen in exactly one way: `MINEKIN_DOMAIN_KILL=Kin` has the server
kill the Kin a few seconds after it joins, while it is holding forward.

```text
server   [18:17:37] Kin joined the game
server   [18:17:43] Kin was killed
client   [18:17:38] bridge applied dc2c8218…: holding [move.forward]
client   [18:17:43] bridge released move.forward
client   [18:17:43] bridge let go of its held input: the client is showing DeathScreen
server   [18:17:50] Kin has the following entity data: [-5.5d, -60.0d, 25.53d]   (and again at :55)
```

A death is the only way to make a client open a screen without touching the
client, which is what makes the two sides of this evidence independent: the
server says it killed the Kin, and the Bridge says it let go, in the same
second. It is also three of §12's triggers arriving through one mechanism — a
screen the player opened, the death screen, and the title screen a client falls
back to when a session ends are all "the keyboard is not the world's any more".

The label is the Bridge's own, not the class's name. A production client's
Minecraft classes are intermediary at runtime, so `getClass().getSimpleName()`
for the death screen is `class_418` — a token that means nothing to a reader and
changes with every version. Measured here first, then confirmed against the Yarn
mappings. So the Bridge names the screens it can prove it is looking at
(`DeathScreen`, `GameMenuScreen`, `TitleScreen`, `ConnectScreen`) and says
`SomeScreen` for anything else. The snapshot's `self.current_screen` still
carries the class name; changing what a *product event* holds is its own
decision, and it is recorded as an open item rather than quietly done here.

### Refusals get classified too

Setting `MINEKIN_USERNAME` to another name whitelists that name instead of the
Kin's — the client's own username comes from the identity root, not the
environment — so the domain refuses the Kin:

```text
server   Disconnecting Kin (…): You are not white-listed on this server!
client   bridge observed a login disconnect from the server: You are not white-listed on this server!
client   bridge classified the login failure as ADMISSION_FAILURE_REASON_WHITELIST_REJECTED
ledger   SessionInterrupted  {"phase":"FAILED","reason":"ADMISSION_FAILURE_REASON_WHITELIST_REJECTED"}
```

The server's sentence stays in the local log; only the category reaches the
ledger, because a server may say anything and the product event may not carry
it. The hook is `onDisconnect(LoginDisconnectS2CPacket)`, measured rather than
guessed: `onDisconnected` is not reached for a kick the server sends.

A second login under the same name — a probe, while the managed client is
already in the world — exercises the other kind of ending:

```text
server   Kin lost connection: You logged in from another location
client   bridge observed a disconnect from the server: You logged in from another location
client   bridge classified the disconnect as ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN
ledger   SessionInterrupted  {"phase":"FAILED","reason":"ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN"}
```

That used to be recorded as `{"phase":"DISCONNECTED"}` — a session the server
threw out, written down as one that stopped on its own. A disconnect *without* a
reason is a session that ended; one *with* a reason is a session the server
ended.
