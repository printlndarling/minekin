"""Fail the build when what it *produced* reaches for the server, not just what was written.

`check_bridge_host_boundary.py` reads the sources: it says which names a person is
allowed to write. Two things get past it, and the contract names both.

The first is the dependency tree and the compiler. A class constant pool holds a
resolved type in a descriptor, a method reached through an interface, a `Signature`
attribute nobody's source line spells out. None of that is a line this repository
wrote, and none of it is visible in the source tree the other gate reads.

The second is the names. The production jar is remapped to intermediary names by the
build: what ships calls `IntegratedServer` `net.minecraft.class_1132` and `getServer()`
`method_9211`. A gate that read the jar with the Yarn spellings would pass it every
time while reporting that it had looked — a name-based gate that cannot translate the
names is not a weaker gate, it is one that cannot see the thing it exists to see. So
the spellings come from `bridge/host-boundary-names.json`, derived from the pinned Yarn
build, and this gate refuses to run without them.

Both spellings are checked at once rather than one per artifact, because the repository
builds the Bridge two ways: Gradle with Minecraft (remapped, intermediary names) and
`check_bridge_proto_java.py`'s stub compile with neither (named names). A gate that
knew only one of them would be blind on one of the two artifacts, and CI only has the
second.

Five surfaces, because a boundary can be crossed on each: the classes' constant pools,
the mixin configuration, the access widener, the entrypoint, and the jars packed inside.
A test probe is a sixth: the contract keeps `bridge-test-probes` in a test-only source
set, and this is the gate that can see whether they stayed out.

What this does not do: it is not a proof that no server truth reaches a Kin, and it does
not replace the black-box canary gate. Same-JVM isolation cannot be proven by scanning;
the contract says so, and this gate is one of the four it asks for rather than all of
them. A marker the pinned Yarn build has no name for — `ServerLevel`, which Yarn calls
`ServerWorld` — resolves to no spelling at all, and the gate says so in its table rather
than pretending to check it; the source gate is the one that catches that spelling.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import struct
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = REPOSITORY_ROOT / "bridge" / "build" / "libs" / "minekin-bridge-0.0.0.jar"

#: The other half of the vocabulary in `bridge_host_rules.py`: how each marker is
#: spelled once the build has remapped it. Derived, pinned, and re-derivable.
DEFAULT_NAMES = REPOSITORY_ROOT / "bridge" / "host-boundary-names.json"

#: Where the Yarn version a table was derived from is pinned. Read rather than passed
#: on the command line so the table and the build cannot name two versions. One root
#: per Minecraft version, so the catalogue is found beside the table rather than
#: hardcoded: a 1.20.1 table labelled from the 1.21.4 pin would be a table that reads
#: the jar through spellings that jar cannot contain.
VERSION_CATALOG = REPOSITORY_ROOT / "bridge" / "gradle" / "libs.versions.toml"

# The vocabulary lives beside this file, and this is the gate that reads what the
# compiler left behind. Imported rather than restated: two copies of these tables
# would be two rules, and the copy in the gate that cannot see the hole is the one
# that would drift.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge_host_rules import (  # noqa: E402
    DENIED_ALWAYS,
    DENIED_OUTSIDE_HOST,
    HOST_PACKAGE_PATH,
    PROBE_PACKAGE_PREFIXES,
)

#: The packages a production Bridge bundle is made of. Anything else in it arrived
#: from somewhere, and a bundle whose contents nobody enumerated is the thing this
#: surface exists to refuse. The generated protobuf classes are the second entry
#: because they are build output of this repository rather than a dependency.
PRODUCTION_PACKAGE_PREFIXES: Final[tuple[str, ...]] = (
    "org/minekin/bridge/",
    "io/minekin/protocol/",
)

#: Where loom's `include(...)` puts a dependency, and the reviewed set of what may be
#: found there. The digest is of the jar as it is packed; the protobuf runtime is named
#: with the version `bridge/gradle.lockfile` locks, because a pinned build input under
#: a digest nobody derived is not pinned.
PACKED_JAR_DIRECTORY = "META-INF/jars/"
PACKED_JARS: Final[dict[str, str]] = {
    # protobuf-javalite-4.36.2.jar, as loom packs it into the bundle.
    "protobuf-javalite-4.36.2.jar": (
        "8b620ac7150930b4802597a021ce4aa1957ea1b9e8d71bdf2845fb6bfb89c01e"
    ),
}

#: The mixin package the mod's own configuration declares, and the only one its mixins
#: may live in. A mixin is the one class here written to run inside someone else's
#: types, so where its configuration points is not a detail.
MIXIN_PACKAGE = "org.minekin.bridge.mixin"

#: Markers that are not Minecraft names and so cannot be in the mappings. Their
#: spelling in an artifact is mechanical, but the *kind* is declared rather than
#: guessed, because guessing is how a marker quietly becomes unchecked:
#:   `class`  — an internal class name
#:   `prefix` — a package, matched as the head of an internal class name
#:   `member` — a member name, matched against every field and method reference
#:   `owned`  — `owner#name`, matched against that pair in a member reference
#:
#: `MethodHandles` is the one that had to be narrowed, and the measurement is why: the
#: constant pool of a class that uses a lambda names `java/lang/invoke/MethodHandles`
#: because `javac` emits a `MethodHandles.lookup()` call in every `LambdaMetafactory`
#: bootstrap. Denying the type at this level is a lambda detector, not a boundary gate —
#: it fired on 28 of this repository's own classes, none of which reflect at anything.
#: What it must still catch is the capability-granting members, which no bootstrap uses.
MECHANICAL_MARKERS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "java.lang.reflect": ("prefix", ("java/lang/reflect/",)),
    "java.lang.invoke.MethodHandles": (
        "owned",
        (
            "java/lang/invoke/MethodHandles#privateLookupIn",
            "java/lang/invoke/MethodHandles#unreflect",
            "java/lang/invoke/MethodHandles#unreflectConstructor",
            "java/lang/invoke/MethodHandles#unreflectSpecial",
            "java/lang/invoke/MethodHandles#defineClass",
            "java/lang/invoke/MethodHandles#defineHiddenClass",
        ),
    ),
    "sun.misc.Unsafe": ("class", ("sun/misc/Unsafe",)),
    "Class.forName": ("owned", ("java/lang/Class#forName",)),
    "setAccessible": ("member", ("setAccessible",)),
}

#: A type named inside a descriptor or a `Signature` attribute: `Lpkg/Cls;`. Erasure
#: hides a type from the code a person wrote, not from the constant pool, and a rule
#: that reads only the code is a rule a generic parameter walks past.
TYPE_IN_DESCRIPTOR = re.compile(r"L([A-Za-z_$][A-Za-z0-9_$]*(?:/[A-Za-z0-9_$]+)+);")

_UTF8 = 1
_INTEGER = 3
_FLOAT = 4
_LONG = 5
_DOUBLE = 6
_CLASS = 7
_STRING = 8
_FIELD_REF = 9
_METHOD_REF = 10
_INTERFACE_METHOD_REF = 11
_NAME_AND_TYPE = 12
_METHOD_HANDLE = 15
_METHOD_TYPE = 16
_DYNAMIC = 17
_INVOKE_DYNAMIC = 18
_MODULE = 19
_PACKAGE = 20

_MEMBER_REF_TAGS = frozenset({_FIELD_REF, _METHOD_REF, _INTERFACE_METHOD_REF})
_INDEX_TAGS = frozenset({_CLASS, _STRING, _METHOD_TYPE, _MODULE, _PACKAGE})
_PAIR_INDEX_TAGS = frozenset({_DYNAMIC, _INVOKE_DYNAMIC, _NAME_AND_TYPE})

#: The namespace a table's alias lists are drawn from. Recorded in the file so a table
#: derived against some other mapping set is recognisable rather than merely wrong.
NAMESPACES: Final[tuple[str, ...]] = ("intermediary", "named")


class ArtifactError(Exception):
    """The artifact, or the table of names, is not something this gate can read."""


@dataclass(frozen=True, slots=True)
class Violation:
    """One crossing of the boundary, where it was found, and why it is one."""

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


@dataclass(frozen=True, slots=True)
class Marker:
    """One denied name, resolved to the spellings an artifact can carry it in."""

    spelling: str
    reason: str
    #: Internal class names, matched against the types a class file names, and package
    #: prefixes, which end in `/` and match as heads.
    types: frozenset[str]
    #: Member names, matched against the name half of every member reference.
    members: frozenset[str]
    #: `owner#name`, matched against the whole of a member reference.
    owned: frozenset[str]


@dataclass(frozen=True, slots=True)
class ParsedClass:
    """What one class file says, as far as a boundary gate needs to know."""

    declared: str
    #: Every type this class file names: constant-pool classes, plus whatever the
    #: descriptors and signature attributes erase to.
    referenced: frozenset[str]
    #: `owner#name` for every field, method and interface-method reference.
    members: frozenset[str]


@dataclass(frozen=True, slots=True)
class NameTable:
    """The pinned spellings, and what they were derived from."""

    yarn: str
    mappings_sha256: str
    #: Marker spelling as `bridge_host_rules.py` writes it -> artifact spellings. An
    #: empty list is a derived answer — the pinned Yarn build has no such name — and is
    #: kept rather than dropped so that it reads as an answer instead of an omission.
    aliases: Mapping[str, Sequence[str]]


# ---------------------------------------------------------------------------
# The names
# ---------------------------------------------------------------------------


def as_object(value: object) -> dict[str, object] | None:
    """A parsed JSON value, when it is an object, and nothing when it is not.

    `json.loads` answers `Any`, which under this repository's strict typing is a value
    nothing can be said about — every field read from it is unknown, and a gate whose
    reads are unknown is a gate whose rules cannot be read either. One place that says
    what shape is being asked for is cheaper than a cast at each of them.
    """

    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def _as_list(value: object) -> list[object]:
    """A JSON value as a list of its items, with a lone value read as a list of one.

    Fabric's manifest allows an entrypoint to be a string or a list of them, so both
    shapes arrive here and only one of them is iterable.
    """

    if isinstance(value, list):
        return cast("list[object]", value)
    return [] if value is None else [value]


def _text(source: Mapping[str, object], key: str) -> str:
    value = source.get(key)
    return value if isinstance(value, str) else ""


def _texts(source: Mapping[str, object], key: str) -> list[str]:
    return [item for item in _as_list(source.get(key)) if isinstance(item, str)]


def load_name_table(path: Path) -> NameTable:
    try:
        document = as_object(json.loads(path.read_text(encoding="utf-8")))
    except OSError as error:
        raise ArtifactError(f"cannot read the name table at {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ArtifactError(f"the name table at {path} is not JSON: {error}") from error
    if document is None or document.get("schema") != 1:
        raise ArtifactError(f"the name table at {path} is not schema 1")
    raw_aliases = as_object(document.get("aliases"))
    if raw_aliases is None:
        raise ArtifactError(f"the name table at {path} has no alias table")
    mappings = as_object(document.get("mappings"))
    if mappings is None:
        raise ArtifactError(f"the name table at {path} names no mappings build")
    # A marker whose list is empty is an answer — the pinned build has no such name —
    # so it is kept. A key whose value is not a list is not a table this gate can use.
    aliases = {key: _texts(raw_aliases, key) for key in raw_aliases}
    return NameTable(
        yarn=_text(document, "yarn"),
        mappings_sha256=_text(mappings, "sha256"),
        aliases=aliases,
    )


def parse_mappings(path: Path) -> list[dict[str, str]]:
    """Read a tiny v2 mapping file into one record per class, method and field.

    A list rather than a table keyed by name: `getServer` is a method on several Yarn
    classes and each of them has its own intermediary name, so a table keyed by name
    keeps whichever one was read last and the gate then recognises one spelling out of
    the several a class file could carry. That is a hole in a denylist and it looks
    exactly like a table that is merely short.

    The header names the namespaces and the columns follow that order, so a file that is
    not the pinned build still reads correctly rather than silently shifting by one.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ArtifactError(f"cannot read the mappings at {path}: {error}") from error
    lines = text.splitlines()
    if not lines or not lines[0].startswith("tiny\t2\t"):
        raise ArtifactError(f"{path} is not a tiny v2 mapping file")
    namespaces = lines[0].split("\t")[3:]
    if "named" not in namespaces or "intermediary" not in namespaces:
        raise ArtifactError(f"{path} does not carry both an intermediary and a named namespace")
    records: list[dict[str, str]] = []
    owner = ""
    for line in lines[1:]:
        # A class is a top-level line and its members are indented under it with a tab,
        # so the tag is the first field either way once the indent is off. Reading the
        # raw first character instead reads a tab for every member and finds no members
        # at all — a mistake that looks exactly like an empty answer.
        fields = line.lstrip("\t").split("\t")
        if fields[0] not in {"c", "m", "f"} or len(fields) < len(namespaces) + 1:
            continue
        # A method and a field carry their descriptor ahead of their names and a class
        # does not. The descriptor is dropped because this gate matches by name, and the
        # name at a call site is the ordinary one (`getServer`), not the resolved one.
        names = fields[1:] if fields[0] == "c" else fields[2:]
        record = dict(zip(namespaces, names, strict=False))
        if "named" not in record:
            continue
        record["kind"] = fields[0]
        if fields[0] == "c":
            owner = record["named"]
        else:
            record["owner"] = owner
        records.append(record)
    return records


def derive_name_table(mappings: Path) -> dict[str, list[str]]:
    """Every marker in the vocabulary, spelled the way the pinned build will spell it.

    A marker that is a Minecraft *type* gets the names that type is remapped to — both
    the intermediary one and the Yarn one, because the two Bridge builds use one each. A
    marker that is a Minecraft *member* gets the intermediary member names in its place.
    Anything else gets an empty list here and is declared in `MECHANICAL_MARKERS`
    instead; the gate refuses to run on a marker that is in neither, which is what makes
    a vocabulary that grows without its table fail loudly rather than quietly.
    """

    records = parse_mappings(mappings)
    aliases: dict[str, list[str]] = {}
    for marker in (*DENIED_ALWAYS, *DENIED_OUTSIDE_HOST):
        names: set[str] = set()
        bare = marker[:-2] if marker.endswith("()") else marker
        for record in records:
            if marker.endswith("."):
                if record["kind"] == "c" and record["named"].startswith(marker.replace(".", "/")):
                    names.update((record["intermediary"], record["named"]))
            elif marker.endswith("()"):
                if record["kind"] == "m" and record["named"] == bare:
                    names.add(record["intermediary"])
            elif record["kind"] == "c" and record["named"].rsplit("/", 1)[-1].split("$")[0] == bare:
                names.update((record["intermediary"], record["named"]))
        aliases[marker] = sorted(names)
    return aliases


def resolve_markers(aliases: Mapping[str, Sequence[str]]) -> tuple[Marker, ...]:
    """Every denied name as an artifact spells it, or a refusal to be a gate at all.

    This is where the two vocabularies are tied together. A marker that is neither in
    the name table nor in `MECHANICAL_MARKERS` would be a rule nothing enforces, so it
    is an error rather than a marker that matches nothing and looks enforced.
    """

    resolved: list[Marker] = []
    unspelled: list[str] = []
    for marker, reason in (*DENIED_ALWAYS.items(), *DENIED_OUTSIDE_HOST.items()):
        mechanical = MECHANICAL_MARKERS.get(marker)
        if mechanical is not None:
            kind, values = mechanical
            resolved.append(
                Marker(
                    spelling=marker,
                    reason=reason,
                    types=frozenset(values) if kind in {"class", "prefix"} else frozenset(),
                    members=frozenset(values) if kind == "member" else frozenset(),
                    owned=frozenset(values) if kind == "owned" else frozenset(),
                )
            )
            continue
        if marker not in aliases:
            unspelled.append(marker)
            continue
        # A call marker (`getServer()`) is a member; everything else here is a type. The
        # vocabulary has no third shape, and one that needed it would have to say so
        # rather than be guessed at.
        if marker.endswith("()"):
            # The bare name is the Yarn spelling and the aliases are the remapped ones,
            # and both artifacts matter: the remapped jar has only the aliases, and the
            # stub compile CI runs has only the bare name.
            members = {marker[:-2], *aliases[marker]}
            resolved.append(
                Marker(
                    spelling=marker,
                    reason=reason,
                    types=frozenset(),
                    members=frozenset(members),
                    owned=frozenset(),
                )
            )
        else:
            resolved.append(
                Marker(
                    spelling=marker,
                    reason=reason,
                    types=frozenset(aliases[marker]),
                    members=frozenset(),
                    owned=frozenset(),
                )
            )
    if unspelled:
        raise ArtifactError(
            f"the vocabulary names {', '.join(unspelled)} and the name table does not spell "
            "them. Re-derive the table from the pinned mappings (--derive-names) or declare "
            "the marker in MECHANICAL_MARKERS; a marker that resolves to nothing is a rule "
            "this gate would report as enforced"
        )
    return tuple(resolved)


def verify_against_mappings(table: NameTable, mappings: Path) -> str:
    """Whether the pinned table still says what the pinned mappings say.

    The table is checked in so the gate runs where there is no Minecraft to resolve
    names against, which is most of the time. That makes it a cached answer, and a
    cached answer nobody re-derives is how a name table stops describing the build it
    claims to. This is the re-derivation, and it compares rather than rewrites: a
    difference is a decision someone makes, not one this makes quietly.
    """

    digest = hashlib.sha256(mappings.read_bytes()).hexdigest()
    if table.mappings_sha256 and digest != table.mappings_sha256:
        return (
            f"the name table was derived from mappings {table.mappings_sha256} and {mappings} "
            f"is {digest} — re-derive it against the build that is pinned now"
        )
    derived = derive_name_table(mappings)
    for marker in sorted(set(derived) | set(table.aliases)):
        pinned = sorted(table.aliases.get(marker, []))
        if pinned != sorted(derived.get(marker, [])):
            return (
                f"the name table spells {marker} as {pinned or 'nothing'} and the mappings spell "
                f"it as {sorted(derived.get(marker, [])) or 'nothing'} — the table is stale"
            )
    return ""


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------


class _Reader:
    """A bounds-checked cursor over a class file."""

    def __init__(self, data: bytes, what: str) -> None:
        self._data = data
        self._at = 0
        self._what = what

    def take(self, count: int) -> bytes:
        if self._at + count > len(self._data):
            raise ArtifactError(f"{self._what} ends in the middle of its constant pool")
        chunk = self._data[self._at : self._at + count]
        self._at += count
        return chunk

    def u1(self) -> int:
        return self.take(1)[0]

    def u2(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def u4(self) -> int:
        return struct.unpack(">I", self.take(4))[0]


def parse_class(data: bytes, what: str) -> ParsedClass:
    """Read one class file's constant pool, and nothing after it.

    The pool is the whole of what a boundary gate needs: every type the compiler
    resolved and every member it reached for are entries there, including the ones that
    appear in no source line. Reading past it would mean reading the attributes, which
    say nothing this gate is asking about.
    """

    reader = _Reader(data, what)
    if reader.u4() != 0xCAFEBABE:
        raise ArtifactError(f"{what} does not begin with a class file's magic number")
    reader.u2()  # minor version
    reader.u2()  # major version
    count = reader.u2()
    utf8: list[str] = [""] * count
    #: A `CONSTANT_Class` entry holds an index into the pool, not a name, so the pool
    #: index of the entry is what the rest of the file refers to and the name is one
    #: hop further on. Reading the entry's own index as a name is how `this_class` came
    #: out empty and every member reference resolved to nothing — a gate that ran, found
    #: no members anywhere, and reported the boundary held.
    classes: dict[int, int] = {}
    member_refs: list[tuple[int, int]] = []
    pairs: dict[int, tuple[int, int]] = {}
    index = 1
    while index < count:
        tag = reader.u1()
        if tag == _UTF8:
            utf8[index] = reader.take(reader.u2()).decode("utf-8", errors="replace")
        elif tag in {_INTEGER, _FLOAT}:
            reader.u4()
        elif tag in {_LONG, _DOUBLE}:
            reader.take(8)
            index += 1  # a long and a double occupy two constant pool entries
        elif tag in _INDEX_TAGS:
            value = reader.u2()
            if tag == _CLASS:
                classes[index] = value
        elif tag in _MEMBER_REF_TAGS:
            member_refs.append((reader.u2(), reader.u2()))
        elif tag in _PAIR_INDEX_TAGS:
            pairs[index] = (reader.u2(), reader.u2())
        elif tag == _METHOD_HANDLE:
            reader.u1()
            reader.u2()
        else:
            raise ArtifactError(f"{what} carries constant pool tag {tag}, which is not a tag")
        index += 1

    reader.u2()  # access flags
    this_class = reader.u2()
    declared = _class_name(classes, utf8, this_class)

    referenced: set[str] = set()
    for name in (_class_name(classes, utf8, entry) for entry in classes):
        # An array is stored as its descriptor, so the type it holds is not an entry of
        # its own and would otherwise be missed.
        referenced.add(name[1:].rstrip(";") if name.startswith("[") else name)
    for text in utf8:
        referenced.update(TYPE_IN_DESCRIPTOR.findall(text))
    referenced.discard("")

    members: set[str] = set()
    for owner_index, pair_index in member_refs:
        owner = _class_name(classes, utf8, owner_index)
        name_index = pairs.get(pair_index, (0, 0))[0]
        name = utf8[name_index] if 0 < name_index < count else ""
        if owner and name:
            members.add(f"{owner}#{name}")
    return ParsedClass(
        declared=declared, referenced=frozenset(referenced), members=frozenset(members)
    )


def _class_name(classes: Mapping[int, int], utf8: Sequence[str], entry: int) -> str:
    """The type a `CONSTANT_Class` entry names, from the pool index that refers to it."""

    name_index = classes.get(entry, 0)
    return utf8[name_index] if 0 < name_index < len(utf8) else ""


def artifact_entries(artifact: Path) -> dict[str, bytes]:
    if artifact.is_dir():
        return {
            path.relative_to(artifact).as_posix(): path.read_bytes()
            for path in sorted(artifact.rglob("*"))
            if path.is_file()
        }
    try:
        with zipfile.ZipFile(artifact) as archive:
            return {
                name: archive.read(name) for name in archive.namelist() if not name.endswith("/")
            }
    except (OSError, zipfile.BadZipFile) as error:
        raise ArtifactError(f"cannot read {artifact} as a jar: {error}") from error


def nested_jars(entries: Mapping[str, bytes]) -> dict[str, dict[str, bytes]]:
    packed: dict[str, dict[str, bytes]] = {}
    for name, data in sorted(entries.items()):
        if not name.startswith(PACKED_JAR_DIRECTORY) or not name.endswith(".jar"):
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                packed[name] = {
                    member: archive.read(member)
                    for member in archive.namelist()
                    if not member.endswith("/")
                }
        except zipfile.BadZipFile as error:
            raise ArtifactError(
                f"{name} is packed in the artifact and is not a jar: {error}"
            ) from error
    return packed


def class_name_of(entry: str) -> str:
    """The internal name a class at this entry is expected to declare.

    Packaging can put a class somewhere other than where its name says —
    `META-INF/versions/<n>/` is Java's own answer for a multi-release jar — so that
    prefix comes off before the comparison rather than being read as a disagreement.
    """

    name = entry.split("!", 1)[-1]
    name = re.sub(r"^META-INF/versions/\d+/", "", name)
    return name[: -len(".class")]


def _within_host_adapter(internal: str) -> bool:
    return internal == HOST_PACKAGE_PATH or internal.startswith(HOST_PACKAGE_PATH + "/")


def scan_class(location: str, data: bytes, markers: Sequence[Marker]) -> list[Violation]:
    try:
        parsed = parse_class(data, location)
    except ArtifactError as error:
        return [
            Violation(
                location,
                f"{error} — an artifact this gate cannot read is not one it may call clean",
            )
        ]
    found: list[Violation] = []
    expected = class_name_of(location)
    if parsed.declared and parsed.declared != expected:
        found.append(
            Violation(
                location,
                f"declares {parsed.declared} and is addressed as {expected} — a class whose name "
                "and address disagree is how code gets past a rule that reads one of them",
            )
        )
    # The allowance follows the name the class declares, as the source gate's does — but
    # only when the address agrees with it, and for a reason that is about jars rather
    # than tidiness: the loader looks a class up by its entry, so a class declaring the
    # adapter's package while addressed somewhere else is not reachable under the name it
    # declares. There are two answers to which module it is, so it does not get the
    # adapter's allowance on the strength of either one.
    host = _within_host_adapter(parsed.declared) and parsed.declared == expected
    # A type can be denied by more than one marker — the server package covers every
    # server type — and one reference reported twice reads as two problems. The first
    # marker to deny a name is the one reported, and the vocabulary is ordered so that
    # the specific rule comes before the package that also contains it.
    reported: set[str] = set()
    for marker in markers:
        allowed_here = host and marker.spelling in DENIED_OUTSIDE_HOST
        if allowed_here:
            continue
        for name in sorted(parsed.referenced):
            if name in reported:
                continue
            if name in marker.types or any(
                prefix.endswith("/") and name.startswith(prefix) for prefix in marker.types
            ):
                reported.add(name)
                found.append(
                    Violation(location, f"names {name} ({marker.spelling}) — {marker.reason}")
                )
        if marker.members or marker.owned:
            for reference in sorted(parsed.members):
                if reference in reported:
                    continue
                owner, _, name = reference.partition("#")
                if name in marker.members or f"{owner}#{name}" in marker.owned:
                    reported.add(reference)
                    found.append(
                        Violation(
                            location, f"calls {reference} ({marker.spelling}) — {marker.reason}"
                        )
                    )
    return found


def scan_class_set(entries: Mapping[str, bytes], where: str, own_bundle: bool) -> list[Violation]:
    """Every class is production code and none of it is a probe.

    The contract keeps the test probes in a source set the bundle is built without, and
    a bundle is exactly where they would not be missed until they were. A probe is
    refused wherever it is found, inside a packed dependency included.

    The package rule is the wider one, and it belongs only to this repository's own
    output: a bundle whose contents nobody enumerated is not a reviewed build, however
    clean each class in it looks on its own. A packed dependency lives in its own
    packages by definition, and what governs it is the digest it was reviewed under.
    """

    found: list[Violation] = []
    for name in sorted(entries):
        if not name.endswith(".class"):
            continue
        internal = class_name_of(name)
        location = f"{where}{name}"
        if any(internal.startswith(prefix.replace(".", "/")) for prefix in PROBE_PACKAGE_PREFIXES):
            found.append(
                Violation(location, "is a test probe, which the production bundle is built without")
            )
        elif own_bundle and not any(
            internal.startswith(prefix) for prefix in PRODUCTION_PACKAGE_PREFIXES
        ):
            found.append(
                Violation(
                    location,
                    "is not in a package this repository produces — a bundle whose contents nobody "
                    f"enumerated is not a reviewed build (expected one of "
                    f"{', '.join(PRODUCTION_PACKAGE_PREFIXES)})",
                )
            )
    return found


def scan_packaging(
    entries: Mapping[str, bytes], packed: Mapping[str, Mapping[str, bytes]]
) -> list[Violation]:
    """Which jars are packed in, under what digest, and whether a probe came with them.

    The classes inside a packed dependency are not scanned for the boundary markers, and
    that is a decision rather than an omission. They are not this repository's code, the
    contract's rule about reflection is a rule about a person writing an escape hatch,
    and what governs a dependency is the digest it was reviewed under. Scanning them
    anyway was measured: protobuf-javalite uses `java.lang.reflect` and `sun.misc.Unsafe`
    on its own classes throughout, so a marker scan there reports a reviewed dependency
    as a boundary crossing thirty-four times and teaches everyone to ignore the gate.
    """

    found: list[Violation] = []
    for name, contents in sorted(packed.items()):
        basename = name[len(PACKED_JAR_DIRECTORY) :]
        reviewed = PACKED_JARS.get(basename)
        digest = hashlib.sha256(entries[name]).hexdigest()
        if reviewed is None:
            found.append(
                Violation(
                    name,
                    "is packed into the bundle and is not in the reviewed set — a dependency that "
                    "ships is a dependency someone reviewed",
                )
            )
        elif digest != reviewed:
            found.append(
                Violation(name, f"is packed under digest {digest}, not the reviewed {reviewed}")
            )
        found.extend(scan_class_set(contents, f"{name}!", own_bundle=False))
    return found


def scan_manifest(manifest: Mapping[str, object], entries: Mapping[str, bytes]) -> list[Violation]:
    """The mod's own manifest: what the loader will run, and where it will find it."""

    found: list[Violation] = []
    if manifest.get("environment") != "client":
        found.append(
            Violation(
                "fabric.mod.json",
                f"declares environment {manifest.get('environment')!r}, not client",
            )
        )
    entrypoints = as_object(manifest.get("entrypoints"))
    if not entrypoints:
        found.append(Violation("fabric.mod.json", "declares no entrypoints"))
        return found
    for kind, declared in sorted(entrypoints.items()):
        for target in _as_list(declared):
            if not isinstance(target, str):
                found.append(Violation("fabric.mod.json", f"entrypoint {kind} is not a class name"))
                continue
            entry = f"{target.replace('.', '/')}.class"
            if entry not in entries:
                found.append(
                    Violation(
                        "fabric.mod.json",
                        f"entrypoint {kind} names {target}, which the bundle does not contain",
                    )
                )
            elif not any(entry.startswith(prefix) for prefix in PRODUCTION_PACKAGE_PREFIXES):
                found.append(
                    Violation(
                        "fabric.mod.json",
                        f"entrypoint {kind} names {target} from outside the reviewed packages",
                    )
                )
    return found


def scan_mixins(entries: Mapping[str, bytes]) -> list[Violation]:
    """Every mixin the configuration lists is a class in this bundle, in this package.

    A mixin is the one class here written to run inside someone else's types, so what
    its configuration points at is not a detail: a configuration naming a class the
    bundle lacks is a mod that fails when it loads, and a package other than the mod's
    own is a mixin loaded into a namespace nobody declared.
    """

    found: list[Violation] = []
    for name in sorted(entries):
        if not name.endswith(".mixins.json") or "/" in name:
            continue
        try:
            document = as_object(json.loads(entries[name]))
        except json.JSONDecodeError as error:
            found.append(Violation(name, f"is not JSON: {error}"))
            continue
        if document is None:
            found.append(Violation(name, "is not an object"))
            continue
        package = _text(document, "package")
        if package != MIXIN_PACKAGE:
            found.append(
                Violation(name, f"declares mixin package {package!r}, not {MIXIN_PACKAGE!r}")
            )
            continue
        for key in ("client", "server", "mixins"):
            for mixin in _texts(document, key):
                entry = f"{MIXIN_PACKAGE.replace('.', '/')}/{mixin}.class"
                if entry not in entries:
                    found.append(
                        Violation(name, f"lists mixin {mixin}, which the bundle does not contain")
                    )
    return found


def scan_access_widener(
    manifest: Mapping[str, object], entries: Mapping[str, bytes], markers: Sequence[Marker]
) -> list[Violation]:
    """An access widener raises access in whatever it names, so it is a boundary surface.

    The contract's case for this gate injects a widener naming server state, and that is
    the point: widening is how a mod reaches a type it was not allowed to name, and it
    is a file rather than a line of code, so the source gate reads past it entirely.
    """

    found: list[Violation] = []
    declared = manifest.get("accessWidener")
    if isinstance(declared, str) and declared not in entries:
        found.append(
            Violation(
                "fabric.mod.json",
                f"declares the access widener {declared}, which the bundle does not contain",
            )
        )
    denied_types = {name for marker in markers for name in marker.types}
    denied_prefixes = {name for name in denied_types if name.endswith("/")}
    denied_members = {name for marker in markers for name in marker.members}
    # The name half of an owned marker is a member name too: a widener that opens
    # `Class.forName` spells the method and not the owner#method pair.
    denied_members.update(name.rpartition("#")[2] for marker in markers for name in marker.owned)
    reason_of = {
        spelling: marker.reason
        for marker in markers
        for spelling in (
            *marker.types,
            *marker.members,
            *(n.rpartition("#")[2] for n in marker.owned),
        )
    }
    for name in sorted(entries):
        if not name.endswith(".accesswidener"):
            continue
        for number, line in enumerate(
            entries[name].decode("utf-8", errors="replace").splitlines(), 1
        ):
            stripped = line.split("#", 1)[0].strip()
            if not stripped or stripped.startswith("accessWidener"):
                continue
            for token in stripped.split():
                if (
                    not token.replace("/", "")
                    .replace(".", "")
                    .replace("_", "")
                    .replace("$", "")
                    .isalnum()
                ):
                    continue
                internal = token.replace(".", "/")
                hit = internal in denied_types or any(
                    internal.startswith(prefix) for prefix in denied_prefixes
                )
                if not hit and token in denied_members:
                    hit = True
                if hit:
                    found.append(
                        Violation(
                            name,
                            f"{number}: widens {token} — "
                            f"{reason_of.get(internal, reason_of.get(token, 'a denied name'))}",
                        )
                    )
    return found


def violations(artifact: Path, table: NameTable) -> list[Violation]:
    markers = resolve_markers(table.aliases)
    entries = artifact_entries(artifact)
    classes = {name: data for name, data in entries.items() if name.endswith(".class")}
    if not classes:
        raise ArtifactError(
            f"{artifact} contains no class files — nothing was scanned, and a gate that scanned "
            "nothing must not say the boundary held"
        )
    packed = nested_jars(entries)
    found = scan_class_set(entries, "", own_bundle=True)
    found.extend(scan_packaging(entries, packed))
    for name, data in sorted(classes.items()):
        found.extend(scan_class(name, data, markers))
    manifest = entries.get("fabric.mod.json")
    if manifest is None:
        found.append(
            Violation("fabric.mod.json", "is absent — a bundle with no manifest is not the mod")
        )
        return found
    try:
        document = as_object(json.loads(manifest))
    except json.JSONDecodeError as error:
        found.append(Violation("fabric.mod.json", f"is not JSON: {error}"))
        return found
    if document is None:
        found.append(Violation("fabric.mod.json", "is not an object"))
        return found
    found.extend(scan_manifest(document, entries))
    found.extend(scan_mixins(entries))
    found.extend(scan_access_widener(document, entries, markers))
    return found


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def version_catalog(names_path: Path) -> Path:
    """The catalogue of the root this name table belongs to.

    Found beside the table rather than named by the caller: a table and the pin it was
    derived from are one decision, and letting the command line point them at two roots
    is how a jar ends up scanned with spellings it cannot contain.
    """

    return names_path.parent / "gradle" / "libs.versions.toml"


def pinned_yarn_version(catalog: Path = VERSION_CATALOG) -> str:
    """The Yarn version the build pins, so the table and the build cannot disagree."""

    try:
        text = catalog.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'^yarn\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help="the built jar or classes directory to scan (default: the Bridge's jar)",
    )
    parser.add_argument(
        "--names",
        type=Path,
        default=DEFAULT_NAMES,
        help="the pinned name table (default: bridge/host-boundary-names.json)",
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        help="a Yarn tiny v2 file to check the name table against, or to derive one from",
    )
    parser.add_argument(
        "--derive-names",
        action="store_true",
        help="write the name table from --mappings instead of scanning an artifact",
    )
    arguments = parser.parse_args(argv)

    if arguments.derive_names:
        if arguments.mappings is None:
            print("bridge artifacts: --derive-names needs --mappings", file=sys.stderr)
            return 2
        try:
            previous = (
                load_name_table(arguments.names)
                if arguments.names.exists()
                else NameTable("", "", {})
            )
            aliases = derive_name_table(arguments.mappings)
        except ArtifactError as error:
            print(f"bridge artifacts: {error}", file=sys.stderr)
            return 2
        digest = hashlib.sha256(arguments.mappings.read_bytes()).hexdigest()
        mappings_provenance: dict[str, object] = {"sha256": digest, "namespaces": list(NAMESPACES)}
        document: dict[str, object] = {
            "schema": 1,
            "yarn": pinned_yarn_version(version_catalog(arguments.names)),
            "mappings": mappings_provenance,
            "aliases": aliases,
        }
        arguments.names.parent.mkdir(parents=True, exist_ok=True)
        arguments.names.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        spellings = sum(len(names) for names in aliases.values())
        # A tiny v2 mapping file does not name the build it came from, so the version in
        # the table is the one the catalogue pins. Deriving from some other build would
        # then label it wrongly, and a table that is confidently mislabelled is worse than
        # one that is obviously stale — so say it out loud when the two disagree.
        if previous.mappings_sha256 and previous.mappings_sha256 != digest:
            print(
                f"bridge artifacts: note — this replaces a table derived from mappings "
                f"{previous.mappings_sha256}, and Yarn {document['yarn']} is the version the "
                "catalogue pins rather than one read from the file just derived"
            )
        # The mechanical markers are not derived from the mappings and are not expected
        # to be here; reporting them as unsighted would be a warning that never goes away
        # and so is a warning nobody reads.
        vacuous = sorted(
            marker
            for marker, names in aliases.items()
            if not names and marker not in MECHANICAL_MARKERS
        )
        print(
            f"bridge artifacts: wrote {arguments.names} from {arguments.mappings} "
            f"({spellings} spellings over {len(aliases)} markers)"
        )
        if vacuous:
            print(
                f"bridge artifacts: {len(vacuous)} marker(s) this build has no name for and the "
                f"artifact gate therefore cannot see: {', '.join(vacuous)}"
            )
        return 0

    try:
        table = load_name_table(arguments.names)
    except ArtifactError as error:
        print(f"bridge artifacts: {error}", file=sys.stderr)
        return 2
    if arguments.mappings is not None:
        drift = verify_against_mappings(table, arguments.mappings)
        if drift:
            print(f"bridge artifacts: {drift}", file=sys.stderr)
            return 2
    if not arguments.artifact.exists():
        print(
            f"bridge artifacts: {arguments.artifact} is not there — build it first; a gate that "
            "cannot find the artifact must not report the artifact clean",
            file=sys.stderr,
        )
        return 2
    try:
        found = violations(arguments.artifact, table)
    except ArtifactError as error:
        print(f"bridge artifacts: {error}", file=sys.stderr)
        return 2
    if found:
        for violation in found:
            print(str(violation), file=sys.stderr)
        print(
            f"bridge artifacts: {len(found)} server-state reference(s) in {arguments.artifact}",
            file=sys.stderr,
        )
        return 1
    print(
        f"Bridge artifacts: OK ({arguments.artifact} against Yarn {table.yarn or 'the table'}; no "
        "server state in the constant pools, mixins, access widener, entrypoint or packed jars)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
