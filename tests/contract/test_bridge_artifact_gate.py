"""The gate that reads the build output, and the two ways it could be useless.

`check_bridge_host_boundary.py` reads the sources. This gate reads what the compiler
left behind, which is a different question and a harder one to ask: the artifact is
remapped, so the names it carries are not the names anyone wrote, and half of what is
in it was put there by `javac` rather than by a person.

The tests below are of two kinds and they are not the same claim. The ones that build
an artifact out of class files this module assembles say the gate catches what it is
supposed to catch. The ones that run it against the real jar and the real Yarn mappings
say those answers are not artefacts of the fixtures.
"""

from __future__ import annotations

import hashlib
import io
import json
import struct
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/check_bridge_artifacts.py"
NAMES = REPOSITORY_ROOT / "bridge" / "host-boundary-names.json"
REAL_JAR = REPOSITORY_ROOT / "bridge" / "build" / "libs" / "minekin-bridge-0.0.0.jar"

#: The Yarn names this repository's Bridge legitimately uses, and the intermediary ones
#: they are remapped to. Read from the checked-in table rather than restated, so a test
#: cannot agree with a stale copy of the answer.
VOCABULARY = json.loads(NAMES.read_text(encoding="utf-8"))["aliases"]
INTEGRATED_SERVER = VOCABULARY["IntegratedServer"]
SERVER_WORLD = VOCABULARY["ServerWorld"]
GET_SERVER = VOCABULARY["getServer()"]
UNSEEN_METHOD = "method_99999999"


# ---------------------------------------------------------------------------
# Building artifacts
# ---------------------------------------------------------------------------


def class_file(
    declared: str,
    types: Sequence[str] = (),
    calls: Sequence[tuple[str, str]] = (),
    strings: Sequence[str] = (),
) -> bytes:
    """A class file with the constant pool this gate reads, and nothing after it.

    Only the pool is a real structure here: the gate stops reading once it has the
    declared name, so fields, methods and attributes would be bytes nothing looks at.
    Keeping the fixture to the part under test is what makes it possible to write the
    class a compiler would never emit — which is the point of a gate that reads compiled
    output, because neither would a compiler emit a leak.

    `strings` are bare pool entries with nothing referring to them, which is what a
    descriptor or a `Signature` attribute looks like from the pool's side.
    """

    pool: list[bytes] = []
    index: dict[tuple[str, ...], int] = {}

    def add(key: tuple[str, ...], entry: bytes) -> int:
        if key not in index:
            pool.append(entry)
            index[key] = len(pool)
        return index[key]

    def utf8(text: str) -> int:
        encoded = text.encode("utf-8")
        return add(("u", text), b"\x01" + struct.pack(">H", len(encoded)) + encoded)

    def klass(name: str) -> int:
        return add(("c", name), b"\x07" + struct.pack(">H", utf8(name)))

    def name_and_type(name: str, descriptor: str) -> int:
        return add(
            ("n", name, descriptor),
            b"\x0c" + struct.pack(">HH", utf8(name), utf8(descriptor)),
        )

    this_class = klass(declared)
    for name in types:
        klass(name)
    for text in strings:
        utf8(text)
    for owner, name in calls:
        pool.append(b"\x0a" + struct.pack(">HH", klass(owner), name_and_type(name, "()V")))
    header = struct.pack(">IHHH", 0xCAFEBABE, 0, 65, len(pool) + 1)
    return header + b"".join(pool) + struct.pack(">HH", 0x0021, this_class)


def entrypoint_class() -> bytes:
    return class_file("org/minekin/bridge/MinekinBridgeClient")


def valid_entries() -> dict[str, bytes]:
    """A bundle with nothing wrong with it, for tests to add one thing to."""

    return {
        "fabric.mod.json": json.dumps(
            {
                "schemaVersion": 1,
                "id": "minekin_bridge",
                "environment": "client",
                "entrypoints": {"client": ["org.minekin.bridge.MinekinBridgeClient"]},
                "mixins": ["minekin_bridge.mixins.json"],
            }
        ).encode(),
        "minekin_bridge.mixins.json": json.dumps(
            {"required": True, "package": "org.minekin.bridge.mixin", "client": []}
        ).encode(),
        "org/minekin/bridge/MinekinBridgeClient.class": entrypoint_class(),
    }


def jar(tmp_path: Path, entries: Mapping[str, bytes], name: str = "artifact.jar") -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        for member, data in entries.items():
            archive.writestr(member, data)
    return path


def classes_dir(tmp_path: Path, entries: Mapping[str, bytes]) -> Path:
    root = tmp_path / "classes"
    for member, data in entries.items():
        target = root / member
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def scan(artifact: Path) -> subprocess.CompletedProcess[str]:
    return run("--artifact", str(artifact))


def with_one(entry: str, data: bytes) -> dict[str, bytes]:
    entries = valid_entries()
    entries[entry] = data
    return entries


# ---------------------------------------------------------------------------
# The boundary, in the names the build actually uses
# ---------------------------------------------------------------------------


def test_a_server_type_outside_the_adapter_is_refused(tmp_path: Path) -> None:
    """The intermediary spelling, which is the only one the production jar has."""

    entries = with_one(
        "org/minekin/bridge/core/Leak.class",
        class_file("org/minekin/bridge/core/Leak", types=[INTEGRATED_SERVER[0]]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert INTEGRATED_SERVER[0] in result.stderr
    assert "IntegratedServer" in result.stderr


def test_the_yarn_spelling_is_refused_too(tmp_path: Path) -> None:
    """The stub compile CI runs produces named names, so a gate that only knew
    intermediary ones would be blind on the only artifact CI has."""

    entries = with_one(
        "org/minekin/bridge/core/Leak.class",
        class_file("org/minekin/bridge/core/Leak", types=[SERVER_WORLD[1]]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert SERVER_WORLD[1] in result.stderr


def test_a_call_to_the_server_door_outside_the_adapter_is_refused(tmp_path: Path) -> None:
    entries = with_one(
        "org/minekin/bridge/core/Leak.class",
        class_file(
            "org/minekin/bridge/core/Leak", calls=[("net/minecraft/class_310", GET_SERVER[0])]
        ),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert GET_SERVER[0] in result.stderr
    assert "getServer()" in result.stderr


def test_every_spelling_of_a_member_is_a_denial(tmp_path: Path) -> None:
    """`getServer` is a method on nine Yarn classes and each has its own intermediary
    name. A table keyed by name alone keeps whichever was read last and recognises one
    spelling out of nine — a hole that reads as a table that is merely short.
    """

    assert len(GET_SERVER) > 1
    for spelling in GET_SERVER:
        entries = with_one(
            "org/minekin/bridge/core/Leak.class",
            class_file(
                "org/minekin/bridge/core/Leak", calls=[("net/minecraft/class_310", spelling)]
            ),
        )
        result = scan(jar(tmp_path, entries))
        assert result.returncode == 1, spelling
        assert spelling in result.stderr, spelling


def test_a_member_that_is_not_a_denied_name_is_left_alone(tmp_path: Path) -> None:
    """The negative control: refusing every call would refuse the mod."""

    entries = with_one(
        "org/minekin/bridge/core/Fine.class",
        class_file(
            "org/minekin/bridge/core/Fine", calls=[("net/minecraft/class_310", UNSEEN_METHOD)]
        ),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 0, result.stderr


def test_the_adapter_may_name_the_server_it_drives(tmp_path: Path) -> None:
    """The negative control for the tier above: refusing this would refuse the job."""

    entries = with_one(
        "org/minekin/bridge/host/IntegratedServerControl.class",
        class_file(
            "org/minekin/bridge/host/IntegratedServerControl",
            types=[INTEGRATED_SERVER[0]],
            calls=[("net/minecraft/class_310", GET_SERVER[0])],
        ),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 0, result.stderr


def test_what_is_in_the_world_is_refused_even_in_the_adapter(tmp_path: Path) -> None:
    """The adapter drives the server's lifecycle; it does not get to read the world.

    Otherwise the boundary would have moved rather than closed: server truth would reach
    the product through the module that is allowed to touch the server.
    """

    entries = with_one(
        "org/minekin/bridge/host/Leak.class",
        class_file("org/minekin/bridge/host/Leak", types=[SERVER_WORLD[0]]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert SERVER_WORLD[0] in result.stderr


def test_a_server_reference_in_a_mixin_is_refused(tmp_path: Path) -> None:
    """A mixin is one of the four places the control-boundary contract names, not a detail.

    It is the only class here written to be injected into someone else's types — it
    runs inside vanilla's own bytecode — so it is the one place where naming server
    state would not merely read the world but sit inside the code that holds it. The
    configuration in this bundle is valid and points at the mod's own package, so what
    is being refused is the reference and nothing else.
    """

    entries = with_one(
        "org/minekin/bridge/mixin/ServerLeakMixin.class",
        class_file(
            "org/minekin/bridge/mixin/ServerLeakMixin",
            types=[INTEGRATED_SERVER[0]],
        ),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert INTEGRATED_SERVER[0] in result.stderr
    assert "IntegratedServer" in result.stderr


def test_a_mixin_that_names_no_server_state_is_left_alone(tmp_path: Path) -> None:
    """The negative control: the rule is about the reference, not about mixing in.

    A gate that refused every mixin would refuse the mechanism the Bridge is built
    on, and the whole boundary would have to be read as "no mixins" instead of as
    "no server state".
    """

    entries = with_one(
        "org/minekin/bridge/mixin/HarmlessMixin.class",
        class_file(
            "org/minekin/bridge/mixin/HarmlessMixin",
            calls=[("net/minecraft/class_310", UNSEEN_METHOD)],
        ),
    )

    assert scan(jar(tmp_path, entries)).returncode == 0


def test_one_reference_is_reported_once(tmp_path: Path) -> None:
    """The server package covers every server type, so `class_1132` is denied twice.

    One crossing reported twice reads as two problems, and the specific rule is the one
    worth reading.
    """

    entries = with_one(
        "org/minekin/bridge/core/Leak.class",
        class_file("org/minekin/bridge/core/Leak", types=[INTEGRATED_SERVER[0]]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert result.stderr.count(INTEGRATED_SERVER[0]) == 1


def test_a_generic_parameter_is_a_reference(tmp_path: Path) -> None:
    """Erasure hides a type from the code, not from the constant pool.

    A `List<IntegratedServer>` field erases to `List`, so no class entry names the server
    type; the type is in a descriptor no source reading of the compiled code would see.
    """

    entries = with_one(
        "org/minekin/bridge/core/Generic.class",
        class_file(
            "org/minekin/bridge/core/Generic",
            strings=[f"Ljava/util/List<L{INTEGRATED_SERVER[0]};>;"],
        ),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert INTEGRATED_SERVER[0] in result.stderr


# ---------------------------------------------------------------------------
# What the compiler put there, not what a person wrote
# ---------------------------------------------------------------------------


def test_the_lambda_bootstrap_is_not_a_reflection_escape(tmp_path: Path) -> None:
    """Measured, not assumed: `javac` emits `MethodHandles.lookup()` in every lambda.

    Denying the type at this level fired on 28 of this repository's own classes, none of
    which reflect at anything. The capability-granting members are still refused.
    """

    entries = with_one(
        "org/minekin/bridge/core/Lambda.class",
        class_file(
            "org/minekin/bridge/core/Lambda",
            types=["java/lang/invoke/MethodHandles$Lookup", "java/lang/invoke/LambdaMetafactory"],
            calls=[("java/lang/invoke/MethodHandles", "lookup")],
        ),
    )

    assert scan(jar(tmp_path, entries)).returncode == 0


def test_a_capability_granting_method_handle_is_refused(tmp_path: Path) -> None:
    """The negative control for the rule above: precision is not permission."""

    entries = with_one(
        "org/minekin/bridge/core/Escape.class",
        class_file(
            "org/minekin/bridge/core/Escape",
            calls=[("java/lang/invoke/MethodHandles", "privateLookupIn")],
        ),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "privateLookupIn" in result.stderr


def test_reflection_by_name_is_refused(tmp_path: Path) -> None:
    entries = with_one(
        "org/minekin/bridge/core/Escape.class",
        class_file("org/minekin/bridge/core/Escape", calls=[("java/lang/Class", "forName")]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "forName" in result.stderr


def test_a_class_whose_name_and_address_disagree_is_refused(tmp_path: Path) -> None:
    """A move that leaves the class's own name alone still declares the old package.

    Which module a class belongs to is what it declares, exactly as the source gate
    reads a file's `package` line — so disagreeing is a violation whichever way round.
    """

    entries = with_one(
        "org/minekin/bridge/runtime/Smuggled.class",
        class_file("org/minekin/bridge/host/Smuggled", types=[INTEGRATED_SERVER[0]]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "declares org/minekin/bridge/host/Smuggled" in result.stderr


def test_the_declared_name_is_what_decides_the_allowance(tmp_path: Path) -> None:
    """Both halves at once: the mismatch is reported *and* the reference is caught.

    Declaring the adapter's package is not enough to be granted its allowance — the
    address has to agree, because the loader looks a class up by its entry and this one
    is not reachable under the name it declares. There are two answers to which module
    it belongs to, so it does not get the benefit of either.
    """

    entries = with_one(
        "org/minekin/bridge/runtime/Smuggled.class",
        class_file("org/minekin/bridge/host/Smuggled", types=[INTEGRATED_SERVER[0]]),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert INTEGRATED_SERVER[0] in result.stderr


# ---------------------------------------------------------------------------
# The other four surfaces
# ---------------------------------------------------------------------------


def test_a_test_probe_in_the_bundle_is_refused(tmp_path: Path) -> None:
    """The contract keeps `bridge-test-probes` in a source set the bundle is built
    without, and a bundle is exactly where they would not be missed until they were."""

    entries = with_one(
        "org/minekin/bridge/probe/ServerCanary.class",
        class_file("org/minekin/bridge/probe/ServerCanary"),
    )

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "test probe" in result.stderr


def test_a_class_from_outside_the_reviewed_packages_is_refused(tmp_path: Path) -> None:
    entries = with_one("com/example/Stowaway.class", class_file("com/example/Stowaway"))

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "not in a package this repository produces" in result.stderr


def test_a_mixin_configuration_pointing_outside_the_mod_package_is_refused(
    tmp_path: Path,
) -> None:
    entries = valid_entries()
    entries["minekin_bridge.mixins.json"] = json.dumps(
        {"package": "org.minekin.bridge.host", "client": []}
    ).encode()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "declares mixin package" in result.stderr


def test_a_mixin_the_bundle_does_not_contain_is_refused(tmp_path: Path) -> None:
    entries = valid_entries()
    entries["minekin_bridge.mixins.json"] = json.dumps(
        {"package": "org.minekin.bridge.mixin", "client": ["NowhereMixin"]}
    ).encode()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "NowhereMixin" in result.stderr


def test_an_access_widener_naming_server_state_is_refused(tmp_path: Path) -> None:
    """Widening is how a mod reaches a type it was not allowed to name, and it is a file
    rather than a line of code — so the source gate reads past it entirely."""

    entries = valid_entries()
    manifest = json.loads(entries["fabric.mod.json"])
    manifest["accessWidener"] = "minekin_bridge.accesswidener"
    entries["fabric.mod.json"] = json.dumps(manifest).encode()
    entries["minekin_bridge.accesswidener"] = (
        "accessWidener v2 named\n"
        "# a comment naming IntegratedServer is not a widening of it\n"
        f"accessible class {INTEGRATED_SERVER[1]}\n"
    ).encode()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert INTEGRATED_SERVER[1] in result.stderr
    assert "# a comment" not in result.stderr


def test_an_access_widener_the_manifest_names_but_the_bundle_lacks_is_refused(
    tmp_path: Path,
) -> None:
    entries = valid_entries()
    manifest = json.loads(entries["fabric.mod.json"])
    manifest["accessWidener"] = "minekin_bridge.accesswidener"
    entries["fabric.mod.json"] = json.dumps(manifest).encode()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "which the bundle does not contain" in result.stderr


def test_an_entrypoint_the_bundle_does_not_contain_is_refused(tmp_path: Path) -> None:
    entries = valid_entries()
    manifest = json.loads(entries["fabric.mod.json"])
    manifest["entrypoints"] = {"client": ["org.minekin.bridge.Nowhere"]}
    entries["fabric.mod.json"] = json.dumps(manifest).encode()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "Nowhere" in result.stderr


def test_an_entrypoint_from_outside_the_reviewed_packages_is_refused(tmp_path: Path) -> None:
    entries = valid_entries()
    manifest = json.loads(entries["fabric.mod.json"])
    manifest["entrypoints"] = {"client": ["com.example.Entry"]}
    entries["fabric.mod.json"] = json.dumps(manifest).encode()
    entries["com/example/Entry.class"] = class_file("com/example/Entry")

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "outside the reviewed packages" in result.stderr


def test_a_server_side_bundle_is_refused(tmp_path: Path) -> None:
    entries = valid_entries()
    manifest = json.loads(entries["fabric.mod.json"])
    manifest["environment"] = "*"
    entries["fabric.mod.json"] = json.dumps(manifest).encode()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "not client" in result.stderr


def test_a_dependency_that_was_not_reviewed_is_refused(tmp_path: Path) -> None:
    entries = valid_entries()
    entries["META-INF/jars/surprise-1.0.jar"] = jar(
        tmp_path, {"com/example/X.class": b""}
    ).read_bytes()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "not in the reviewed set" in result.stderr


def test_a_reviewed_dependency_under_another_digest_is_refused(tmp_path: Path) -> None:
    """A pinned artifact under a different digest is one nobody reviewed.

    The bundle here is a real jar with the reviewed name and other bytes, which is the
    shape a swapped dependency actually has — not a corrupted one, which is caught a
    layer earlier for a different reason.
    """

    entries = valid_entries()
    entries["META-INF/jars/protobuf-javalite-4.36.2.jar"] = jar(
        tmp_path,
        {"com/example/NotProtobuf.class": class_file("com/example/NotProtobuf")},
        "other.jar",
    ).read_bytes()

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "not the reviewed" in result.stderr


def test_a_packed_entry_that_is_not_a_jar_at_all_is_refused(tmp_path: Path) -> None:
    """The failure mode above reaches a different branch, and it must not be a pass."""

    entries = valid_entries()
    entries["META-INF/jars/protobuf-javalite-4.36.2.jar"] = b"not a zip file"

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 2
    assert "is not a jar" in result.stderr


def test_a_dependencys_own_reflection_is_not_a_boundary_crossing(tmp_path: Path) -> None:
    """What governs a packed dependency is its digest, not its internals.

    Measured: protobuf-javalite reflects on its own classes throughout, so scanning it
    for the boundary markers reports a reviewed dependency as a crossing thirty-four
    times and teaches everyone to ignore the gate. The digest in this bundle is the
    reviewed one, so the only way to build this case is to let a dependency carry the
    marker and keep its digest — which the review would have caught instead.
    """

    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as archive:
        archive.writestr(
            "com/google/protobuf/UnsafeUtil.class",
            class_file("com/google/protobuf/UnsafeUtil", types=["sun/misc/Unsafe"]),
        )
    entries = valid_entries()
    entries["META-INF/jars/protobuf-javalite-4.36.2.jar"] = nested.getvalue()

    result = scan(jar(tmp_path, entries))

    # Only the digest is reported: the marker inside it is not this repository's code.
    assert result.returncode == 1
    assert "not the reviewed" in result.stderr
    assert "Unsafe" not in result.stderr


# ---------------------------------------------------------------------------
# A gate that cannot see must not report a pass
# ---------------------------------------------------------------------------


def test_a_missing_artifact_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    result = run("--artifact", str(tmp_path / "nowhere.jar"))

    assert result.returncode == 2
    assert "is not there" in result.stderr


def test_an_artifact_with_no_classes_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    """A sources jar is the shape this catches: nothing was scanned."""

    path = jar(tmp_path, {"org/minekin/bridge/MinekinBridgeClient.java": b"class A {}"})

    result = scan(path)

    assert result.returncode == 2
    assert "no class files" in result.stderr


def test_a_class_this_gate_cannot_read_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    entries = with_one("org/minekin/bridge/core/Broken.class", b"not a class file")

    result = scan(jar(tmp_path, entries))

    assert result.returncode == 1
    assert "does not begin with a class file's magic number" in result.stderr
    assert "may call clean" in result.stderr


def test_a_missing_name_table_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    result = run(
        "--artifact", str(jar(tmp_path, valid_entries())), "--names", str(tmp_path / "no.json")
    )

    assert result.returncode == 2
    assert "cannot read the name table" in result.stderr


def test_a_vocabulary_the_table_does_not_spell_is_refused(tmp_path: Path) -> None:
    """A marker the table does not know is a rule nothing enforces.

    Refusing is what keeps the two files describing one vocabulary: adding a marker
    without re-deriving the table fails here rather than passing in silence.
    """

    table = json.loads(NAMES.read_text(encoding="utf-8"))
    del table["aliases"]["IntegratedServer"]
    stripped = tmp_path / "names.json"
    stripped.write_text(json.dumps(table), encoding="utf-8")

    result = run("--artifact", str(jar(tmp_path, valid_entries())), "--names", str(stripped))

    assert result.returncode == 2
    assert "does not spell them" in result.stderr


def test_a_marker_the_build_has_no_name_for_is_an_answer_not_an_error(
    tmp_path: Path,
) -> None:
    """`ServerLevel` is Mojang's spelling and Yarn calls the type `ServerWorld`.

    So there is nothing in the artifact for that marker to match, and the table says so
    rather than the gate pretending to check it. The source gate is the one that catches
    that spelling.
    """

    table = json.loads(NAMES.read_text(encoding="utf-8"))

    assert table["aliases"]["ServerLevel"] == []


def test_the_table_is_pinned_to_the_yarn_build_the_gradle_build_pins() -> None:
    """The table is a cached answer, and a cached answer for another build is wrong."""

    table = json.loads(NAMES.read_text(encoding="utf-8"))
    catalog = (REPOSITORY_ROOT / "bridge" / "gradle" / "libs.versions.toml").read_text(
        encoding="utf-8"
    )

    assert f'yarn = "{table["yarn"]}"' in catalog


# ---------------------------------------------------------------------------
# Deriving the table, and noticing when it has gone stale
# ---------------------------------------------------------------------------

TINY_HEADER = "tiny\t2\t0\tofficial\tintermediary\tnamed\n"


def tiny_mappings() -> bytes:
    return (
        TINY_HEADER
        + "c\ta\tnet/minecraft/class_310\tnet/minecraft/client/MinecraftClient\n"
        + "\tm\t()V\tb\tmethod_9211\tgetServer\n"
        + "c\tc\tnet/minecraft/class_1132\tnet/minecraft/server/integrated/IntegratedServer\n"
    ).encode()


def test_the_derivation_reads_members_and_classes(tmp_path: Path) -> None:
    """A tiny v2 file indents its members under the class they belong to.

    Reading the raw first character reads a tab for every member and finds none of them,
    which looks exactly like a build that has no such name.
    """

    mappings = tmp_path / "mappings.tiny"
    mappings.write_text(tiny_mappings().decode(), encoding="utf-8")
    table = tmp_path / "names.json"

    result = run("--derive-names", "--mappings", str(mappings), "--names", str(table))

    assert result.returncode == 0, result.stderr
    aliases = json.loads(table.read_text(encoding="utf-8"))["aliases"]
    assert aliases["getServer()"] == ["method_9211"]
    assert sorted(aliases["IntegratedServer"]) == [
        "net/minecraft/class_1132",
        "net/minecraft/server/integrated/IntegratedServer",
    ]
    assert aliases["ServerWorld"] == []


def test_verifying_against_the_mappings_it_was_derived_from_is_clean(tmp_path: Path) -> None:
    mappings = tmp_path / "mappings.tiny"
    mappings.write_text(tiny_mappings().decode(), encoding="utf-8")
    table = tmp_path / "names.json"
    run("--derive-names", "--mappings", str(mappings), "--names", str(table))

    result = run(
        "--artifact",
        str(jar(tmp_path, valid_entries())),
        "--names",
        str(table),
        "--mappings",
        str(mappings),
    )

    assert result.returncode == 0, result.stderr


def test_a_table_derived_from_other_mappings_is_refused(tmp_path: Path) -> None:
    """The mappings moved and the table did not — the answer is a decision, not a rewrite."""

    mappings = tmp_path / "mappings.tiny"
    mappings.write_text(tiny_mappings().decode(), encoding="utf-8")
    table = tmp_path / "names.json"
    run("--derive-names", "--mappings", str(mappings), "--names", str(table))
    mappings.write_text(
        tiny_mappings().decode().replace("method_9211", "method_9999"), encoding="utf-8"
    )

    result = run(
        "--artifact",
        str(jar(tmp_path, valid_entries())),
        "--names",
        str(table),
        "--mappings",
        str(mappings),
    )

    assert result.returncode == 2
    assert "re-derive it" in result.stderr


def test_mappings_that_are_not_tiny_are_refused(tmp_path: Path) -> None:
    mappings = tmp_path / "mappings.txt"
    mappings.write_text("class A\n", encoding="utf-8")

    result = run("--derive-names", "--mappings", str(mappings), "--names", str(tmp_path / "n.json"))

    assert result.returncode == 2
    assert "not a tiny v2 mapping file" in result.stderr


# ---------------------------------------------------------------------------
# The real artifacts
# ---------------------------------------------------------------------------


def test_the_compiled_classes_are_scanned_the_same_way_a_jar_is(tmp_path: Path) -> None:
    """CI has no Minecraft and so no remapped jar; it has a compiled classes directory.

    A gate that could only read a jar would be one CI never runs.
    """

    entries = with_one(
        "org/minekin/bridge/core/Leak.class",
        class_file("org/minekin/bridge/core/Leak", types=[INTEGRATED_SERVER[0]]),
    )

    result = scan(classes_dir(tmp_path, entries))

    assert result.returncode == 1
    assert INTEGRATED_SERVER[0] in result.stderr


def test_the_bridge_as_it_is_built_is_inside_the_boundary() -> None:
    """The real jar, against the real table, when this checkout has built one.

    Not a skip: when the artifact is there the gate runs over it, and when it is not the
    gate is the thing that says so. A fresh checkout has not built the Bridge, and this
    test says which of the two happened rather than passing quietly either way.
    """

    if not REAL_JAR.exists():
        result = scan(REAL_JAR)
        assert result.returncode == 2
        assert "is not there" in result.stderr
        return

    result = scan(REAL_JAR)

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_the_pinned_table_matches_the_build_the_jar_was_remapped_with() -> None:
    """The digest in the table is a claim about the mappings, and this is it.

    The mappings jar is what loom unpacks to build the jar above; when it is present the
    table is checked against it rather than taken on trust.
    """

    table = json.loads(NAMES.read_text(encoding="utf-8"))
    loom = Path.home() / ".gradle" / "caches" / "fabric-loom"
    candidates = sorted(loom.glob(f"*/net.fabricmc.yarn.*{table['yarn']}*/mappings.tiny"))
    if not candidates:
        return

    digest = hashlib.sha256(candidates[0].read_bytes()).hexdigest()

    assert digest == table["mappings"]["sha256"], (
        "the checked-in name table was derived from different mappings than the ones this "
        "checkout has"
    )
