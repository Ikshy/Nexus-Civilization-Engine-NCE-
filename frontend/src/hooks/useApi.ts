/**
 * NCE API client — axios-based with SWR for reactive state.
 */
import axios from "axios";
import useSWR from "swr";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: `${BASE}/api/v1` });

const fetcher = (url: string) => api.get(url).then((r) => r.data);

// ---- Simulation control ---------------------------------------------------

export const startSimulation = (config: Record<string, unknown>) =>
  api.post("/simulation/start", config).then((r) => r.data);

export const stopSimulation = () =>
  api.post("/simulation/stop").then((r) => r.data);

export const pauseSimulation = () =>
  api.post("/simulation/pause").then((r) => r.data);

export const resumeSimulation = () =>
  api.post("/simulation/resume").then((r) => r.data);

export const stepSimulation = (n: number = 1) =>
  api.post(`/simulation/step?n=${n}`).then((r) => r.data);

export const updateParameters = (params: Record<string, unknown>) =>
  api.patch("/simulation/parameters", params).then((r) => r.data);

// ---- Scenarios ------------------------------------------------------------

export const injectScenario = (data: {
  scenario_type: string;
  severity: number;
  faction_a?: string;
  faction_b?: string;
}) => api.post("/scenarios/inject", data).then((r) => r.data);

// ---- Agents ---------------------------------------------------------------

export const modifyAgent = (agentId: string, mods: Record<string, unknown>) =>
  api.patch(`/agents/${agentId}`, { agent_id: agentId, modifications: mods }).then((r) => r.data);

// ---- Hooks ----------------------------------------------------------------

export const useSimStatus = () =>
  useSWR("/simulation/status", fetcher, { refreshInterval: 1000 });

export const useSimState = () =>
  useSWR("/simulation/state", fetcher, { refreshInterval: 2000 });

export const useAgents = (params?: string) =>
  useSWR(`/agents/${params || ""}`, fetcher, { refreshInterval: 2000 });

export const useAgent = (agentId: string | null) =>
  useSWR(agentId ? `/agents/${agentId}` : null, fetcher);

export const useAnalytics = () =>
  useSWR("/analytics/summary", fetcher, { refreshInterval: 3000 });

export const useLeaders = () =>
  useSWR("/analytics/leaders", fetcher, { refreshInterval: 5000 });

export const useClusters = () =>
  useSWR("/analytics/clusters", fetcher, { refreshInterval: 5000 });

export const useConflictZones = () =>
  useSWR("/analytics/conflict-zones", fetcher, { refreshInterval: 3000 });

export const useInformation = () =>
  useSWR("/analytics/information", fetcher, { refreshInterval: 3000 });

export const useHeatmap = (resource: string) =>
  useSWR(`/world/heatmap/${resource}`, fetcher, { refreshInterval: 3000 });

export const useWorldState = () =>
  useSWR("/world/state", fetcher, { refreshInterval: 2000 });

export const useRecentEvents = (limit = 50) =>
  useSWR(`/events/recent?limit=${limit}`, fetcher, { refreshInterval: 1500 });

export const useScenarios = () =>
  useSWR("/scenarios/status", fetcher, { refreshInterval: 2000 });

export const useAvailableScenarios = () =>
  useSWR("/scenarios/available", fetcher);

export const useMetricTrend = (metric: string, lastN = 50) =>
  useSWR(`/analytics/trends/${metric}?last_n=${lastN}`, fetcher, { refreshInterval: 5000 });
