from flask import Flask, request, jsonify, render_template
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_core.output_parsers import StrOutputParser

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Embeddings + Vector DB + LLM ──────────────────────────────────────────────
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectordb   = Chroma(persist_directory="vector_db", embedding_function=embeddings)
retriever  = vectordb.as_retriever(search_kwargs={"k": 5})
llm        = OllamaLLM(model="llama3.2:3b")

# ── Python keyword detection (not LLM) ────────────────────────────────────────
PLATFORM_MAP = [
    (["kubernetes", "k8s", "pod", "container", "kubectl", "helm"],     "Kubernetes",    "Kubernetes Auth"),
    (["github action", "github workflow", "ci/cd", "cicd", "pipeline"], "GitHub Actions", "GitHub Auth"),
    (["aws", "ec2", "lambda", "ecs", "fargate"],                        "AWS",           "AWS IAM Auth"),
    (["vm", "virtual machine", "bare metal", "baremetal", "server",
      "traditional", "on-prem", "on-premise"],                          "VM/Bare Metal", "AppRole Auth"),
]
SECRET_MAP = [
    (["oracle", "oracle db", "oracle database"],      "Oracle DB credentials",     "Oracle Database Secret Engine"),
    (["ldap", "active directory", "openldap"],        "LDAP credentials",          "LDAP Secret Engine"),
    (["api key", "password", "token", "static",
      "config", "credential", "secret", "key"],       "Static credentials/API keys", "KV Secret Engine"),
]
UNSUPPORTED = [
    "mysql","postgres","postgresql","mongodb","redis","pki","tls certificate",
    "ssh secret","oidc","jwt auth","azure ad","azure auth","gcp auth",
    "transit","totp","rabbitmq","consul","cassandra",
]
CONFIRM_WORDS = ["yes","correct","confirm","looks good","that's right","go ahead",
                 "proceed","confirmed","ok","okay","sure","yep","yup","approved"]
INFO_WORDS    = ["what is","what are","how does","how do","explain","tell me about",
                 "describe","difference between","what does"]
TROUBLE_WORDS = ["error","failing","failed","not working","permission denied","invalid",
                 "expired","cannot","can't","unable","broken","issue","problem","troubleshoot"]

def detect(text):
    t = text.lower()
    plat = auth = stype = eng = None
    for kws, pl, am in PLATFORM_MAP:
        if any(k in t for k in kws):
            plat, auth = pl, am
            break
    for kws, sl, se in SECRET_MAP:
        if any(k in t for k in kws):
            stype, eng = sl, se
            break
    return plat, auth, stype, eng

def is_unsupported(text):
    t = text.lower()
    return any(k in t for k in UNSUPPORTED)

def is_info(text):
    t = text.lower()
    return any(k in t for k in INFO_WORDS)

def is_trouble(text):
    t = text.lower()
    return any(k in t for k in TROUBLE_WORDS)

def is_confirm(text):
    t = text.strip().lower()
    return any(t == k or t.startswith(k) for k in CONFIRM_WORDS)

def extract_env(text):
    t = text.lower()
    for e in ["production","prod","staging","qa","dev","development","test","uat"]:
        if e in t:
            return e
    return None

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def ask_llm(prompt_text):
    return StrOutputParser().invoke(llm.invoke(prompt_text))

def build_history(history):
    return "".join(f"User: {t['user']}\nAssistant: {t['assistant']}\n\n" for t in history)

# ── Prompt builders ────────────────────────────────────────────────────────────

HEADER = """You are an enterprise HashiCorp Vault Self-Service Onboarding Assistant.
You behave like a senior Vault onboarding engineer helping teams CHECK if they can onboard to Vault.
Answer ONLY from the documentation context provided. Be concise and professional.

SUPPORTED AUTH METHODS: AppRole Auth, AWS IAM Auth, Kubernetes Auth, GitHub Auth.
SUPPORTED SECRET ENGINES: KV Secret Engine, Oracle Database Secret Engine, LDAP Secret Engine.

CRITICAL RULE - NEVER ask for or request any of the following:
- Passwords, secrets, tokens, or credentials of any kind
- Usernames or service account passwords
- Database connection strings with real credentials
- API keys or private keys
- Any actual sensitive values

This tool is a READINESS CHECKER only. It helps users understand:
1. Which Vault auth method and secret engine they need
2. What they need to PREPARE before onboarding
3. What the onboarding steps will look like
4. What inputs the Vault Ops team will need from them (field names only, NOT values)

Always clarify: "Do not share actual credentials here. This assistant helps you prepare for onboarding, not collect sensitive data."
"""

def prompt_info(context, history, question):
    return f"""{HEADER}
The user is asking an informational question. Answer it clearly and concisely from the context.
Do NOT use onboarding plan format. Do NOT list Required Inputs. Just explain it well.

{build_history(history)}---
Context:
{context}

User: {question}
Answer:"""

def prompt_trouble(context, history, question):
    return f"""{HEADER}
The user has a problem. Diagnose it and give the exact fix from the context.
State the likely cause first, then the fix. Do NOT use onboarding plan format.

{build_history(history)}---
Context:
{context}

User: {question}
Answer:"""

def prompt_intake(context, history, question, detected):
    known = ""
    if detected:
        known = f"\nALREADY DETECTED FROM USER INPUT:\n{detected}\n"
    return f"""{HEADER}{known}
The user wants to onboard an application into Vault.

Your response must do TWO things:
1. Briefly confirm what you detected (1-2 sentences explaining WHY that auth method and secret engine are correct for their use case).
2. Ask ONLY for what is still missing: application name, environment (dev/qa/prod), and Vault namespace.
   Ask maximum 2 questions in a single short paragraph.

Do NOT ask about platform or secret type — those are already detected above.
Do NOT generate onboarding steps yet.

{build_history(history)}---
Context:
{context}

User: {question}
Answer:"""

def prompt_summary(context, history, question, plat, auth, stype, eng, env):
    return f"""{HEADER}
You have collected enough information. Produce ONLY the summary below. Nothing else.

STOP after the confirmation line. Do NOT add any questions. Do NOT ask for Oracle details.
Do NOT ask for any inputs. Do NOT generate steps. Just the summary and the confirmation line.

Write exactly this (fill in the blanks from the conversation):

Based on the information provided, here is the understood onboarding use case:
- Application: <name from conversation>
- Platform: {plat or "as described"}
- Authentication Method: {auth or "as discussed"}
- Secret Engine: {eng or "as discussed"}
- Secret Type: {stype or "as discussed"}
- Environment: {env or "from conversation"}
- Namespace: <namespace from conversation>

Please confirm if this is correct, or let me know what needs to change.

STOP HERE. Do not write anything after the confirmation line.

{build_history(history)}---
Context:
{context}

User: {question}
Answer:"""

def prompt_plan(context, history, plat, auth, stype, eng, env):
    return f"""{HEADER}
The user confirmed their onboarding details. Generate a complete onboarding readiness plan.

IMPORTANT: This plan must tell users WHAT to prepare, not ask for actual values.
Never request real passwords, usernames, or credentials.
Frame required inputs as "what you need to have ready" — field names and descriptions only.

Confirmed details:
- Platform: {plat or "as discussed"}
- Authentication Method: {auth or "as discussed"}
- Secret Engine: {eng or "as discussed"}
- Secret Type: {stype or "as discussed"}
- Environment: {env or "as discussed"}

Use this EXACT format:

Recommended Authentication Method: {auth or "<method>"}
Recommended Secret Engine: {eng or "<engine>"}

Why this recommendation:
<1-2 sentences explaining why this auth method and secret engine fit their use case>

Onboarding Plan:
1. <step>
2. <step>
3. <step>
4. <step>
5. <step>

What You Need to Prepare (do NOT share actual values here — provide these to the Vault Ops team via secure channel):
- Application name
- Target environment (dev / qa / prod)
- Vault namespace
- <secret-engine specific items as field names only, e.g. "Oracle DB hostname and port" NOT the actual value>
- Required access level (read-only / read-write)

Vault Policy Example:
path "<secret-path>" {{ capabilities = ["read"] }}

Best Practices:
- Use least privilege access
- Rotate credentials regularly
- Separate production and non-production environments
- Never hardcode credentials in application source code
- Provide sensitive values only to the Vault Ops team via secure channel, not in this chat

Validation Checklist:
- Auth method configured and tested
- Policy created and attached to role
- Secret path created with correct permissions
- Application retrieves secrets successfully in non-production first

Note: This assistant is a readiness checker. Do not share actual passwords, usernames, or credentials here.
To proceed with onboarding, raise a request with the Vault Ops team using the details above.

{build_history(history)}---
Context:
{context}

Generate the plan now.
Answer:"""

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/auth")
def auth():
    return render_template("auth.html")

@app.route("/engines")
def engines():
    return render_template("engines.html")

@app.route("/help")
def help():
    return render_template("help.html")

@app.route("/chat", methods=["POST"])
def chat():
    data        = request.get_json()
    user_msg    = data.get("message", "").strip()
    history     = data.get("history", [])

    if not user_msg:
        return jsonify({"response": "Please enter a message."})

    # ── Sensitive data guard ───────────────────────────────────────────────────
    import re
    sensitive_patterns = [
        r'password\s*[:=]\s*\S+',
        r'passwd\s*[:=]\s*\S+',
        r'secret\s*[:=]\s*\S+',
        r'token\s*[:=]\s*\S+',
        r'api[_-]?key\s*[:=]\s*\S+',
        r'username\s*[:=]\s*\S+',
        r'user\s*[:=]\s*\S+',
        r'pwd\s*[:=]\s*\S+',
    ]
    if any(re.search(p, user_msg, re.IGNORECASE) for p in sensitive_patterns):
        return jsonify({"response": (
            "⚠️ It looks like you may be sharing actual credentials or sensitive values.\n\n"
            "Please do not share real passwords, usernames, tokens, or secrets in this chat.\n\n"
            "This assistant is a Vault onboarding readiness checker — it helps you understand "
            "WHAT to prepare and HOW to onboard. Actual sensitive values should be provided "
            "directly to the Vault Ops team via a secure channel.\n\n"
            "Please rephrase your message without any actual credential values."
        )})

    # Collect all user text across session for detection
    all_user_text = user_msg + " " + " ".join(t["user"] for t in history)
    all_text      = all_user_text + " " + " ".join(t["assistant"] for t in history)

    plat, auth, stype, eng = detect(all_user_text)
    env = extract_env(all_text)

    docs    = retriever.invoke(user_msg)
    context = format_docs(docs)

    # 1. Unsupported
    if is_unsupported(user_msg) and not is_info(user_msg) and not is_trouble(user_msg):
        return jsonify({"response": "This use case is not currently supported by the Vault self-service platform. A Vault engineer will get in touch with you shortly."})

    # 2. Informational
    if is_info(user_msg) and not any(k in user_msg.lower() for k in ["onboard", "integrate", "set up", "setup"]):
        return jsonify({"response": ask_llm(prompt_info(context, history, user_msg))})

    # 3. Troubleshooting
    if is_trouble(user_msg):
        return jsonify({"response": ask_llm(prompt_trouble(context, history, user_msg))})

    # 4. Confirmation -> generate plan
    if is_confirm(user_msg) and len(history) >= 1:
        return jsonify({"response": ask_llm(prompt_plan(context, history, plat, auth, stype, eng, env))})

    # 5. Onboarding intake / summary
    known_parts = []
    if plat and auth:  known_parts.append(f"Platform: {plat} -> Auth Method: {auth}")
    if stype and eng:  known_parts.append(f"Secret Type: {stype} -> Secret Engine: {eng}")
    if env:            known_parts.append(f"Environment: {env}")
    detected_str = "\n".join(known_parts) if known_parts else None

    # Only go to summary if we have answers across multiple turns (not first message)
    # and we have env + namespace signals from history
    has_env      = env is not None
    has_namespace = any(k in all_text.lower() for k in ["namespace", "ns ", " ns="])
    is_first_msg  = len(history) == 0

    if plat and stype and has_env and has_namespace and not is_first_msg:
        return jsonify({"response": ask_llm(prompt_summary(context, history, user_msg, plat, auth, stype, eng, env))})

    # Still collecting — go to intake
    return jsonify({"response": ask_llm(prompt_intake(context, history, user_msg, detected_str))})

if __name__ == "__main__":
    app.run(debug=True, port=5000)