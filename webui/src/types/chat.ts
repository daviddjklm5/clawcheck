export interface ChatSession {
  sessionId: string;
  title: string;
  workspaceDir: string;
  modelProvider: string;
  modelName: string;
  status: string;
  createdAt: string;
  lastActiveAt: string;
}

export interface ChatMessage {
  messageId: string;
  sessionId: string;
  role: "user" | "assistant" | "system" | "tool" | string;
  content: string;
  tokenCount: number | null;
  createdAt: string;
}

export interface ChatSessionDetail {
  session: ChatSession;
  messages: ChatMessage[];
  running: boolean;
  lastEventSeq: number;
}

export interface ChatSubmitMessageResponse {
  sessionId: string;
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
  run: {
    runId: string;
    status: string;
  };
}

export interface ChatConfigSummary {
  provider: string;
  baseUrl: string;
  model: string;
  timeoutSeconds: number;
  maxOutputTokens: number;
  apiKeyEnv: string;
  apiKeyConfigured: boolean;
  codexCliExecutable: string;
  codexCliResolvedPath: string;
  workspaceDir: string;
  routerEnabled: boolean;
  approvalEnabled: boolean;
  approvalDryRunOnly: boolean;
  approvalPlanTtlSeconds: number;
}

export interface ChatHealth {
  status: string;
  codexCliAvailable: boolean;
  codexCliPath: string;
  codexCliVersion: string;
  apiKeyEnv: string;
  apiKeyConfigured: boolean;
  provider: string;
  model: string;
  routerEnabled: boolean;
  approvalEnabled: boolean;
  approvalDryRunOnly: boolean;
  approvalPlanTtlSeconds: number;
}

export interface ChatStreamEvent {
  seq: number;
  type: string;
  at: string;
  data: Record<string, unknown>;
}
