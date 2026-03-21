import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import { chatApi } from "../services/chatApi";
import type {
  ChatConfigSummary,
  ChatHealth,
  ChatMessage,
  ChatSession,
  ChatStreamEvent,
} from "../types/chat";

const STREAM_EVENT_TYPES = [
  "status",
  "message_created",
  "token",
  "tool",
  "event",
  "error",
  "done",
  "session_created",
] as const;

function roleLabel(role: string): string {
  if (role === "assistant") {
    return "Assistant";
  }
  if (role === "user") {
    return "You";
  }
  if (role === "system") {
    return "System";
  }
  return role || "Message";
}

function getSessionTitle(session: ChatSession): string {
  return session.title || `Session ${session.sessionId.slice(0, 8)}`;
}

function getRunStatusLabel(status: string): string {
  if (status === "routing") {
    return "意图路由中";
  }
  if (status === "running_tool") {
    return "调用正式工具中";
  }
  if (status === "clarifying") {
    return "追问补齐中";
  }
  if (status === "templated") {
    return "模板直答中";
  }
  if (status === "composing") {
    return "组织答案中";
  }
  if (status === "cancel_requested") {
    return "取消中";
  }
  return status || "-";
}

export function ChatWorkspacePage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [runStatus, setRunStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputText, setInputText] = useState("");
  const [configSummary, setConfigSummary] = useState<ChatConfigSummary | null>(null);
  const [health, setHealth] = useState<ChatHealth | null>(null);
  const [activitySummary, setActivitySummary] = useState("");
  const lastSeqRef = useRef<number>(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  const selectedSession = useMemo(
    () => sessions.find((item) => item.sessionId === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  );

  const isRunning =
    runStatus === "queued" ||
    runStatus === "running" ||
    runStatus === "cancel_requested";

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      try {
        setLoading(true);
        setError(null);
        const [sessionRows, config, healthPayload] = await Promise.all([
          chatApi.listSessions(),
          chatApi.getConfigSummary(),
          chatApi.getHealth(),
        ]);
        if (!active) {
          return;
        }

        setConfigSummary(config);
        setHealth(healthPayload);
        let currentSessions = sessionRows;
        if (currentSessions.length === 0) {
          const created = await chatApi.createSession();
          if (!active) {
            return;
          }
          currentSessions = [created];
        }
        setSessions(currentSessions);
        setSelectedSessionId((prev) => prev || currentSessions[0].sessionId);
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "加载对话工作台失败");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
      setMessages([]);
      setRunStatus("");
      setActivitySummary("");
      return;
    }
    let active = true;
    async function loadDetail() {
      try {
        const detail = await chatApi.getSessionDetail(selectedSessionId);
        if (!active) {
          return;
        }
        setMessages(detail.messages);
        setRunStatus(detail.running ? "running" : detail.session.status);
        setActivitySummary("");
        lastSeqRef.current = 0;
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "加载会话详情失败");
        }
      }
    }
    void loadDetail();
    return () => {
      active = false;
    };
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) {
      return;
    }
    eventSourceRef.current?.close();

    const eventSource = new EventSource(chatApi.getStreamUrl(selectedSessionId, lastSeqRef.current));
    eventSourceRef.current = eventSource;

    const onEvent = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as ChatStreamEvent;
        if (payload.seq <= lastSeqRef.current) {
          return;
        }
        lastSeqRef.current = payload.seq;
        const eventType = payload.type;
        if (eventType === "message_created") {
          const message = payload.data.message as ChatMessage | undefined;
          if (!message) {
            return;
          }
          setMessages((current) => {
            if (current.some((item) => item.messageId === message.messageId)) {
              return current;
            }
            return [...current, message];
          });
          return;
        }
        if (eventType === "token") {
          const messageId = String(payload.data.messageId ?? "");
          const delta = String(payload.data.delta ?? "");
          if (!messageId || !delta) {
            return;
          }
          setMessages((current) =>
            current.map((item) =>
              item.messageId === messageId
                ? { ...item, content: `${item.content}${delta}` }
                : item,
            ),
          );
          return;
        }
        if (eventType === "status") {
          const nextStatus = String(payload.data.status ?? "");
          setRunStatus(nextStatus);
          setActivitySummary(getRunStatusLabel(nextStatus));
          return;
        }
        if (eventType === "tool" || eventType === "event") {
          const summary = String(payload.data.summary ?? "");
          if (summary) {
            setActivitySummary(summary);
          }
          return;
        }
        if (eventType === "done") {
          setRunStatus(String(payload.data.status ?? ""));
          setActivitySummary("本轮回答已完成");
          return;
        }
        if (eventType === "error") {
          const message = String(payload.data.message ?? "");
          if (message) {
            setError(message);
          }
        }
      } catch {
        // Ignore malformed SSE payloads.
      }
    };

    for (const eventType of STREAM_EVENT_TYPES) {
      eventSource.addEventListener(eventType, onEvent as EventListener);
    }
    eventSource.onerror = () => {
      // Keep existing UI state; browser will retry SSE automatically.
    };

    return () => {
      for (const eventType of STREAM_EVENT_TYPES) {
        eventSource.removeEventListener(eventType, onEvent as EventListener);
      }
      eventSource.close();
    };
  }, [selectedSessionId]);

  async function createNewSession() {
    try {
      const created = await chatApi.createSession();
      setSessions((current) => [created, ...current]);
      setSelectedSessionId(created.sessionId);
      setInputText("");
      setError(null);
      setActivitySummary("");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "创建会话失败");
    }
  }

  async function sendMessage() {
    const text = inputText.trim();
    if (!selectedSessionId || !text) {
      return;
    }
    try {
      setSending(true);
      setError(null);
      const response = await chatApi.submitMessage(selectedSessionId, text);
      setMessages((current) => {
        const hasUser = current.some((item) => item.messageId === response.userMessage.messageId);
        const hasAssistant = current.some((item) => item.messageId === response.assistantMessage.messageId);
        const next = [...current];
        if (!hasUser) {
          next.push(response.userMessage);
        }
        if (!hasAssistant) {
          next.push(response.assistantMessage);
        }
        return next;
      });
      setRunStatus(response.run.status);
      setInputText("");
      setActivitySummary(getRunStatusLabel(response.run.status));
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "发送消息失败");
    } finally {
      setSending(false);
    }
  }

  async function cancelRun() {
    if (!selectedSessionId) {
      return;
    }
    try {
      await chatApi.cancelRun(selectedSessionId);
      setRunStatus("cancel_requested");
      setActivitySummary(getRunStatusLabel("cancel_requested"));
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "取消执行失败");
    }
  }

  return (
    <Stack spacing={2.5}>
      <Typography variant="body1">
        对话工作台默认采用 Web 入口。后端使用 Codex CLI 执行，模型服务通过 API Key 配置。
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <Paper
        elevation={0}
        sx={{
          p: 1.5,
          border: "1px solid",
          borderColor: "divider",
          backgroundColor: "rgba(255,255,255,0.72)",
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
          <Typography variant="body2">
            Model: {configSummary?.provider ?? "-"} / {configSummary?.model ?? "-"}
          </Typography>
          <Typography variant="body2">
            Key: {configSummary?.apiKeyConfigured ? "Configured" : "Missing"} ({configSummary?.apiKeyEnv ?? "-"})
          </Typography>
          <Typography variant="body2">
            Codex CLI: {health?.codexCliAvailable ? "Available" : "Unavailable"}
          </Typography>
          <Typography variant="body2">Router: {configSummary?.routerEnabled ? "Enabled" : "Disabled"}</Typography>
          <Typography variant="body2">Run status: {getRunStatusLabel(runStatus)}</Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Activity: {activitySummary || "-"}
        </Typography>
      </Paper>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "280px 1fr" },
          gap: 2,
          minHeight: 640,
        }}
      >
        <Paper
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 1.25 }}>
            <Typography variant="subtitle2">会话</Typography>
            <Button size="small" variant="outlined" onClick={createNewSession}>
              新建
            </Button>
          </Stack>
          <Divider />
          <List dense sx={{ overflowY: "auto", flex: 1 }}>
            {sessions.map((session) => (
              <ListItemButton
                key={session.sessionId}
                selected={session.sessionId === selectedSessionId}
                onClick={() => setSelectedSessionId(session.sessionId)}
              >
                <ListItemText
                  primary={getSessionTitle(session)}
                  secondary={`${session.status} · ${session.lastActiveAt}`}
                />
              </ListItemButton>
            ))}
          </List>
        </Paper>

        <Paper
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <Box sx={{ p: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
            <Typography variant="subtitle2">{selectedSession ? getSessionTitle(selectedSession) : "-"}</Typography>
            <Typography variant="caption" color="text.secondary">
              {selectedSession?.workspaceDir || configSummary?.workspaceDir || "-"}
            </Typography>
          </Box>

          <Box sx={{ p: 1.5, overflowY: "auto", flex: 1, display: "grid", rowGap: 1.25 }}>
            {loading ? (
              <Stack direction="row" spacing={1} alignItems="center">
                <CircularProgress size={16} />
                <Typography variant="body2">加载中...</Typography>
              </Stack>
            ) : null}
            {!loading && messages.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                该会话暂无消息，输入后按 Enter 发送。
              </Typography>
            ) : null}
            {messages.map((message) => (
              <Box
                key={message.messageId}
                sx={{
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 1,
                  p: 1.25,
                  backgroundColor: message.role === "user" ? "rgba(236, 252, 203, 0.45)" : "rgba(255,255,255,0.9)",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {roleLabel(message.role)} · {message.createdAt}
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.75, whiteSpace: "pre-wrap" }}>
                  {message.content || (message.role === "assistant" && isRunning ? "..." : "-")}
                </Typography>
              </Box>
            ))}
          </Box>

          <Divider />
          <Stack spacing={1.25} sx={{ p: 1.5 }}>
            <TextField
              multiline
              minRows={3}
              maxRows={10}
              value={inputText}
              disabled={!selectedSessionId || sending}
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              placeholder="输入问题后按 Enter 发送，Shift+Enter 换行"
            />
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                disableElevation
                onClick={() => void sendMessage()}
                disabled={!selectedSessionId || sending || !inputText.trim()}
              >
                发送
              </Button>
              <Button variant="outlined" onClick={() => void cancelRun()} disabled={!selectedSessionId || !isRunning}>
                停止
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Box>
    </Stack>
  );
}
