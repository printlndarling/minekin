/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DASHBOARD_ADAPTER?: string;
  readonly VITE_MOCK_SCENARIO?: string;
  readonly VITE_GATEWAY_BASE_URL?: string;
  readonly VITE_MOCK_LATENCY_MS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
