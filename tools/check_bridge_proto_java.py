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
    # The client parameter is typed, not `Object`. The real Fabric events carry a
    # MinecraftClient, and a stub that widened it to Object would accept a
    # listener that cannot actually be registered — the compile this gate exists
    # to perform would pass while the mod failed to load.
    "net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientTickEvents.java": """\
package net.fabricmc.fabric.api.client.event.lifecycle.v1;
import net.minecraft.client.MinecraftClient;
public final class ClientTickEvents {
    private ClientTickEvents() {}
    public static final Event<EndTick> END_CLIENT_TICK = new Event<>();
    @FunctionalInterface public interface EndTick { void onEndTick(MinecraftClient client); }
}
""",
    "net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientLifecycleEvents.java": """\
package net.fabricmc.fabric.api.client.event.lifecycle.v1;
import net.minecraft.client.MinecraftClient;
public final class ClientLifecycleEvents {
    private ClientLifecycleEvents() {}
    public static final Event<ClientStopping> CLIENT_STOPPING = new Event<>();
    @FunctionalInterface public interface ClientStopping {
        void onClientStopping(MinecraftClient client);
    }
}
""",
    "org/minekin/bridge/runtime/ClientAdmissionController.java": """\
package org.minekin.bridge.runtime;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.InitialObservation;
import java.util.function.Predicate;
import net.minecraft.client.MinecraftClient;
public final class ClientAdmissionController {
    public ClientAdmissionController(
            BridgePhaseMachine phases,
            Predicate<ConnectionLifecycle> lifecycleSink,
            Predicate<InitialObservation> observationSink) {}
    public void handle(MinecraftClient client, BridgeIpcWorker.ClientMessage message) {}
    public void safeStop(MinecraftClient client) {}
    public void collectSnapshotWhenPlayable(MinecraftClient client) {}
    public void reportPendingConnectFailure() {}
    public void loginNegotiating() {}
    public void playInit() {}
    public void joinSeen() {}
    public void loginFailed() {}
    public void playEnded() {}
}
""",
    # The phases only the client can observe. Stubbed with the real listener
    # signatures from fabric-networking-api-v1 4.4.0+db5e668204, because a stub
    # that widened them would accept a listener the real dispatcher cannot hold.
    "net/fabricmc/fabric/api/client/networking/v1/ClientLoginConnectionEvents.java": """\
package net.fabricmc.fabric.api.client.networking.v1;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.Event;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientLoginNetworkHandler;
public final class ClientLoginConnectionEvents {
    private ClientLoginConnectionEvents() {}
    public static final Event<Init> INIT = new Event<>();
    public static final Event<Disconnect> DISCONNECT = new Event<>();
    @FunctionalInterface public interface Init {
        void onLoginStart(ClientLoginNetworkHandler handler, MinecraftClient client);
    }
    @FunctionalInterface public interface Disconnect {
        void onLoginDisconnect(ClientLoginNetworkHandler handler, MinecraftClient client);
    }
}
""",
    "net/fabricmc/fabric/api/client/networking/v1/ClientPlayConnectionEvents.java": """\
package net.fabricmc.fabric.api.client.networking.v1;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.Event;
import net.fabricmc.fabric.api.networking.v1.PacketSender;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayNetworkHandler;
public final class ClientPlayConnectionEvents {
    private ClientPlayConnectionEvents() {}
    public static final Event<Init> INIT = new Event<>();
    public static final Event<Join> JOIN = new Event<>();
    public static final Event<Disconnect> DISCONNECT = new Event<>();
    @FunctionalInterface public interface Init {
        void onPlayInit(ClientPlayNetworkHandler handler, MinecraftClient client);
    }
    @FunctionalInterface public interface Join {
        void onPlayReady(
                ClientPlayNetworkHandler handler, PacketSender sender, MinecraftClient client);
    }
    @FunctionalInterface public interface Disconnect {
        void onPlayDisconnect(ClientPlayNetworkHandler handler, MinecraftClient client);
    }
}
""",
    "net/fabricmc/fabric/api/networking/v1/PacketSender.java": """\
package net.fabricmc.fabric.api.networking.v1;
public interface PacketSender {}
""",
    "net/minecraft/client/network/ClientLoginNetworkHandler.java": """\
package net.minecraft.client.network;
public class ClientLoginNetworkHandler {}
""",
    # The one method the Bridge calls to turn a view, with the signature read from
    # the compiled client rather than guessed: it takes the cursor delta the mouse
    # would have handed it, which is what keeps a look the client's own.
    "net/minecraft/client/network/ClientPlayerEntity.java": """\
package net.minecraft.client.network;
public class ClientPlayerEntity {
    public void changeLookDirection(double cursorDeltaX, double cursorDeltaY) {}
}
""",
    "net/minecraft/client/network/ClientPlayNetworkHandler.java": """\
package net.minecraft.client.network;
public class ClientPlayNetworkHandler {}
""",
    "org/slf4j/Logger.java": """\
package org.slf4j;
public interface Logger {
    default void info(String message, Object... values) {}
    default void warn(String message, Object... values) {}
    default void error(String message, Object... values) {}
}
""",
    "org/slf4j/LoggerFactory.java": """\
package org.slf4j;
public final class LoggerFactory {
    private static final Logger LOGGER = new Logger() {};
    private LoggerFactory() {}
    public static Logger getLogger(String name) { return LOGGER; }
}
""",
    "net/minecraft/client/option/KeyBinding.java": """\
package net.minecraft.client.option;
public class KeyBinding { public void setPressed(boolean pressed) {} }
""",
    "net/minecraft/client/option/GameOptions.java": """\
package net.minecraft.client.option;
public class GameOptions {
    public final KeyBinding forwardKey = new KeyBinding();
    public final KeyBinding backKey = new KeyBinding();
    public final KeyBinding leftKey = new KeyBinding();
    public final KeyBinding rightKey = new KeyBinding();
    public final KeyBinding jumpKey = new KeyBinding();
    public final KeyBinding sneakKey = new KeyBinding();
    public final KeyBinding useKey = new KeyBinding();
}
""",
    # The screen field is typed rather than `Object`, and there is no way to read
    # anything out of a Screen: the Bridge is allowed to know a screen's *class*
    # (a product event may not carry a screen's text) and nothing else about it.
    "net/minecraft/client/gui/screen/Screen.java": """\
package net.minecraft.client.gui.screen;
public class Screen {}
""",
    # The screens the Bridge can name, as subclasses of the one above: naming them
    # is only possible if they are distinguishable by type, which is the point.
    "net/minecraft/client/gui/screen/DeathScreen.java": """\
package net.minecraft.client.gui.screen;
public class DeathScreen extends Screen {}
""",
    "net/minecraft/client/gui/screen/GameMenuScreen.java": """\
package net.minecraft.client.gui.screen;
public class GameMenuScreen extends Screen {}
""",
    "net/minecraft/client/gui/screen/TitleScreen.java": """\
package net.minecraft.client.gui.screen;
public class TitleScreen extends Screen {}
""",
    "net/minecraft/client/gui/screen/multiplayer/ConnectScreen.java": """\
package net.minecraft.client.gui.screen.multiplayer;
import net.minecraft.client.gui.screen.Screen;
public class ConnectScreen extends Screen {}
""",
    # Compile-only Minecraft facade. Its always-present instance and inline
    # execution do not claim to test real client-thread behaviour.
    "net/minecraft/client/MinecraftClient.java": """\
package net.minecraft.client;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.option.GameOptions;
public class MinecraftClient {
    public final GameOptions options = new GameOptions();
    public Screen currentScreen;
    public ClientPlayerEntity player;
    public static MinecraftClient getInstance() { return new MinecraftClient(); }
    public void execute(Runnable operation) { operation.run(); }
    public boolean isOnThread() { return true; }
}
""",
}
ADAPTER_SOURCES = (
    ROOT / "bridge/src/main/java/org/minekin/bridge/MinekinBridgeClient.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BridgePhaseMachine.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BoundedChannel.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BridgeIpcWorker.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/BridgeInputController.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/InputOwnership.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/InputWatchdog.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/KeySink.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/InputBinding.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/VanillaKeySink.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/ViewSink.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/input/VanillaViewSink.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/HandshakeGate.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/AdmissionCommandGate.java",
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
    ROOT / "tools/java/AdmissionCommandGateSelfTest.java",
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
        _run(
            [
                str(java),
                "-ea",
                "-cp",
                os.pathsep.join((str(classes), str(runtime))),
                "AdmissionCommandGateSelfTest",
            ]
        )
    print("Minekin Bridge protobuf adapter: OK (verified Maven artifacts, Java 17 subset)")


if __name__ == "__main__":
    main()
