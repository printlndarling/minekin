import { expect, test } from "@playwright/test";

test("the browser starts, observes and stops an owned local game session", async ({ page }) => {
  test.skip(process.env.E2E_SESSION_START_LIVE !== "1", "Requires controlled local Minecraft, cached client and Gateway.");
  test.setTimeout(150_000);
  await page.goto("/?adapter=gateway&gateway=/gateway#session");
  await expect(page.getByTestId("session-start-confirm")).toBeEnabled();
  await page.getByTestId("session-start-confirm").check();
  await page.getByTestId("session-start-submit").click();
  await expect(page.getByTestId("session-start-result")).toContainText("已接受");
  await expect(page.getByTestId("session-start-submit")).toBeDisabled();
  await expect.poll(async () => {
    const response = await page.request.get("/gateway/api/v1/dashboard/snapshot");
    const body = await response.json();
    return body.runtimeState.value === "running" && body.world.value?.joined?.value === true && body.serverLink.value === "connected";
  }, { timeout: 100_000, intervals: [1000] }).toBe(true);
  // The wire poll above reads the Gateway directly; the page itself refreshes on its own
  // cadence. The screenshot is the artifact, so wait for the page to display the joined
  // reading before capturing it — otherwise the shot can lag the run it claims to show.
  await expect(page.getByTestId("context-where")).toContainText("已入服", { timeout: 15_000 });
  await page.screenshot({ path: "test-results/session-start-local.png", fullPage: true });
  await page.getByTestId("panel-session-control").getByRole("checkbox").check();
  await page.getByTestId("session-stop-submit").click();
  await expect.poll(async () => {
    const response = await page.request.get("/gateway/api/v1/dashboard/session/job");
    const body = await response.json();
    return body.job?.phase;
  }, { timeout: 30_000, intervals: [500] }).toBe("ended");
  const result = await (await page.request.get("/gateway/api/v1/dashboard/session/job")).json();
  expect(result.job.outcome).toBe("STOPPED_ON_REQUEST");
  expect(result.job.inputReleaseFailed).toBe(false);
});
