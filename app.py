from flask import Flask, request, jsonify, render_template
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_core.output_parsers import StrOutputParser
import re

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Models ─────────────────────────────────────────────────────────────────────
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectordb   = Chroma(persist_directory="vector_db", embedding_function=embeddings)
retriever  = vectordb.as_retriever(search_kwargs={"k": 5})
llm        = OllamaLLM(model="llama3.2:3b")

# ── Static knowledge ───────────────────────────────────────────────────────────
WHY_AUTH = {
    "AppRole Auth":    "AppRole Auth is the right choice for VM/bare-metal servers. It uses a role_id and secret_id for machine-to-machine authentication — no cloud identity provider needed.",
    "AWS IAM Auth":    "AWS IAM Auth is the right choice for AWS workloads. The EC2 instance authenticates using its attached IAM role — no credentials need to be stored anywhere.",
    "Kubernetes Auth": "Kubernetes Auth is the right choice for pods. Containers authenticate using their native Kubernetes service account token — no secrets to manage.",
    "GitHub Auth":     "GitHub Auth is the right choice for GitHub Actions. The pipeline authenticates using its built-in GitHub token — no credentials to store.",
}
WHY_ENGINE = {
    "KV Secret Engine":              "The KV Secret Engine securely stores static credentials like API keys, passwords, and tokens with full versioning support.",
    "Oracle Database Secret Engine": "The Oracle Database Secret Engine dynamically generates short-lived Oracle credentials on demand — no static passwords, automatic rotation.",
    "LDAP Secret Engine":            "The LDAP Secret Engine manages and auto-rotates Active Directory/LDAP service account passwords.",
}

# ── Detection maps ─────────────────────────────────────────────────────────────
PLATFORM_MAP = [
    (["kubernetes", "k8s", "pod", "container", "kubectl", "helm"],       "Kubernetes",    "Kubernetes Auth"),
    (["github action", "github workflow", "ci/cd", "cicd", "pipeline"],  "GitHub Actions","GitHub Auth"),
    (["aws", "ec2", "lambda", "ecs", "fargate"],                         "AWS",           "AWS IAM Auth"),
    (["vm", "virtual machine", "bare metal", "baremetal", "server",
      "traditional", "on-prem", "on-premise"],                           "VM/Bare Metal", "AppRole Auth"),
]
SECRET_MAP = [
    (["oracle", "oracle db", "oracle database"],                          "Oracle DB credentials",   "Oracle Database Secret Engine"),
    (["ldap", "active directory", "openldap"],                            "LDAP credentials",        "LDAP Secret Engine"),
    (["api key", "api keys", "static", "static secret", "password",
      "token", "kv", "config"],                                           "Static credentials",      "KV Secret Engine"),
]
ENV_MAP = [
    (["non-prod", "nonprod", "non prod"],    "non-prod"),
    (["production", "prod"],                 "prod"),
    (["development", "dev"],                 "dev"),
    (["testing", "qa"],                      "qa"),
    (["staging", "stage"],                   "staging"),
    (["uat"],                                "uat"),
]
UNSUPPORTED_KEYWORDS = [
    "mysql", "postgres", "postgresql", "mongodb", "redis", "pki",
    "tls certificate", "ssh secret", "oidc", "jwt auth", "azure ad",
    "azure auth", "gcp auth", "transit", "totp", "rabbitmq", "cassandra",
]
SENSITIVE_PATTERNS = [
    r'password\s*[:=]\s*\S+',
    r'passwd\s*[:=]\s*\S+',
    r'token\s*[:=]\s*\S+',
    r'api[_-]?key\s*[:=]\s*\S+',
    r'secret\s*[:=]\s*\S{6,}',
]
CONFIRM_WORDS = [
    "yes", "correct", "confirm", "looks good", "that's right",
    "go ahead", "proceed", "confirmed", "ok", "okay", "sure",
    "yep", "yup", "approved", "yes confirm", "all good",
]

# ── Template field labels ──────────────────────────────────────────────────────
TEMPLATE_TEXT = """To onboard your application, fill in this template and send it:

Application Name: <your app name>
Platform: <VM / AWS EC2 / Kubernetes / GitHub Actions>
Language/Type: <Java / Python / Node.js / etc.>
Secret Type: <Oracle DB credentials / API keys / LDAP credentials>
Environment: <dev / qa / prod / non-prod>
Namespace: <your Vault namespace>
Access: <read-only / read-write>

Example:
Application Name: payment-service
Platform: AWS EC2
Language/Type: Java Spring Boot
Secret Type: Oracle DB credentials
Environment: production
Namespace: finance
Access: read-only

For any Vault questions, just ask — e.g. "What is AppRole auth?" or "How does Kubernetes auth work?\""""

WELCOME = f"""Hello! I am the Vault Self-Service Onboarding Assistant.

I help application teams onboard into HashiCorp Vault.

I have two modes:

1. Onboarding — Fill in the template below and I will recommend the right auth method and secret engine, then walk you through the steps.

2. Q&A — Ask me anything about Vault. Examples:
   - "What is AppRole authentication?"
   - "How does Kubernetes auth work?"
   - "What is the difference between KV v1 and v2?"
   - "I am getting a permission denied error"

Supported Auth Methods: AppRole Auth | AWS IAM Auth | Kubernetes Auth | GitHub Auth
Supported Secret Engines: KV Secret Engine | Oracle Database Secret Engine | LDAP Secret Engine

---

{TEMPLATE_TEXT}"""

UNSUPPORTED = "This use case is not currently supported by the Vault self-service platform. A Vault engineer will get in touch with you shortly."

SENSITIVE_WARNING = """Please do not share actual passwords, tokens, or credentials here.

This assistant is a readiness checker — it tells you what to prepare and how to onboard.
Actual credential values should go directly to the Vault Ops team via a secure channel.

Please re-send your template without any actual credential values."""

# ── Helpers ────────────────────────────────────────────────────────────────────
def has(text, triggers):
    t = text.lower()
    return any(k in t for k in triggers)

def is_confirm(msg):
    t = msg.strip().lower()
    return any(t == k or t.startswith(k) for k in CONFIRM_WORDS)

def is_sensitive(msg):
    return any(re.search(p, msg, re.IGNORECASE) for p in SENSITIVE_PATTERNS)

def is_greeting(msg):
    t = msg.strip().lower()
    greetings = ["hi", "hello", "hey", "what can you do", "who are you",
                 "help me", "get started", "what is this", "how can you help"]
    return len(t.split()) <= 8 and any(k in t for k in greetings)

def get_docs(query):
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)

def ask_llm(prompt):
    return StrOutputParser().invoke(llm.invoke(prompt))

def history_str(history):
    return "".join(f"User: {t['user']}\nAssistant: {t['assistant']}\n\n" for t in history)

def detect_platform(text):
    t = text.lower()
    for kws, pl, am in PLATFORM_MAP:
        if any(k in t for k in kws):
            return pl, am
    return None, None

def detect_secret(text):
    t = text.lower()
    for kws, sl, se in SECRET_MAP:
        if any(k in t for k in kws):
            return sl, se
    return None, None

def detect_env(text):
    t = text.lower()
    for kws, label in ENV_MAP:
        if any(k in t for k in kws):
            return label
    return None

# ── Parse structured template ──────────────────────────────────────────────────
def parse_template(text):
    """
    Parses a filled template from the user.
    Returns dict with keys: app_name, platform, lang, secret_type, env, namespace, access
    Returns None if this doesn't look like a filled template.
    """
    fields = {
        "app_name":    r'application\s+name\s*[:=]\s*(.+)',
        "platform":    r'platform\s*[:=]\s*(.+)',
        "lang":        r'language[/\w]*\s*[:=]\s*(.+)',
        "secret_type": r'secret\s+type\s*[:=]\s*(.+)',
        "env":         r'environment\s*[:=]\s*(.+)',
        "namespace":   r'namespace\s*[:=]\s*(.+)',
        "access":      r'access\s*[:=]\s*(.+)',
    }
    result = {}
    for key, pattern in fields.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result[key] = m.group(1).strip()

    # Need at least app_name + platform + secret_type to be a valid template
    if result.get("app_name") and result.get("platform") and result.get("secret_type"):
        return result
    return None

def resolve_auth_engine(parsed):
    """Map parsed platform/secret text to auth method and secret engine."""
    plat_text = parsed.get("platform", "")
    secret_text = parsed.get("secret_type", "")

    plat, auth = detect_platform(plat_text)
    stype, eng = detect_secret(secret_text)

    # Fallback: also scan full text
    if not plat:
        combined = " ".join(parsed.values())
        plat, auth = detect_platform(combined)
    if not stype:
        combined = " ".join(parsed.values())
        stype, eng = detect_secret(combined)

    return plat, auth, stype, eng

# ── LLM prompts ────────────────────────────────────────────────────────────────
SYSTEM = """You are an enterprise HashiCorp Vault Self-Service Onboarding Assistant.
Behave like a senior Vault onboarding engineer. Be concise and professional.
Answer ONLY from the documentation context provided. Never ask for passwords or credentials."""

def p_qa(ctx, hist, q):
    return f"""{SYSTEM}

Answer the user's question like a senior Vault engineer talking to an application team.
Use the context provided. Be direct, helpful, and conversational.

You may be asked:
- Factual questions: 'What is AppRole?' 'How does KV v2 work?'
- Scenario questions: 'Can we do custom password rotation?' 'What is standard for Oracle creds?'
- Troubleshooting: 'Permission denied error' 'Secret not found'
- Comparison questions: 'Difference between KV v1 and v2?'

For ALL questions:
- Give a clear direct answer first, then add useful detail
- If troubleshooting, state the likely cause and the exact fix
- Answer from the context — do not hallucinate
- Never show the onboarding template

{history_str(hist)}---
Context:
{ctx}

User: {q}
Answer:"""

def p_summary(parsed, plat, auth, stype, eng):
    app  = parsed.get("app_name", "Not specified")
    env  = detect_env(parsed.get("env", "")) or parsed.get("env", "Not specified")
    ns   = parsed.get("namespace", "Not specified")
    lang = parsed.get("lang", "Not specified")
    acc  = parsed.get("access", "read-only")
    return f"""Here is the onboarding use case I understood from your input:

Application Name : {app}
Language/Type    : {lang}
Platform         : {plat or parsed.get('platform', 'Not specified')}
Auth Method      : {auth or 'Could not determine — please check platform field'}
Secret Type      : {stype or parsed.get('secret_type', 'Not specified')}
Secret Engine    : {eng or 'Could not determine — please check secret type field'}
Environment      : {env}
Vault Namespace  : {ns}
Access Level     : {acc}

Please confirm if everything is correct.
If yes, I will show you exactly how a Vault engineer will onboard your application and what you need to prepare."""

def p_plan(ctx, hist, parsed, plat, auth, stype, eng):
    app  = parsed.get("app_name", "your application")
    env  = detect_env(parsed.get("env", "")) or parsed.get("env", "as specified")
    ns   = parsed.get("namespace", "as specified")
    acc  = parsed.get("access", "read-only")
    wa   = WHY_AUTH.get(auth, f"{auth} is recommended for this platform.")
    we   = WHY_ENGINE.get(eng, f"{eng} is recommended for this secret type.")

    return f"""{SYSTEM}

Generate a complete Vault onboarding readiness plan. Tell users WHAT to prepare — never ask for actual credential values.

Confirmed details:
- Application: {app}
- Platform: {plat}
- Auth Method: {auth}
- Secret Engine: {eng}
- Secret Type: {stype}
- Environment: {env}
- Namespace: {ns}
- Access: {acc}

Why this recommendation:
{wa}
{we}

Use this EXACT format:

Recommended Authentication Method: {auth}
Recommended Secret Engine: {eng}

Why this recommendation:
[use the why text above]

Onboarding Plan:
1. [specific step for {auth}]
2. [specific step]
3. [specific step for {eng}]
4. [specific step]
5. [specific step]

What you need to prepare (share values with Vault Ops team via secure channel — NOT here):
- Application name and environment confirmed above
- Vault namespace confirmed above
- [secret-engine specific items as field names only, no actual values]
- Access level confirmed above

Vault Policy Example:
path "[engine-specific-path]/{app}/*" {{{{ capabilities = ["read"] }}}}

Best Practices:
- Use least privilege — read-only unless write is explicitly required
- Separate dev / qa / prod with different Vault roles and policies
- Never hardcode credentials in source code
- Rotate credentials regularly

Validation Checklist:
- [ ] Auth method configured and tested in non-prod first
- [ ] Vault policy created with correct path and capabilities
- [ ] Secret path created and verified
- [ ] Application successfully retrieves secrets

{history_str(hist)}---
Context:
{ctx}

Generate the plan now.
Answer:"""

# ── Route ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data    = request.get_json()
    msg     = data.get("message", "").strip()
    history = data.get("history", [])
    mode    = data.get("mode", "qa")  # 'onboard', 'qa', 'trouble' — set by UI

    if not msg:
        return jsonify({"response": "Please enter a message."})

    # Always: sensitive data guard
    if is_sensitive(msg):
        return jsonify({"response": SENSITIVE_WARNING})

    # ── ONBOARDING MODE ────────────────────────────────────────────────────────
    if mode == "onboard":
        # Step 1: Parse the filled form (first message is always the template)
        parsed = parse_template(msg)
        if parsed:
            plat, auth, stype, eng = resolve_auth_engine(parsed)
            secret_text = parsed.get("secret_type", "").lower()
            if has(secret_text, UNSUPPORTED_KEYWORDS):
                return jsonify({"response": UNSUPPORTED})
            summary = p_summary(parsed, plat, auth, stype, eng)
            return jsonify({"response": summary})

        # Step 2: User confirmed summary → generate plan
        if is_confirm(msg) and history:
            ctx = get_docs(msg)
            last = history[-1].get("assistant", "")
            def ef(text, label):
                m = re.search(rf'{label}\s*:\s*(.+)', text, re.IGNORECASE)
                return m.group(1).strip() if m else None
            parsed_hist = {
                "app_name":    ef(last, "Application Name"),
                "lang":        ef(last, "Language/Type"),
                "secret_type": ef(last, "Secret Type"),
                "env":         ef(last, "Environment"),
                "namespace":   ef(last, "Vault Namespace"),
                "access":      ef(last, "Access Level"),
            }
            plat  = ef(last, "Platform")
            auth  = ef(last, "Auth Method")
            stype = ef(last, "Secret Type")
            eng   = ef(last, "Secret Engine")
            if auth and eng:
                return jsonify({"response": ask_llm(p_plan(ctx, history, parsed_hist, plat, auth, stype, eng))})
            return jsonify({"response": "Could not find previous summary. Please go back and fill the form again."})

        # Any other message in onboard mode → Q&A about their specific use case
        ctx = get_docs(msg)
        return jsonify({"response": ask_llm(p_qa(ctx, history, msg))})

    # ── TROUBLESHOOTING MODE ───────────────────────────────────────────────────
    if mode == "trouble":
        ctx = get_docs(msg)
        prompt = f"""{SYSTEM}

The user has a Vault problem. Be a Vault support engineer.
State the most likely cause first, then give the exact fix with commands.
Be direct and practical. Use the context provided.

{history_str(history)}---
Context:
{ctx}

User: {msg}
Answer:"""
        return jsonify({"response": ask_llm(prompt)})

    # ── Q&A MODE (default) ─────────────────────────────────────────────────────
    # Unsupported check — only for onboarding attempts
    ONBOARDING_INTENT = ["onboard", "integrate", "set up", "configure", "i need", "we need", "can i use", "can we use"]
    if has(msg, UNSUPPORTED_KEYWORDS) and has(msg, ONBOARDING_INTENT) and not any(
        k in msg.lower() for k in ["what is", "what are", "how does", "explain", "tell me", "standard", "rotation", "custom"]
    ):
        return jsonify({"response": UNSUPPORTED})

    ctx = get_docs(msg)
    return jsonify({"response": ask_llm(p_qa(ctx, history, msg))})

if __name__ == "__main__":
    app.run(debug=True, port=5000)