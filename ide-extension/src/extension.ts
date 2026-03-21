import * as vscode from "vscode";

let panel: vscode.WebviewPanel | undefined;

function createNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 32; i += 1) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function getApiBaseUrl(): string {
  const config = vscode.workspace.getConfiguration();
  const raw = String(config.get("clawcheck.chatApiBaseUrl", "http://127.0.0.1:8000/api")).trim();
  return raw.replace(/\/$/, "");
}

function getWebviewHtml(webview: vscode.Webview): string {
  const nonce = createNonce();
  const apiBase = JSON.stringify(getApiBaseUrl());
  const csp = [
    "default-src 'none'",
    `img-src ${webview.cspSource} data:`,
    `style-src ${webview.cspSource} 'unsafe-inline'`,
    `script-src 'nonce-${nonce}'`,
    "connect-src http: https: vscode-webview:",
  ].join("; ");

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="Content-Security-Policy" content="${csp}" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>clawcheck Chat</title>
    <style>
      :root { color-scheme: light dark; }
      * { box-sizing: border-box; }
      html, body { margin: 0; padding: 0; height: 100%; font-family: var(--vscode-font-family); }
      body { display: grid; grid-template-rows: auto 1fr auto; gap: 8px; padding: 8px; }
      .topbar {
        display: flex; align-items: center; justify-content: space-between; gap: 8px;
        border: 1px solid var(--vscode-panel-border); padding: 8px;
      }
      .layout { display: grid; grid-template-columns: 240px 1fr; gap: 8px; min-height: 0; }
      .card {
        border: 1px solid var(--vscode-panel-border);
        min-height: 0;
        display: flex;
        flex-direction: column;
      }
      .card-header {
        padding: 8px;
        border-bottom: 1px solid var(--vscode-panel-border);
        display: flex; justify-content: space-between; align-items: center;
      }
      .session-list { overflow: auto; padding: 4px; display: grid; gap: 4px; }
      .session-item {
        width: 100%;
        text-align: left;
        border: 1px solid var(--vscode-panel-border);
        background: transparent;
        color: inherit;
        padding: 6px 8px;
        cursor: pointer;
      }
      .session-item.active { border-color: var(--vscode-focusBorder); }
      .messages {
        overflow: auto;
        padding: 8px;
        display: grid;
        gap: 8px;
      }
      .message {
        border: 1px solid var(--vscode-panel-border);
        padding: 8px;
        white-space: pre-wrap;
      }
      .message.user { background: color-mix(in srgb, var(--vscode-textLink-foreground) 10%, transparent); }
      .meta { opacity: 0.8; font-size: 12px; margin-bottom: 6px; }
      .composer {
        border: 1px solid var(--vscode-panel-border);
        padding: 8px;
        display: grid;
        gap: 8px;
      }
      textarea {
        width: 100%;
        min-height: 72px;
        resize: vertical;
        background: var(--vscode-input-background);
        color: var(--vscode-input-foreground);
        border: 1px solid var(--vscode-input-border);
        padding: 8px;
      }
      .row { display: flex; gap: 8px; align-items: center; }
      button {
        border: 1px solid var(--vscode-button-border, transparent);
        background: var(--vscode-button-background);
        color: var(--vscode-button-foreground);
        padding: 6px 10px;
        cursor: pointer;
      }
      button.secondary {
        background: transparent;
        color: inherit;
        border-color: var(--vscode-panel-border);
      }
      button[disabled] { opacity: 0.5; cursor: not-allowed; }
      .status { font-size: 12px; opacity: 0.9; }
      .error {
        color: var(--vscode-errorForeground);
        font-size: 12px;
      }
    </style>
  </head>
  <body>
    <div class="topbar">
      <div class="status" id="status">Idle</div>
      <div class="status" id="apiInfo"></div>
    </div>
    <div class="layout">
      <section class="card">
        <div class="card-header">
          <strong>Sessions</strong>
          <button class="secondary" id="newSessionBtn">New</button>
        </div>
        <div class="session-list" id="sessionList"></div>
      </section>
      <section class="card">
        <div class="card-header">
          <strong id="sessionTitle">Messages</strong>
        </div>
        <div class="messages" id="messageList"></div>
      </section>
    </div>
    <div class="composer">
      <textarea id="composer" placeholder="Type a message. Enter to send, Shift+Enter for newline."></textarea>
      <div class="row">
        <button id="sendBtn">Send</button>
        <button class="secondary" id="stopBtn">Stop</button>
        <span class="error" id="error"></span>
      </div>
    </div>

    <script nonce="${nonce}">
      (() => {
        const apiBase = ${apiBase};
        const statusEl = document.getElementById("status");
        const apiInfoEl = document.getElementById("apiInfo");
        const sessionListEl = document.getElementById("sessionList");
        const sessionTitleEl = document.getElementById("sessionTitle");
        const messageListEl = document.getElementById("messageList");
        const newSessionBtn = document.getElementById("newSessionBtn");
        const sendBtn = document.getElementById("sendBtn");
        const stopBtn = document.getElementById("stopBtn");
        const composerEl = document.getElementById("composer");
        const errorEl = document.getElementById("error");

        /** @type {Array<any>} */
        let sessions = [];
        let selectedSessionId = "";
        /** @type {Array<any>} */
        let messages = [];
        let runStatus = "idle";
        let lastSeq = 0;
        /** @type {EventSource | null} */
        let eventSource = null;
        let sending = false;

        apiInfoEl.textContent = apiBase;

        async function request(path, init = {}) {
          const response = await fetch(apiBase + path, {
            ...init,
            headers: {
              "Accept": "application/json",
              ...(init.body ? { "Content-Type": "application/json" } : {}),
            },
          });
          if (!response.ok) {
            let detail = "";
            try {
              const payload = await response.json();
              detail = String(payload.detail || "");
            } catch {
              detail = "";
            }
            throw new Error(detail || ("Request failed: " + response.status));
          }
          return response.json();
        }

        function setError(message) {
          errorEl.textContent = message || "";
        }

        function setStatus(text) {
          runStatus = text || "idle";
          statusEl.textContent = "Status: " + runStatus;
        }

        function renderSessions() {
          sessionListEl.innerHTML = "";
          for (const session of sessions) {
            const button = document.createElement("button");
            button.className = "session-item" + (session.sessionId === selectedSessionId ? " active" : "");
            button.textContent = (session.title || ("Session " + session.sessionId.slice(0, 8))) + " · " + session.status;
            button.addEventListener("click", () => selectSession(session.sessionId));
            sessionListEl.appendChild(button);
          }
        }

        function renderMessages() {
          messageListEl.innerHTML = "";
          for (const message of messages) {
            const box = document.createElement("div");
            box.className = "message " + (message.role === "user" ? "user" : "assistant");
            const meta = document.createElement("div");
            meta.className = "meta";
            meta.textContent = (message.role || "assistant") + " · " + (message.createdAt || "-");
            const content = document.createElement("div");
            content.textContent = message.content || ((message.role === "assistant" && (runStatus === "running" || runStatus === "queued")) ? "..." : "-");
            box.appendChild(meta);
            box.appendChild(content);
            messageListEl.appendChild(box);
          }
          messageListEl.scrollTop = messageListEl.scrollHeight;
        }

        async function loadSessions() {
          const response = await request("/chat/sessions");
          sessions = response.sessions || [];
          if (sessions.length === 0) {
            const created = await request("/chat/sessions", { method: "POST", body: JSON.stringify({}) });
            sessions = [created.session];
          }
          if (!selectedSessionId) {
            selectedSessionId = sessions[0].sessionId;
          } else if (!sessions.some((s) => s.sessionId === selectedSessionId)) {
            selectedSessionId = sessions[0].sessionId;
          }
          renderSessions();
          await loadSessionDetail();
        }

        async function createSession() {
          setError("");
          const response = await request("/chat/sessions", { method: "POST", body: JSON.stringify({}) });
          sessions.unshift(response.session);
          selectedSessionId = response.session.sessionId;
          renderSessions();
          await loadSessionDetail();
        }

        async function loadSessionDetail() {
          if (!selectedSessionId) {
            messages = [];
            renderMessages();
            return;
          }
          const detail = await request("/chat/sessions/" + encodeURIComponent(selectedSessionId));
          messages = detail.messages || [];
          sessionTitleEl.textContent = detail.session?.title || "Messages";
          setStatus(detail.running ? "running" : (detail.session?.status || "idle"));
          lastSeq = 0;
          renderMessages();
          connectStream();
        }

        function selectSession(sessionId) {
          selectedSessionId = sessionId;
          renderSessions();
          loadSessionDetail().catch((error) => setError(error.message));
        }

        function connectStream() {
          if (!selectedSessionId) {
            return;
          }
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
          const streamUrl = apiBase + "/chat/sessions/" + encodeURIComponent(selectedSessionId) + "/stream?afterSeq=" + lastSeq;
          eventSource = new EventSource(streamUrl);

          const handler = (rawEvent) => {
            try {
              const payload = JSON.parse(rawEvent.data);
              lastSeq = Math.max(lastSeq, Number(payload.seq || 0));
              const eventType = payload.type;
              const data = payload.data || {};
              if (eventType === "message_created" && data.message) {
                if (!messages.some((item) => item.messageId === data.message.messageId)) {
                  messages.push(data.message);
                  renderMessages();
                }
              } else if (eventType === "token") {
                const messageId = String(data.messageId || "");
                const delta = String(data.delta || "");
                if (messageId && delta) {
                  messages = messages.map((item) => item.messageId === messageId ? { ...item, content: (item.content || "") + delta } : item);
                  renderMessages();
                }
              } else if (eventType === "status") {
                setStatus(String(data.status || ""));
              } else if (eventType === "done") {
                setStatus(String(data.status || ""));
                loadSessionDetail().catch(() => {});
              } else if (eventType === "error") {
                setError(String(data.message || "Unknown error"));
              }
            } catch {
              // ignore malformed events
            }
          };

          const eventTypes = ["status", "message_created", "token", "tool", "event", "error", "done", "session_created"];
          for (const eventType of eventTypes) {
            eventSource.addEventListener(eventType, handler);
          }
        }

        async function sendMessage() {
          if (sending || !selectedSessionId) {
            return;
          }
          const content = composerEl.value.trim();
          if (!content) {
            return;
          }
          sending = true;
          setError("");
          sendBtn.disabled = true;
          try {
            const response = await request("/chat/sessions/" + encodeURIComponent(selectedSessionId) + "/messages", {
              method: "POST",
              body: JSON.stringify({ content }),
            });
            const userMessage = response.userMessage;
            const assistantMessage = response.assistantMessage;
            if (userMessage && !messages.some((item) => item.messageId === userMessage.messageId)) {
              messages.push(userMessage);
            }
            if (assistantMessage && !messages.some((item) => item.messageId === assistantMessage.messageId)) {
              messages.push(assistantMessage);
            }
            renderMessages();
            setStatus(response.run?.status || "queued");
            composerEl.value = "";
          } catch (error) {
            setError(error.message || String(error));
          } finally {
            sending = false;
            sendBtn.disabled = false;
          }
        }

        async function stopRun() {
          if (!selectedSessionId) {
            return;
          }
          setError("");
          try {
            await request("/chat/sessions/" + encodeURIComponent(selectedSessionId) + "/cancel", { method: "POST" });
            setStatus("cancel_requested");
          } catch (error) {
            setError(error.message || String(error));
          }
        }

        newSessionBtn.addEventListener("click", () => createSession().catch((error) => setError(error.message)));
        sendBtn.addEventListener("click", () => sendMessage());
        stopBtn.addEventListener("click", () => stopRun());
        composerEl.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
          }
        });

        loadSessions().catch((error) => setError(error.message));
      })();
    </script>
  </body>
</html>`;
}

export function activate(context: vscode.ExtensionContext): void {
  const disposable = vscode.commands.registerCommand("clawcheck.openChatPanel", () => {
    if (panel !== undefined) {
      panel.reveal(vscode.ViewColumn.Beside);
      return;
    }

    panel = vscode.window.createWebviewPanel(
      "clawcheckChatPanel",
      "clawcheck Chat",
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      },
    );

    panel.webview.html = getWebviewHtml(panel.webview);
    panel.onDidDispose(() => {
      panel = undefined;
    });
  });

  context.subscriptions.push(disposable);
}

export function deactivate(): void {
  if (panel !== undefined) {
    panel.dispose();
    panel = undefined;
  }
}

