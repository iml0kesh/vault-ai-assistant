/* Vault Self-Service Portal — Frontend Logic */

let history     = [];
let currentMode = null;

// ── Screen navigation ──────────────────────────────────────────────────────────
function showScreen(id) {
  ["mode-screen", "form-screen", "chat-screen"].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.style.display = "none";
  });
  const target = document.getElementById(id);
  if (target) target.style.display = "flex";
}

function goBack() {
  history = [];
  currentMode = null;
  clearMessages();
  showScreen("mode-screen");
}

// ── Mode selection ─────────────────────────────────────────────────────────────
function selectMode(mode) {
  currentMode = mode;
  if (mode === "onboard") {
    showScreen("form-screen");
    return;
  }
  showScreen("chat-screen");
  updateModeLabel(mode);
  clearMessages();

  const intros = {
    qa:      "Q&A mode — Ask me anything about HashiCorp Vault.\n\nExamples:\n• What is AppRole authentication?\n• How does Kubernetes auth work?\n• Difference between KV v1 and v2?\n• Can we do custom password rotation for Oracle?\n• What are Vault best practices for AWS workloads?",
    trouble: "Troubleshooting mode — Describe your Vault issue and I'll diagnose it.\n\nExamples:\n• I'm getting permission denied when reading secrets\n• AppRole login is failing with invalid secret_id\n• My Kubernetes pod can't authenticate to Vault\n• Oracle credentials expired before TTL\n• Token expired and app stopped working"
  };
  addMsg("ai", intros[mode]);
}

function updateModeLabel(mode) {
  const bar = document.getElementById("mode-label");
  if (!bar) return;
  const labels = {
    onboard: ["ONBOARDING", "ml-onboard"],
    qa:      ["Q&A",        "ml-qa"],
    trouble: ["TROUBLESHOOT","ml-trouble"]
  };
  const [text, cls] = labels[mode] || ["Q&A", "ml-qa"];
  bar.textContent  = text;
  bar.className    = `mode-label ${cls}`;
}

// ── Onboarding form submission ─────────────────────────────────────────────────
function submitForm() {
  const get  = id => document.getElementById(id)?.value?.trim() || "";
  const name = get("f-name");
  const plat = get("f-platform");
  const sec  = get("f-secret");
  const env  = get("f-env");
  const ns   = get("f-ns");

  if (!name || !plat || !sec || !env || !ns) {
    alert("Please fill in all required fields (marked with *)");
    return;
  }

  const lang   = get("f-lang") || "Not specified";
  const access = get("f-access") || "read-only";

  const msg =
`Application Name: ${name}
Platform: ${plat}
Language/Type: ${lang}
Secret Type: ${sec}
Environment: ${env}
Namespace: ${ns}
Access: ${access}`;

  showScreen("chat-screen");
  updateModeLabel("onboard");
  clearMessages();
  addMsg("user", msg);
  sendToBot(msg);
}

// ── Chat helpers ───────────────────────────────────────────────────────────────
function clearMessages() {
  const box = document.getElementById("messages");
  if (box) box.innerHTML = "";
}

function addMsg(role, text) {
  const box  = document.getElementById("messages");
  if (!box) return;

  const wrap = document.createElement("div");
  wrap.className = `msg ${role === "user" ? "user" : ""}`;

  const av = document.createElement("div");
  av.className   = role === "user" ? "av av-user" : "av av-ai";
  av.textContent = role === "user" ? "U" : "V";

  const bub = document.createElement("div");
  bub.className  = role === "user" ? "bubble bubble-user" : "bubble bubble-ai";
  bub.textContent = text;

  wrap.appendChild(av);
  wrap.appendChild(bub);
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

function addTyping() {
  const box  = document.getElementById("messages");
  const wrap = document.createElement("div");
  wrap.className = "msg"; wrap.id = "typing";
  const av  = document.createElement("div");
  av.className   = "av av-ai"; av.textContent = "V";
  const bub = document.createElement("div");
  bub.className  = "typing-bub";
  bub.innerHTML  = '<div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>';
  wrap.appendChild(av); wrap.appendChild(bub);
  box.appendChild(wrap); box.scrollTop = box.scrollHeight;
}

function removeTyping() {
  document.getElementById("typing")?.remove();
}

// ── Send message ───────────────────────────────────────────────────────────────
function sendMsg() {
  const inp  = document.getElementById("inp");
  const text = inp?.value?.trim();
  if (!text) return;
  inp.value = ""; inp.style.height = "auto";
  addMsg("user", text);
  sendToBot(text);
}

async function sendToBot(text) {
  addTyping();
  try {
    const res  = await fetch("/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ message: text, history, mode: currentMode })
    });
    const data = await res.json();
    removeTyping();
    const reply = data.response || "No response received.";
    addMsg("ai", reply);
    history.push({ user: text, assistant: reply });
  } catch {
    removeTyping();
    addMsg("ai", "Connection error. Make sure the Flask server is running on port 5000.");
  }
}

// ── Input helpers ──────────────────────────────────────────────────────────────
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 100) + "px";
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMsg();
  }
}
