"""
All LLM prompt builders in one place.
Changing a prompt = edit here only, nothing else needs to change.
"""
from app.knowledge import WHY_AUTH, WHY_ENGINE
from app.detector import detect_env


SYSTEM = """You are an enterprise HashiCorp Vault Self-Service Onboarding Assistant.
Behave like a senior Vault onboarding engineer. Be concise and professional.
Answer ONLY from the documentation context provided. Never ask for passwords or credentials."""


def history_str(history):
    return "".join(f"User: {t['user']}\nAssistant: {t['assistant']}\n\n" for t in history)


def qa_prompt(ctx, history, question):
    return f"""{SYSTEM}

Answer the user's question like a senior Vault engineer.
Use the context provided. Be direct, helpful, and conversational.

Types of questions you may receive:
- Factual: "What is AppRole?" "How does KV v2 work?"
- Scenario: "Can we do custom password rotation?" "What is standard for Oracle?"
- Troubleshooting: "Permission denied" "Secret not found"
- Comparison: "Difference between KV v1 and v2?"

Rules:
- Give a clear direct answer first, then add detail
- For troubleshooting: state the likely cause then the exact fix
- Answer from context only — never hallucinate

{history_str(history)}---
Context:
{ctx}

User: {question}
Answer:"""


def trouble_prompt(ctx, history, question):
    return f"""{SYSTEM}

The user has a Vault problem. Be a Vault support engineer.
State the most likely cause first, then give the exact fix with commands.
Be direct and practical. Use the context provided.

{history_str(history)}---
Context:
{ctx}

User: {question}
Answer:"""


def summary_text(parsed, plat, auth, stype, eng):
    app  = parsed.get("app_name", "Not specified")
    env  = detect_env(parsed.get("env", "")) or parsed.get("env", "Not specified")
    ns   = parsed.get("namespace", "Not specified")
    lang = parsed.get("lang", "Not specified")
    acc  = parsed.get("access", "read-only")
    return f"""Here is the onboarding use case I understood from your input:

Application Name : {app}
Language/Type    : {lang}
Platform         : {plat or parsed.get('platform', 'Not specified')}
Auth Method      : {auth or 'Could not determine — check platform field'}
Secret Type      : {stype or parsed.get('secret_type', 'Not specified')}
Secret Engine    : {eng or 'Could not determine — check secret type field'}
Environment      : {env}
Vault Namespace  : {ns}
Access Level     : {acc}

Please confirm if everything is correct.
If yes, I will show you exactly how a Vault engineer will onboard your application and what you need to prepare."""


def plan_prompt(ctx, history, parsed, plat, auth, stype, eng):
    app  = parsed.get("app_name", "your-app")
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

Use this EXACT format:

Recommended Authentication Method: {auth}
Recommended Secret Engine: {eng}

Why this recommendation:
{wa}
{we}

Onboarding Plan:
1. [specific step for {auth}]
2. [specific step]
3. [specific step for {eng}]
4. [specific step]
5. [specific step]

What you need to prepare (share with Vault Ops team via secure channel — NOT here):
- Application name and environment confirmed above
- Vault namespace confirmed above
- [secret-engine specific field names only, no actual values]
- Access level confirmed above

Vault Policy Example:
path "[engine-path]/{app}/*" {{{{ capabilities = ["read"] }}}}

Best Practices:
- Use least privilege — read-only unless write is required
- Separate dev / qa / prod with different Vault roles
- Never hardcode credentials in source code
- Rotate credentials regularly

Validation Checklist:
- [ ] Auth method configured and tested in non-prod first
- [ ] Vault policy created with correct path and capabilities
- [ ] Secret path created and verified
- [ ] Application successfully retrieves secrets

{history_str(history)}---
Context:
{ctx}

Generate the plan now.
Answer:"""
