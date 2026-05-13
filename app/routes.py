"""
Flask route handlers.
Each mode (onboard / qa / trouble) is a clean isolated function.
"""
import re
from flask import request, jsonify, render_template
from app.rag import get_context, ask
from app.detector import parse_template, resolve_auth_engine, is_confirm, is_sensitive, is_unsupported_onboarding, has
from app.prompts import qa_prompt, trouble_prompt, summary_text, plan_prompt
from app.knowledge import UNSUPPORTED_KEYWORDS


UNSUPPORTED    = "This use case is not currently supported by the Vault self-service platform. A Vault engineer will get in touch with you shortly."
SENSITIVE_WARN = """Please do not share actual passwords, tokens, or credentials here.

This assistant is a readiness checker — it tells you what to prepare, not collect secrets.
Share actual values only with the Vault Ops team via a secure channel.

Please re-send without any actual credential values."""


def register_routes(app):

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/chat", methods=["POST"])
    def chat():
        data    = request.get_json()
        msg     = data.get("message", "").strip()
        history = data.get("history", [])
        mode    = data.get("mode", "qa")

        if not msg:
            return jsonify({"response": "Please enter a message."})

        # Global guard — sensitive data
        if is_sensitive(msg):
            return jsonify({"response": SENSITIVE_WARN})

        # ── ONBOARDING MODE ────────────────────────────────────────────────────
        if mode == "onboard":
            return handle_onboard(msg, history)

        # ── TROUBLESHOOTING MODE ───────────────────────────────────────────────
        if mode == "trouble":
            return handle_trouble(msg, history)

        # ── Q&A MODE ──────────────────────────────────────────────────────────
        return handle_qa(msg, history)


def handle_onboard(msg, history):
    # Parse structured form submission
    parsed = parse_template(msg)
    if parsed:
        plat, auth, stype, eng = resolve_auth_engine(parsed)
        if has(parsed.get("secret_type", ""), UNSUPPORTED_KEYWORDS):
            return jsonify({"response": UNSUPPORTED})
        return jsonify({"response": summary_text(parsed, plat, auth, stype, eng)})

    # Confirm → generate plan
    if is_confirm(msg) and history:
        last = history[-1].get("assistant", "")
        def ef(label):
            m = re.search(rf'{label}\s*:\s*(.+)', last, re.IGNORECASE)
            return m.group(1).strip() if m else None
        parsed_h = {
            "app_name":    ef("Application Name"),
            "lang":        ef("Language/Type"),
            "secret_type": ef("Secret Type"),
            "env":         ef("Environment"),
            "namespace":   ef("Vault Namespace"),
            "access":      ef("Access Level"),
        }
        auth  = ef("Auth Method")
        eng   = ef("Secret Engine")
        plat  = ef("Platform")
        stype = ef("Secret Type")
        if auth and eng:
            ctx = get_context(msg)
            return jsonify({"response": ask(plan_prompt(ctx, history, parsed_h, plat, auth, stype, eng))})
        return jsonify({"response": "Could not find previous summary. Please go back and fill the form again."})

    # Follow-up question in onboard mode
    ctx = get_context(msg)
    return jsonify({"response": ask(qa_prompt(ctx, history, msg))})


def handle_trouble(msg, history):
    ctx = get_context(msg)
    return jsonify({"response": ask(trouble_prompt(ctx, history, msg))})


def handle_qa(msg, history):
    if is_unsupported_onboarding(msg):
        return jsonify({"response": UNSUPPORTED})
    ctx = get_context(msg)
    return jsonify({"response": ask(qa_prompt(ctx, history, msg))})
