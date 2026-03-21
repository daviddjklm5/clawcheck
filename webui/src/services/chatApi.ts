import type {
  ChatConfigSummary,
  ChatHealth,
  ChatSession,
  ChatSessionDetail,
  ChatSubmitMessageResponse,
} from "../types/chat";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

type RequestOptions = RequestInit & {
  timeoutMs?: number;
};

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const { timeoutMs = 0, signal, ...fetchInit } = init ?? {};
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const timeoutId =
    controller != null
      ? window.setTimeout(() => {
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
      },
      signal: controller?.signal ?? signal,
    });

    if (!response.ok) {
      let detail = "";
      try {
        const payload = (await response.json()) as { detail?: string };
        detail = String(payload.detail ?? "");
      } catch {
        detail = "";
      }
      throw new Error(detail || `Request failed: ${response.status} ${response.statusText}`);
    }

    return (await response.json()) as T;
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
  }
}

export const chatApi = {
  async listSessions(): Promise<ChatSession[]> {
    const response = await request<{ sessions: ChatSession[] }>("/chat/sessions");
    return response.sessions;
  },
  async createSession(payload?: { title?: string; workspaceDir?: string }): Promise<ChatSession> {
    const response = await request<{ session: ChatSession }>("/chat/sessions", {
      method: "POST",
      body: JSON.stringify({
        title: payload?.title ?? "",
        workspaceDir: payload?.workspaceDir ?? "",
      }),
    });
    return response.session;
  },
  async getSessionDetail(sessionId: string): Promise<ChatSessionDetail> {
    return request<ChatSessionDetail>(`/chat/sessions/${encodeURIComponent(sessionId)}`);
  },
  async submitMessage(sessionId: string, content: string): Promise<ChatSubmitMessageResponse> {
    return request<ChatSubmitMessageResponse>(`/chat/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
      timeoutMs: 15000,
    });
  },
  async cancelRun(sessionId: string): Promise<{ status: string }> {
    return request<{ status: string }>(`/chat/sessions/${encodeURIComponent(sessionId)}/cancel`, {
      method: "POST",
    });
  },
  async getConfigSummary(): Promise<ChatConfigSummary> {
    return request<ChatConfigSummary>("/chat/config-summary");
  },
  async getHealth(): Promise<ChatHealth> {
    return request<ChatHealth>("/chat/health");
  },
  getStreamUrl(sessionId: string, afterSeq: number): string {
    const encodedSession = encodeURIComponent(sessionId);
    return `${API_BASE_URL}/chat/sessions/${encodedSession}/stream?afterSeq=${afterSeq}`;
  },
};

