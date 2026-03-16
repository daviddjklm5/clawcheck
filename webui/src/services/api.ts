import type {
  CollectDetail,
  CollectRunRequest,
  CollectRunSummary,
  CollectWorkbench,
  MasterDataDashboard,
  ProcessAnalysisDashboard,
  ProcessAuditRunRequest,
  ProcessAuditRunSummary,
  ProcessApprovalRequest,
  ProcessApprovalResponse,
  ProcessDetail,
  ProcessTodoSyncRequest,
  ProcessTodoSyncResponse,
  ProcessWorkbench,
  RuntimeSettingsSummary,
} from "../types/dashboard";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");

type RequestOptions = RequestInit & {
  timeoutMs?: number;
  timeoutMessage?: string;
};

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const { timeoutMs = 0, timeoutMessage, headers, signal, ...fetchInit } = init ?? {};
  const controller = timeoutMs > 0 ? new AbortController() : null;
  let didTimeout = false;
  let detachAbortForwarder: (() => void) | null = null;

  if (controller && signal) {
    const forwardAbort = () => controller.abort();
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", forwardAbort, { once: true });
      detachAbortForwarder = () => signal.removeEventListener("abort", forwardAbort);
    }
  }

  const timeoutId =
    controller !== null
      ? window.setTimeout(() => {
          didTimeout = true;
          controller.abort();
        }, timeoutMs)
      : null;

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchInit,
      method: fetchInit.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(fetchInit.body ? { "Content-Type": "application/json" } : {}),
        ...(headers ?? {}),
      },
      signal: controller?.signal ?? signal,
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
  } catch (error) {
    if (didTimeout) {
      throw new Error(timeoutMessage ?? `API request timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
    detachAbortForwarder?.();
  }
}

export const dashboardApi = {
  getMasterData(): Promise<MasterDataDashboard> {
    return request<MasterDataDashboard>("/jobs/master-data");
  },
  getCollectWorkbench(): Promise<CollectWorkbench> {
    return request<CollectWorkbench>("/documents/collect-workbench");
  },
  getCollectDocumentDetail(documentNo: string): Promise<CollectDetail> {
    return request<CollectDetail>(`/documents/collect-workbench/${encodeURIComponent(documentNo)}`);
  },
  startCollectTask(payload: CollectRunRequest): Promise<CollectRunSummary> {
    return request<CollectRunSummary>("/documents/collect-workbench/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getProcessWorkbench(): Promise<ProcessWorkbench> {
    return request<ProcessWorkbench>("/documents/process-workbench");
  },
  getProcessAnalysisDashboard(): Promise<ProcessAnalysisDashboard> {
    return request<ProcessAnalysisDashboard>("/documents/process-analysis");
  },
  getProcessDocumentDetail(documentNo: string): Promise<ProcessDetail> {
    return request<ProcessDetail>(`/documents/process-workbench/${encodeURIComponent(documentNo)}`);
  },
  approveProcessDocument(documentNo: string, payload: ProcessApprovalRequest): Promise<ProcessApprovalResponse> {
    return request<ProcessApprovalResponse>(
      `/documents/process-workbench/${encodeURIComponent(documentNo)}/approval`,
      {
        method: "POST",
        body: JSON.stringify(payload),
        timeoutMs: 120_000,
        timeoutMessage:
          "审批请求超过 120 秒未返回，后端可能卡在 EHR 窗口。请检查弹出的 EHR 浏览器，并查看 automation/logs 下最新 approval_*.json。",
      },
    );
  },
  syncProcessTodoStatus(payload: ProcessTodoSyncRequest = { dryRun: false }): Promise<ProcessTodoSyncResponse> {
    return request<ProcessTodoSyncResponse>("/documents/process-workbench/todo-sync", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 180_000,
      timeoutMessage:
        "待办状态同步超过 180 秒未返回，后端可能卡在 EHR 待办页。请检查弹出的 EHR 浏览器，并查看 automation/logs 下最新 run_*.log。",
    });
  },
  startProcessAuditTask(payload: ProcessAuditRunRequest): Promise<ProcessAuditRunSummary> {
    return request<ProcessAuditRunSummary>("/documents/process-workbench/audit", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getRuntimeSettings(): Promise<RuntimeSettingsSummary> {
    return request<RuntimeSettingsSummary>("/settings/runtime");
  },
};
