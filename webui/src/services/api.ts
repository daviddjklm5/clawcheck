import type {
  CollectDashboard,
  MasterDataDashboard,
  ProcessDetail,
  ProcessDashboard,
  RuntimeSettingsSummary,
} from "../types/dashboard";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const error = new Error(`API request failed: ${response.status} ${response.statusText}`) as Error & {
      status?: number;
    };
    error.status = response.status;
    throw error;
  }

  return (await response.json()) as T;
}

export const dashboardApi = {
  getMasterData(): Promise<MasterDataDashboard> {
    return request<MasterDataDashboard>("/jobs/master-data");
  },
  getCollectDashboard(): Promise<CollectDashboard> {
    return request<CollectDashboard>("/documents/collect-dashboard");
  },
  getProcessDashboard(): Promise<ProcessDashboard> {
    return request<ProcessDashboard>("/documents/process-dashboard");
  },
  getProcessDocumentDetail(documentNo: string): Promise<ProcessDetail> {
    return request<ProcessDetail>(`/documents/process-dashboard/${encodeURIComponent(documentNo)}`);
  },
  getRuntimeSettings(): Promise<RuntimeSettingsSummary> {
    return request<RuntimeSettingsSummary>("/settings/runtime");
  },
};
