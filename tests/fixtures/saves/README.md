# A prepared world, as a file

`kinworld/level.dat` is the world a host case starts from: 1,636 bytes of gzipped NBT,
and nothing else. A Minecraft save is normally a directory — region files, entities,
player data — but the only file that makes a directory a *world* is this one: it holds
the level name, the difficulty, whether commands are allowed, and the generator settings
(a flat world with the seed `minekin-p0-controlled`). Vanilla generates the terrain from
those settings the first time it loads the world, so a save with no chunks is a world
that has not been generated yet rather than one that is empty.

That is what makes it a fixture worth committing. Measured in the runner: a managed
client enters a world seeded from this file alone (`Started serving on 25570`), and the
whole world is 1.6 KiB instead of the 5.3 MiB a played-in save becomes, so the bytes a
host case starts from can live in the repository and be identical on every machine.

It is also why the file is pinned *raw* in `tests/fixtures/manifest.sha256`: the digest
in this repository's text fixtures normalises line endings, and a gzipped blob that
someone's checkout converted would be a different world wearing the same name.

It was produced once, by the controlled server:

```text
MINEKIN_SERVER_JAR=<pinned 1.21.4 server jar> \
    bash test-orchestrator/runner/run.sh server --accept-eula --allow-player Kin
```

and then the `level.dat` out of the world that run generated. It is not generated per
run on purpose: a world generated per run is a different world every time (`LastPlayed`
alone moves), while a case wants the world it started from to be nameable. Regenerating
it means a new fixture and a new pin, not an edit.
