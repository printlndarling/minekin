"""Compile and execute the dependency-free Bridge protocol kernel."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: One Bridge source root per Minecraft version. The protocol kernel is the part that
#: is deliberately Minecraft-free, so the same self-test runs against each root's copy
#: of it — which is the point: a root whose kernel drifted from the reviewed one fails
#: here rather than in a launcher that cannot agree with it.
BRIDGE_ROOTS = ("bridge", "bridge-1201")

KERNEL_SOURCES = (
    "protocol/FrameCodec.java",
    "protocol/HandshakeGate.java",
    "runtime/BoundedChannel.java",
    "runtime/BridgeMetrics.java",
    "runtime/BridgePhaseMachine.java",
    "runtime/CallbackBudget.java",
)

SELF_TEST = ROOT / "tools/java/BridgeProtocolSelfTest.java"


def sources_for(bridge_root: str) -> tuple[Path, ...]:
    kernel = ROOT / bridge_root / "src/main/java/org/minekin/bridge"
    return (*(kernel / relative for relative in KERNEL_SOURCES), SELF_TEST)


def main() -> None:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        raise SystemExit("a local JDK is required for the dependency-free Bridge self-test")
    for bridge_root in BRIDGE_ROOTS:
        sources = sources_for(bridge_root)
        with tempfile.TemporaryDirectory(prefix="minekin-bridge-protocol-") as temporary:
            output = Path(temporary)
            compile_result = subprocess.run(
                [javac, "--release", "17", "-d", str(output), *(str(path) for path in sources)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if compile_result.returncode != 0:
                raise SystemExit(f"{bridge_root}: {compile_result.stderr}")
            run_result = subprocess.run(
                [java, "-ea", "-cp", str(output), "BridgeProtocolSelfTest"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if run_result.returncode != 0:
                raise SystemExit(f"{bridge_root}: {run_result.stderr}")
        print(f"Minekin Bridge protocol kernel of {bridge_root}: OK (Java 17 compatibility subset)")


if __name__ == "__main__":
    main()
