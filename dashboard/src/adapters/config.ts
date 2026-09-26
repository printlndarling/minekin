import type { KinReadAdapter } from "../domain/adapter";
import { isMockScenarioId, type MockScenarioId } from "../fixtures/mockFixtures";
import { createMockAdapter } from "./mockAdapter";
import { createGatewayAdapter } from "./gatewayAdapter";

export const DEFAULT_SCENARIO: MockScenarioId = "healthy_run_07";
export const DEFAULT_TIMEOUT_MS = 3_000;
export const DEFAULT_LATENCY_MS = 120;

export interface DashboardEnv {
  readonly adapter: string;
  readonly scenario: string;
  readonly gatewayBaseUrl: string;
  readonly latencyMs: string;
}

export interface DashboardConfig {
  readonly adapter: "mock" | "gateway";
  readonly scenario: MockScenarioId;
  readonly gatewayBaseUrl: string | null;
  readonly latencyMs: number;
}

const ENV_DEFAULTS: DashboardEnv = {
  adapter: "mock",
  scenario: DEFAULT_SCENARIO,
  gatewayBaseUrl: "",
  latencyMs: String(DEFAULT_LATENCY_MS),
};

function pick(value: string | undefined, fallback: string): string {
  return value === undefined || value === "" ? fallback : value;
}

/** Pure so the adapter switch is unit-testable without a DOM. */
export function parseDashboardConfig(search: string, env: Partial<DashboardEnv> = {}): DashboardConfig {
  const merged: DashboardEnv = {
    adapter: pick(env.adapter, ENV_DEFAULTS.adapter),
    scenario: pick(env.scenario, ENV_DEFAULTS.scenario),
    gatewayBaseUrl: pick(env.gatewayBaseUrl, ENV_DEFAULTS.gatewayBaseUrl),
    latencyMs: pick(env.latencyMs, ENV_DEFAULTS.latencyMs),
  };
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const adapterRaw = params.get("adapter") ?? merged.adapter;
  const adapter = adapterRaw === "gateway" ? "gateway" : "mock";
  const scenarioRaw = params.get("scenario") ?? merged.scenario;
  const scenario = isMockScenarioId(scenarioRaw) ? scenarioRaw : DEFAULT_SCENARIO;
  const gatewayBaseUrl = (params.get("gateway") ?? merged.gatewayBaseUrl).trim();
  const latencyRaw = Number(params.get("latency") ?? merged.latencyMs);
  return {
    adapter,
    scenario,
    gatewayBaseUrl: gatewayBaseUrl === "" ? null : gatewayBaseUrl.replace(/\/+$/, ""),
    latencyMs: Number.isFinite(latencyRaw) && latencyRaw >= 0 ? latencyRaw : DEFAULT_LATENCY_MS,
  };
}

function runtimeEnv(): DashboardEnv {
  return {
    adapter: import.meta.env.VITE_DASHBOARD_ADAPTER ?? "",
    scenario: import.meta.env.VITE_MOCK_SCENARIO ?? "",
    gatewayBaseUrl: import.meta.env.VITE_GATEWAY_BASE_URL ?? "",
    latencyMs: import.meta.env.VITE_MOCK_LATENCY_MS ?? "",
  };
}

export function readDashboardConfig(search: string): DashboardConfig {
  return parseDashboardConfig(search, runtimeEnv());
}

export function createAdapter(config: DashboardConfig, nowScenario?: MockScenarioId): KinReadAdapter {
  if (config.adapter === "gateway") {
    return createGatewayAdapter(
      config.gatewayBaseUrl === null ? null : { baseUrl: config.gatewayBaseUrl, timeoutMs: DEFAULT_TIMEOUT_MS },
    );
  }
  return createMockAdapter(nowScenario ?? config.scenario, config.latencyMs);
}
