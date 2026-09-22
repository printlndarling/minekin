"""Compile and execute the dependency-free Bridge protocol kernel."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/FrameCodec.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/protocol/HandshakeGate.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BoundedChannel.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BridgeMetrics.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/BridgePhaseMachine.java",
    ROOT / "bridge/src/main/java/org/minekin/bridge/runtime/CallbackBudget.java",
    ROOT / "tools/java/BridgeProtocolSelfTest.java",
)


def main() -> None:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        raise SystemExit("a local JDK is required for the dependency-free Bridge self-test")
    with tempfile.TemporaryDirectory(prefix="minekin-bridge-protocol-") as temporary:
        output = Path(temporary)
        compile_result = subprocess.run(
            [javac, "--release", "17", "-d", str(output), *(str(path) for path in SOURCES)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if compile_result.returncode != 0:
            raise SystemExit(compile_result.stderr)
        run_result = subprocess.run(
            [java, "-ea", "-cp", str(output), "BridgeProtocolSelfTest"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if run_result.returncode != 0:
            raise SystemExit(run_result.stderr)
    print("Minekin Bridge protocol kernel: OK (Java 17 compatibility subset)")


if __name__ == "__main__":
    main()
