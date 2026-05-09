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

# ── Knowledge: why each method is correct ─────────────────────────────────────
WHY_AUTH = {
    "AppRole Auth":    "AppRole Auth is the right choice for VM and bare-metal servers — it uses a role_id and secret_id for machine-to-machine authentication without needing cloud identity.",
    "AWS IAM Auth":    "AWS IAM Auth is the right choice for AWS EC2/Lambda/ECS — the instance authenticates using its attached IAM role, no credentials need to be stored.",
    "Kubernetes Auth": "Kubernetes Auth is the right choice for pods — containers authenticate using their native Kubernetes service account token.",
    "GitHub Auth":     "GitHub Auth is the right choice for GitHub Actions — pipelines authenticate using the built-in GitHub token.",
}
WHY_ENGINE = {
    "KV Secret Engine":              "The KV Secret Engine stores static credentials like API keys, passwords, and tokens securely with versioning.",
    "Oracle Database Secret Engine": "The Oracle Database Secret Engine dynamically generates short-lived Oracle credentials on demand, removing the need for static passwords.",
    "LDAP Secret Engine":            "The LDAP Secret Engine manages and auto-rotates Active Directory / LDAP service account passwords.",
}

# ── Detection maps ─────────────────────────────────────────────────────────────
PLATFORM_MAP = [
    (["kubernetes", "k8s", "pod", "container", "kubectl", "helm"],      "Kubernetes",    "Kubernetes Auth"),
    (["github action", "github workflow", "ci/cd", "cicd", "pipeline"], "GitHub Actions","GitHub Auth"),
    (["aws", "ec2", "lambda", "ecs", "fargate"],                        "AWS",           "AWS IAM Auth"),
    (["vm", "virtual machine", "bare metal", "baremetal", "server",
      "traditional", "on-prem", "on-premise"],                          "VM/Bare Metal", "AppRole Auth"),
]
SECRET_MAP = [
    (["oracle", "oracle db", "oracle database"],           "Oracle DB credentials",   "Oracle Database Secret Engine"),
    (["ldap", "active directory", "openldap"],             "LDAP credentials",        "LDAP Secret Engine"),
    (["api key", "api keys", "static", "password",
      "token", "kv", "config", "app secret"],              "Static credentials",      "KV Secret Engine"),
]
UNSUPPORTED_KEYWORDS = [
    "mysql", "postgres", "postgresql", "mongodb", "redis", "pki",
    "tls certificate", "ssh secret", "oidc", "jwt auth", "azure ad",
    "azure auth", "gcp auth", "transit", "totp", "rabbitmq", "cassandra",
]
ENV_MAP = [
    (["production", "prod"],                "prod"),
    (["development", "dev"],                "dev"),
    (["quality assurance", "testing", "qa"],"qa"),
    (["staging", "stage"],                  "staging"),
    (["uat"],                               "uat"),
]
GREETING_TRIGGERS = [
    "hi", "hello", "hey", "what can you do", "what do you do",
    "who are you", "help me", "how can you help", "get started",
    "i need help", "what is this tool", "what are you",
]
INFO_TRIGGERS = [
    "what is", "what are", "how does", "how do", "explain",
    "tell me about", "describe", "difference between", "what does",
]
TROUBLE_TRIGGERS = [
    "error", "failing", "failed", "not working", "permission denied",
    "invalid", "expired", "cannot", "can\'t", "unable", "broken",
    "issue with", "problem with", "troubleshoot",
]
ONBOARDING_TRIGGERS = [
    "my app", "my application", "our app", "our application",
    "i have a", "we have a", "i need to onboard", "onboard my",
    "runs on", "running on", "deployed on", "hosted on",
    "needs to read", "needs vault", "needs secrets", "needs credentials",
    "java", "python", "node", "spring", "microservice", "batch job",
    "service needs", "integrate with vault",
]
CONFIRM_WORDS = [
    "yes", "correct", "confirm", "looks good", "that\'s right",
    "go ahead", "proceed", "confirmed", "ok", "okay", "sure",
    "yep", "yup", "approved", "yes confirm", "yes that\'s correct",
]
SENSITIVE_PATTERNS = [
    r'password\s*[:=]\s*\S+',
    r'passwd\s*[:=]\s*\S+',
    r'token\s*[:=]\s*\S+',
    r'api[_-]?key\s*[:=]\s*\S+',
    r'username\s*[:=]\s*\S+',
    r'pwd\s*[:=]\s*\S+',
]

# ── Helper functions ───────────────────────────────────────────────────────────
def detect(turns):
    """Detect platform and secret type from list of user messages."""
    plat = auth = stype = eng = None
    for text in turns:
        t = text.lower()
        if not plat:
            for kws, pl, am in PLATFORM_MAP:
                if any(k in t for k in kws):
                    plat, auth = pl, am
                    break
        if not stype:
            for kws, sl, se in SECRET_MAP:
                if any(k in t for k in kws):
                    stype, eng = sl, se
                    break
        if plat and stype:
            break
    return plat, auth, stype, eng

def get_env(text):
    t = text.lower()
    for keywords, label in ENV_MAP:
        if any(k in t for k in keywords):
            return label
    return None

def has(text, triggers):
    t = text.strip().lower()
    return any(k in t for k in triggers)

def is_greeting(msg):
    t = msg.strip().lower()
    return len(t.split()) <= 8 and has(t, GREETING_TRIGGERS)

def is_confirm(msg):
    t = msg.strip().lower()
    return any(t == k or t.startswith(k) for k in CONFIRM_WORDS)

def is_sensitive(msg):
    return any(re.search(p, msg, re.IGNORECASE) for p in SENSITIVE_PATTERNS)

def get_docs(query):
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)

def ask(prompt):
    return StrOutputParser().invoke(llm.invoke(prompt))

def history_str(history):
    return "".join(f"User: {t['user']}\nAssistant: {t['assistant']}\n\n" for t in history)

# ── Static responses (no LLM needed) ──────────────────────────────────────────
WELCOME = """Hello! I'm the Vault Self-Service Onboarding Assistant.

I help application teams check readiness for onboarding into HashiCorp Vault.

What I can do:
- Onboarding Guidance: Describe your app and I'll recommend the right auth method and secret engine, then walk you through the steps.
- Answer Questions: Ask me anything — "What is AppRole?", "How does Kubernetes auth work?"
- Troubleshoot: Describe an error and I'll diagnose it.

Supported Auth Methods: AppRole Auth | AWS IAM Auth | Kubernetes Auth | GitHub Auth
Supported Secret Engines: KV Secret Engine | Oracle Database Secret Engine | LDAP Secret Engine

To get started, describe your use case. Example:
"My Java app runs on a VM and needs Oracle DB credentials." """

UNSUPPORTED = "This use case is not currently supported by the Vault self-service platform. A Vault engineer will get in touch with you shortly."

SENSITIVE_WARNING = """⚠️ Please do not share actual passwords, tokens, or credentials here.

This assistant is a readiness checker — it tells you WHAT to prepare and HOW to onboard.
Actual sensitive values should go directly to the Vault Ops team via a secure channel.

Please rephrase without any credential values."""

# ── LLM Prompts ────────────────────────────────────────────────────────────────
SYSTEM = """You are an enterprise HashiCorp Vault Self-Service Onboarding Assistant.
Behave like a senior Vault onboarding engineer. Be concise and professional.
Answer ONLY from the documentation context provided.
NEVER ask for or accept passwords, tokens, usernames, or any actual credential values.
This tool is a readiness checker — it tells users what to prepare, not collects secrets."""

def p_info(ctx, hist, q):
    return f"""{SYSTEM}

The user is asking an informational question. Answer clearly and concisely from the context.
Do NOT use onboarding plan format.

{history_str(hist)}---
Context: {ctx}

User: {q}
Answer:"""

def p_trouble(ctx, hist, q):
    return f"""{SYSTEM}

The user has a Vault problem. State the likely cause then give the exact fix from context.
Do NOT use onboarding plan format.

{history_str(hist)}---
Context: {ctx}

User: {q}
Answer:"""

def p_intake(ctx, hist, q, plat, auth, stype, eng, missing):
    known = ""
    if plat:  known += f"- Platform detected: {plat} -> Use {auth}\n"
    if stype: known += f"- Secret type detected: {stype} -> Use {eng}\n"

    return f"""{SYSTEM}

{"ALREADY DETECTED (do NOT ask about these):" + chr(10) + known if known else ""}
STILL NEEDED (ask ONLY for these, nothing else): {", ".join(missing) if missing else "all collected"}

Rules:
1. If platform is known, confirm it in one sentence using the EXACT explanation below:
   - VM/Bare Metal  -> "Since your app runs on a VM, we will use AppRole Auth — designed for server-based apps authenticating with role_id and secret_id."
   - AWS            -> "Since your app runs on AWS EC2, we will use AWS IAM Auth — the instance authenticates using its attached IAM role."
   - Kubernetes     -> "Since your app runs in Kubernetes, we will use Kubernetes Auth — pods authenticate via service account tokens."
   - GitHub Actions -> "Since this is a GitHub Actions workflow, we will use GitHub Auth — the pipeline authenticates using its GitHub token."
2. Ask ONLY for items listed in STILL NEEDED. Maximum 2 questions. One question per missing item.
3. Do NOT generate onboarding steps yet. Do NOT ask for passwords or credentials.

{history_str(hist)}---
Context: {ctx}

User: {q}
Answer:"""

def p_summary(ctx, hist, q, plat, auth, stype, eng, env, appname, namespace):
    return f"""{SYSTEM}

All required information has been collected. Output ONLY this summary, then stop.
Do NOT add any questions or steps after the confirmation line.

Write exactly:

Based on the information provided, here is the understood onboarding use case:
- Application: {appname}
- Platform: {plat}
- Authentication Method: {auth}
- Secret Engine: {eng}
- Secret Type: {stype}
- Environment: {env}
- Namespace: {namespace}

Please confirm if this is correct, or let me know what needs to change.

{history_str(hist)}---
User: {q}
Answer:"""

def p_plan(ctx, hist, plat, auth, stype, eng, env):
    wa = WHY_AUTH.get(auth, f"{auth} is the recommended method for this platform.")
    we = WHY_ENGINE.get(eng, f"{eng} is the recommended engine for this secret type.")
    return f"""{SYSTEM}

Generate a complete Vault onboarding readiness plan for the confirmed details below.
Tell users WHAT to prepare — never ask for actual credential values.

Confirmed:
- Platform: {plat}
- Authentication Method: {auth}
- Secret Engine: {eng}
- Secret Type: {stype}
- Environment: {env}

Use this EXACT format:

Recommended Authentication Method: {auth}
Recommended Secret Engine: {eng}

Why This Recommendation:
{wa} {we}

Onboarding Plan:
1. <specific step for {auth}>
2. <specific step>
3. <specific step for {eng}>
4. <specific step>
5. <specific step>

What You Need to Prepare (provide these to the Vault Ops team — do NOT share actual values here):
- Application name and target environment
- Vault namespace
- {"Oracle DB hostname, port, and service name (no passwords)" if "Oracle" in eng else "Secret path and key names" if "KV" in eng else "LDAP server URL and service account DN (no passwords)"}
- Required access level (read-only or read-write)

Vault Policy Example:
path "{"oracle/creds" if "Oracle" in eng else "ldap/static-cred" if "LDAP" in eng else "kv/data"}/<app-name>/*" {{{{ capabilities = ["read"] }}}}

Best Practices:
- Use least privilege — grant read-only unless write is required
- Separate dev / qa / prod with different Vault roles and policies
- Never hardcode credentials in application source code
- Rotate secret_id regularly (AppRole) or let Vault handle rotation (Oracle/LDAP engines)

Validation Checklist:
- [ ] Auth method configured and tested in non-prod first
- [ ] Vault policy created and attached to role
- [ ] Secret path created and verified
- [ ] Application successfully retrieves secrets

Note: This is a readiness check. Share actual credential values only with the Vault Ops team via secure channel.

{history_str(hist)}---
Context: {ctx}

Answer:"""

# ── Route ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    msg      = data.get("message", "").strip()
    history  = data.get("history", [])

    if not msg:
        return jsonify({"response": "Please enter a message."})

    # ── 1. Greeting ────────────────────────────────────────────────────────────
    if is_greeting(msg) and not history:
        return jsonify({"response": WELCOME})

    # ── 2. Sensitive data guard ────────────────────────────────────────────────
    if is_sensitive(msg):
        return jsonify({"response": SENSITIVE_WARNING})

    # ── 3. Unsupported ─────────────────────────────────────────────────────────
    if has(msg, UNSUPPORTED_KEYWORDS) and not has(msg, INFO_TRIGGERS) and not has(msg, TROUBLE_TRIGGERS):
        return jsonify({"response": UNSUPPORTED})

    # Gather all context
    all_turns = [t["user"] for t in history] + [msg]
    all_text  = " ".join(all_turns)
    plat, auth, stype, eng = detect(all_turns)
    env = get_env(all_text)

    # Extract app name and namespace from full conversation text
    appname   = None
    namespace = None
    name_patterns = [
        r'(?:application|app)\s+(?:name\s+)?is\s+([\w-]+)',
        r'named?\s+([\w-]+)',
        r'called\s+([\w-]+)',
        r'name\s*[:\/]\s*([\w-]+)',
    ]
    ns_patterns = [
        r'namespace\s+is\s+([\w-]+)',
        r'namespace\s*[:\/]\s*([\w-]+)',
        r'ns\s*[:\/]\s*([\w-]+)',
    ]
    for p in name_patterns:
        m = re.search(p, all_text, re.IGNORECASE)
        if m:
            appname = m.group(1)
            break
    for p in ns_patterns:
        m = re.search(p, all_text, re.IGNORECASE)
        if m:
            namespace = m.group(1)
            break

    ctx = get_docs(msg)

    # ── 4. Informational ───────────────────────────────────────────────────────
    if has(msg, INFO_TRIGGERS) and not has(msg, ONBOARDING_TRIGGERS):
        return jsonify({"response": ask(p_info(ctx, history, msg))})

    # ── 5. Troubleshooting ─────────────────────────────────────────────────────
    if has(msg, TROUBLE_TRIGGERS):
        return jsonify({"response": ask(p_trouble(ctx, history, msg))})

    # ── 6. Confirmation → generate plan ───────────────────────────────────────
    if is_confirm(msg) and history:
        return jsonify({"response": ask(p_plan(ctx, history, plat, auth, stype, eng, env))})

    # ── 7. All collected → summary ─────────────────────────────────────────────
    if plat and stype and env and appname and namespace and history:
        return jsonify({"response": ask(p_summary(ctx, history, msg, plat, auth, stype, eng, env, appname, namespace))})

    # ── 8. Still collecting → intake ──────────────────────────────────────────
    missing = []
    if not stype:     missing.append("secret type (Oracle DB credentials / API keys / LDAP credentials)")
    if not appname:   missing.append("application name")
    if not env:       missing.append("environment (dev / qa / prod)")
    if not namespace: missing.append("Vault namespace")

    if has(msg, ONBOARDING_TRIGGERS) or plat or stype or history:
        return jsonify({"response": ask(p_intake(ctx, history, msg, plat, auth, stype, eng, missing))})

    # ── 9. Fallback ────────────────────────────────────────────────────────────
    return jsonify({"response": (
        "I can help you onboard your application into Vault, answer questions, or troubleshoot issues.\n\n"
        "To get started, describe your use case. Example:\n"
        "My Java app runs on a VM and needs Oracle DB credentials."
    )})

if __name__ == "__main__":
    app.run(debug=True, port=5000)