import type {
  CollectDashboard,
  MasterDataDashboard,
  ProcessApprovalRequest,
  ProcessApprovalResponse,
  ProcessDetail,
  ProcessDashboard,
  RuntimeSettingsSummary,
} from "../types/dashboard";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: init?.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
    body: init?.body,
  });

  if (!response.ok) {
    let detailMessage = "";
    try {
      const errorPayload = (await response.json()) as { detail?: string };
      detailMessage = String(errorPayload.detail ?? "").trim();
    } catch {
      detailMessage = "";
    }
    const error = new Error(`API request failed: ${response.status} ${response.statusText}`) as Error & {
      status?: number;
    };
    error.status = response.status;
    if (detailMessage) {
      error.message = detailMessage;
    }
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
  approveProcessDocument(documentNo: string, payload: ProcessApprovalRequest): Promise<ProcessApprovalResponse> {
    return request<ProcessApprovalResponse>(
      `/documents/process-dashboard/${encodeURIComponent(documentNo)}/approval`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  getRuntimeSettings(): Promise<RuntimeSettingsSummary> {
    return request<RuntimeSettingsSummary>("/settings/runtime");
  },
};
