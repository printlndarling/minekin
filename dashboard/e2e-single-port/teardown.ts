import type { FullConfig } from "@playwright/test";

export default async function teardown(config: FullConfig): Promise<void> {
  const response = await fetch(`${config.metadata.smokeOrigin}/__smoke_shutdown`, {
    method: "POST", headers: { "X-Smoke-Token": config.metadata.smokeShutdownToken },
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error("isolated browser fixture did not accept shutdown");
  // Wait for its owned Python process to close SQLite and clean its TemporaryDirectory.
  await new Promise((resolve) => setTimeout(resolve, 1000));
}
