"""Generate lite Java protobufs and compile the W20 adapter without Gradle or Fabric."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOBUF_VERSION = "4.36.2"
MAVEN_BASE = "https://repo1.maven.org/maven2/com/google/protobuf"
PROTOS = tuple(sorted((ROOT / "proto" / "minekin" / "v1").glob("*.proto")))
FABRIC_STUBS = {
    "net/fabricmc/api/ClientModInitializer.java": """\
package net.fabricmc.api;
public interface ClientModInitializer { void onInitializeClient(); }
""",
    "net/fabricmc/fabric/api/client/event/lifecycle/v1/Event.java": """\
package net.fabricmc.fabric.api.client.event.lifecycle.v1;
public final class Event<T> { public void register(T listener) {} }
""",
    "net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientTickEvents.java": """\
package net.fabricmc.fabric.api.client.event.lifecycle.v1;
public final class ClientTickEvents {
    private ClientTickEvents() {}
    public static final Event<EndTick> END_CLIENT_TICK = new Event<>();
    @FunctionalInterface public interface EndTick { void onEndTick(Object client); }
}
""",
    "net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientLifecycleEvents.java": """\
package net.fabricmc.fabric.api.client.event.lifecycle.v1;
public final class ClientLifecycleEvents {
    private ClientLifecycleEvents() {}
    public static final Event<ClientStopping> CLIENT_STOPPING = new Event<>();
    @FunctionalInterface public interface ClientStopping { void onClientStopping(Object client); }
}
""",
}
ADAPTER_SOURCES = (
    ROOT / "bridge/src/main/java/org/minekin/bridge/MinekinBridgeClient.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BridgePhaseMachine.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BoundedChannel.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BridgeIpcWorker.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/HandshakeGate.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/DescriptorLoader.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/BootstrapDescriptorAdapter.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/SessionIdentityReportAdapter.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/EnvelopeGate.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/EndpointConnector.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/FrameCodec.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/FramedEnvelopeChannel.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/NioEnvelopeChannel.java",
    ROOT / "tools/java/BridgeProtoAdapterSelfTest.java",
    ROOT / "tools/java/BridgeEnvelopeTransportSelfTest.java",
    ROOT / "tools/java/BridgeIpcWorkerSelfTest.java",
    ROOT / "tools/java/BridgeSessionIdentitySelfTest.java",
)


def _protoc_classifier() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        arch = "x86_64"
    elif machine in {"aarch64", "arm64"}:
        arch = "aarch_64"
    else:
        raise SystemExit(f"unsupported protoc architecture: {machine}")
    system = platform.system()
    os_name = {"Windows": "windows", "Linux": "linux", "Darwin": "osx"}.get(system)
    if os_name is None:
        raise SystemExit(f"unsupported protoc operating system: {system}")
    return f"{os_name}-{arch}"


def _download_verified(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=30) as response:
        destination.write_bytes(response.read())
    with urllib.request.urlopen(f"{url}.sha1", timeout=30) as response:
        expected = response.read().decode("ascii").strip()
    actual = hashlib.sha1(destination.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Maven Central digest mismatch for {destination.name}")


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)


def main() -> None:
    javac = shutil.which("javac")
    if javac is None:
        raise SystemExit("javac is required for the Bridge protobuf adapter check")
    java = Path(javac).with_name("java.exe" if os.name == "nt" else "java")
    if not java.is_file():
        raise SystemExit("java must be installed beside javac")
    classifier = _protoc_classifier()
    with tempfile.TemporaryDirectory(prefix="minekin-bridge-proto-") as temporary:
        work = Path(temporary)
        generated = work / "generated"
        stubs = work / "stubs"
        classes = work / "classes"
        generated.mkdir()
        stubs.mkdir()
        classes.mkdir()
        for relative_path, source in FABRIC_STUBS.items():
            stub = stubs / relative_path
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text(source, encoding="utf-8")
        protoc = work / ("protoc.exe" if os.name == "nt" else "protoc")
        runtime = work / "protobuf-javalite.jar"
        _download_verified(
            f"{MAVEN_BASE}/protoc/{PROTOBUF_VERSION}/protoc-{PROTOBUF_VERSION}-{classifier}.exe",
            protoc,
        )
        _download_verified(
            f"{MAVEN_BASE}/protobuf-javalite/{PROTOBUF_VERSION}/"
            f"protobuf-javalite-{PROTOBUF_VERSION}.jar",
            runtime,
        )
        if os.name != "nt":
            protoc.chmod(0o700)
        _run(
            [
                str(protoc),
                f"-I{ROOT / 'proto'}",
                f"--java_out=lite:{generated}",
                *(str(path) for path in PROTOS),
            ]
        )
        generated_sources = [str(path) for path in generated.rglob("*.java")]
        stub_sources = [str(path) for path in stubs.rglob("*.java")]
        _run(
            [
                javac,
                "--release",
                "17",
                "-cp",
                str(runtime),
                "-d",
                str(classes),
                *generated_sources,
                *stub_sources,
                *(str(path) for path in ADAPTER_SOURCES),
            ]
        )
        _run(
            [
                str(java),
                "-ea",
                "-cp",
                os.pathsep.join((str(classes), str(runtime))),
                "BridgeProtoAdapterSelfTest",
            ]
        )
        _run(
            [
                str(java),
                "-ea",
                "-cp",
                os.pathsep.join((str(classes), str(runtime))),
                "BridgeEnvelopeTransportSelfTest",
            ]
        )
        _run(
            [
                str(java),
                "-ea",
                "-cp",
                os.pathsep.join((str(classes), str(runtime))),
                "BridgeIpcWorkerSelfTest",
            ]
        )
        _run(
            [
                str(java),
                "-ea",
                "-cp",
                os.pathsep.join((str(classes), str(runtime))),
                "BridgeSessionIdentitySelfTest",
            ]
        )
    print("Minekin Bridge protobuf adapter: OK (verified Maven artifacts, Java 17 subset)")


if __name__ == "__main__":
    main()
