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

const DESKTOP_WORKSPACE_HEIGHT = "clamp(620px, calc(100vh - 290px), 820px)";
const MESSAGE_STICKY_THRESHOLD = 64;

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
  if (status === "approval_preparing") {
    return "生成审批计划中";
  }
  if (status === "approval_confirmation_required") {
    return "等待审批确认";
  }
  if (status === "approval_dry_running") {
    return "审批连通性验证中";
  }
  if (status === "approval_submitting") {
    return "审批提交中";
  }
  if (status === "cancel_requested") {
    return "取消中";
  }
  if (status === "succeeded") {
    return "已完成";
  }
  if (status === "failed") {
    return "执行失败";
  }
  return status || "-";
}

function shouldStickToBottom(node: HTMLDivElement): boolean {
  return node.scrollHeight - node.scrollTop - node.clientHeight <= MESSAGE_STICKY_THRESHOLD;
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
  const [streamAfterSeq, setStreamAfterSeq] = useState<number | null>(null);
  const lastSeqRef = useRef<number>(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const messagesViewportRef = useRef<HTMLDivElement | null>(null);
  const shouldStickToBottomRef = useRef(true);

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
        const [sessionRows, config] = await Promise.all([
          chatApi.listSessions(),
          chatApi.getConfigSummary(),
        ]);
        if (!active) {
          return;
        }

        setConfigSummary(config);
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
    let active = true;

    async function loadHealth() {
      try {
        const healthPayload = await chatApi.getHealth();
        if (!active) {
          return;
        }
        setHealth(healthPayload);
      } catch {
        if (!active) {
          return;
        }
        setHealth(null);
      }
    }

    void loadHealth();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    shouldStickToBottomRef.current = true;
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setMessages([]);
      setRunStatus("");
      setActivitySummary("");
      setStreamAfterSeq(null);
      lastSeqRef.current = 0;
      return;
    }

    let active = true;
    setStreamAfterSeq(null);
    lastSeqRef.current = 0;

    async function loadDetail() {
      try {
        const detail = await chatApi.getSessionDetail(selectedSessionId);
        if (!active) {
          return;
        }
        setMessages(detail.messages);
        setRunStatus(detail.running ? "running" : detail.session.status);
        setActivitySummary("");
        lastSeqRef.current = detail.lastEventSeq;
        setStreamAfterSeq(detail.lastEventSeq);
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
    if (!selectedSessionId || streamAfterSeq === null) {
      return;
    }

    eventSourceRef.current?.close();

    const eventSource = new EventSource(chatApi.getStreamUrl(selectedSessionId, streamAfterSeq));
    eventSourceRef.current = eventSource;

    const onEvent = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as ChatStreamEvent;
        if (payload.seq <= lastSeqRef.current) {
          return;
        }
        lastSeqRef.current = payload.seq;

        if (payload.type === "message_created") {
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

        if (payload.type === "token") {
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

        if (payload.type === "status") {
          const nextStatus = String(payload.data.status ?? "");
          setRunStatus(nextStatus);
          setActivitySummary(getRunStatusLabel(nextStatus));
          return;
        }

        if (payload.type === "tool" || payload.type === "event") {
          const summary = String(payload.data.summary ?? "");
          if (summary) {
            setActivitySummary(summary);
          }
          return;
        }

        if (payload.type === "done") {
          const assistantMessageId = String(payload.data.assistantMessageId ?? "");
          const finalMessage = String(payload.data.message ?? "");
          if (assistantMessageId && finalMessage) {
            setMessages((current) =>
              current.map((item) =>
                item.messageId === assistantMessageId
                  ? { ...item, content: finalMessage }
                  : item,
              ),
            );
          }
          setRunStatus(String(payload.data.status ?? ""));
          setActivitySummary("本轮回答已完成");
          return;
        }

        if (payload.type === "__legacy_done__") {
          setRunStatus(String(payload.data.status ?? ""));
          setActivitySummary("本轮回答已完成");
          return;
        }

        if (payload.type === "error") {
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
      eventSourceRef.current = null;
    };
  }, [selectedSessionId, streamAfterSeq]);

  useEffect(() => {
    const node = messagesViewportRef.current;
    if (!node || !shouldStickToBottomRef.current) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [messages, loading, selectedSessionId]);

  async function createNewSession() {
    try {
      const created = await chatApi.createSession();
      shouldStickToBottomRef.current = true;
      setSessions((current) => [created, ...current]);
      setSelectedSessionId(created.sessionId);
      setMessages([]);
      setRunStatus("");
      setStreamAfterSeq(null);
      lastSeqRef.current = 0;
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
      shouldStickToBottomRef.current = true;
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
        对话工作台默认走 Web 对话入口，后端通过 Codex CLI 执行，并使用 API Key 接入模型服务。
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
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          alignItems={{ md: "center" }}
          useFlexGap
          flexWrap="wrap"
        >
          <Typography variant="body2">
            Model: {configSummary?.provider ?? "-"} / {configSummary?.model ?? "-"}
          </Typography>
          <Typography variant="body2">
            Key: {configSummary?.apiKeyConfigured ? "Configured" : "Missing"} ({configSummary?.apiKeyEnv ?? "-"})
          </Typography>
          <Typography variant="body2">
            Codex CLI:{" "}
            {health == null ? "Checking" : health.codexCliAvailable ? "Available" : "Unavailable"}
          </Typography>
          <Typography variant="body2">Router: {configSummary?.routerEnabled ? "Enabled" : "Disabled"}</Typography>
          <Typography variant="body2">
            Approval:{" "}
            {configSummary?.approvalEnabled
              ? configSummary?.approvalDryRunOnly
                ? "Enabled (Dry-run only)"
                : "Enabled (Submit allowed)"
              : "Disabled"}
          </Typography>
          <Typography variant="body2">Run status: {getRunStatusLabel(runStatus)}</Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Activity: {activitySummary || "-"}
        </Typography>
      </Paper>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "280px minmax(0, 1fr)" },
          gap: 2,
          height: { xs: "auto", md: DESKTOP_WORKSPACE_HEIGHT },
          minHeight: { xs: "auto", md: 620 },
          alignItems: "stretch",
        }}
      >
        <Paper
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            display: "flex",
            flexDirection: "column",
            minHeight: { xs: 260, md: 0 },
            maxHeight: { xs: 320, md: "none" },
            height: { md: "100%" },
            overflow: "hidden",
            background: "linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(247,250,252,0.96) 100%)",
          }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 1.25 }}>
            <Box>
              <Typography variant="subtitle2">对话记录</Typography>
              <Typography variant="caption" color="text.secondary">
                {sessions.length} 个会话
              </Typography>
            </Box>
            <Button size="small" variant="outlined" onClick={createNewSession}>
              新建
            </Button>
          </Stack>
          <Divider />
          <List dense disablePadding sx={{ flex: 1, minHeight: 0, overflowY: "auto", p: 1 }}>
            {sessions.map((session) => {
              const selected = session.sessionId === selectedSessionId;

              return (
                <ListItemButton
                  key={session.sessionId}
                  selected={selected}
                  onClick={() => setSelectedSessionId(session.sessionId)}
                  sx={{
                    mb: 0.75,
                    alignItems: "flex-start",
                    border: "1px solid",
                    borderColor: selected ? "primary.main" : "divider",
                    backgroundColor: selected ? "rgba(23, 92, 211, 0.08)" : "rgba(255,255,255,0.6)",
                    "&.Mui-selected": {
                      backgroundColor: "rgba(23, 92, 211, 0.1)",
                    },
                    "&.Mui-selected:hover": {
                      backgroundColor: "rgba(23, 92, 211, 0.14)",
                    },
                  }}
                >
                  <ListItemText
                    primary={getSessionTitle(session)}
                    secondary={`${session.status} · ${session.lastActiveAt}`}
                    primaryTypographyProps={{ fontWeight: selected ? 600 : 500, noWrap: true }}
                    secondaryTypographyProps={{ sx: { mt: 0.5 }, noWrap: true }}
                  />
                </ListItemButton>
              );
            })}
          </List>
        </Paper>

        <Paper
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            display: "flex",
            flexDirection: "column",
            minHeight: { xs: 560, md: 0 },
            height: { md: "100%" },
            overflow: "hidden",
            background: "linear-gradient(180deg, rgba(250,252,255,0.96) 0%, rgba(241,245,249,0.92) 100%)",
          }}
        >
          <Box
            sx={{
              px: { xs: 1.5, md: 2 },
              py: 1.5,
              borderBottom: "1px solid",
              borderColor: "divider",
              backgroundColor: "rgba(255,255,255,0.78)",
            }}
          >
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {selectedSession ? getSessionTitle(selectedSession) : "-"}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {selectedSession?.workspaceDir || configSummary?.workspaceDir || "-"}
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1.25 }}>
              <Box
                sx={{
                  px: 1.25,
                  py: 0.5,
                  borderRadius: 999,
                  backgroundColor: "rgba(11, 79, 108, 0.1)",
                  width: "fit-content",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  运行状态: {getRunStatusLabel(runStatus)}
                </Typography>
              </Box>
              <Box
                sx={{
                  px: 1.25,
                  py: 0.5,
                  borderRadius: 999,
                  backgroundColor: "rgba(148, 163, 184, 0.14)",
                  width: "fit-content",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  消息数: {messages.length}
                </Typography>
              </Box>
            </Stack>
          </Box>

          <Box
            ref={messagesViewportRef}
            onScroll={(event) => {
              shouldStickToBottomRef.current = shouldStickToBottom(event.currentTarget);
            }}
            sx={{
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              px: { xs: 1.25, md: 2 },
              py: 2,
              display: "flex",
              flexDirection: "column",
              gap: 1.25,
              background:
                "radial-gradient(circle at top right, rgba(44,125,160,0.08), transparent 24%), linear-gradient(180deg, rgba(248,250,252,0.4) 0%, rgba(255,255,255,0.12) 100%)",
            }}
          >
            {loading ? (
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                sx={{
                  width: "fit-content",
                  px: 1.5,
                  py: 1,
                  borderRadius: 999,
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.92)",
                }}
              >
                <CircularProgress size={16} />
                <Typography variant="body2">加载中...</Typography>
              </Stack>
            ) : null}

            {!loading && messages.length === 0 ? (
              <Box
                sx={{
                  alignSelf: "center",
                  maxWidth: 420,
                  px: 2,
                  py: 1.75,
                  borderRadius: 2,
                  border: "1px dashed",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.76)",
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  当前会话还没有消息。输入问题后按 Enter 发送，Shift+Enter 换行。
                </Typography>
              </Box>
            ) : null}

            {messages.map((message) => {
              const isUserMessage = message.role === "user";

              return (
                <Box
                  key={message.messageId}
                  sx={{
                    display: "flex",
                    justifyContent: isUserMessage ? "flex-end" : "flex-start",
                  }}
                >
                  <Box
                    sx={{
                      maxWidth: { xs: "100%", sm: "88%", lg: "74%" },
                      px: 1.5,
                      py: 1.25,
                      border: "1px solid",
                      borderColor: isUserMessage ? "rgba(11,79,108,0.16)" : "rgba(148,163,184,0.22)",
                      borderRadius: isUserMessage ? "18px 18px 6px 18px" : "18px 18px 18px 6px",
                      backgroundColor: isUserMessage ? "rgba(222, 247, 255, 0.94)" : "rgba(255,255,255,0.92)",
                      boxShadow: "0 10px 28px rgba(15, 23, 42, 0.06)",
                    }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      {roleLabel(message.role)} · {message.createdAt}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.75, whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
                      {message.content || (message.role === "assistant" && isRunning ? "..." : "-")}
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Box>

          <Divider />
          <Box
            sx={{
              p: { xs: 1.25, md: 1.5 },
              backgroundColor: "rgba(255,255,255,0.88)",
            }}
          >
            <Stack spacing={1.25}>
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
                sx={{
                  "& .MuiInputBase-root": {
                    alignItems: "flex-start",
                    backgroundColor: "rgba(255,255,255,0.94)",
                  },
                }}
              />
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1}
                justifyContent="space-between"
                alignItems={{ sm: "center" }}
              >
                <Typography variant="caption" color="text.secondary">
                  Enter 发送，Shift+Enter 换行
                </Typography>
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
            </Stack>
          </Box>
        </Paper>
      </Box>
    </Stack>
  );
}
