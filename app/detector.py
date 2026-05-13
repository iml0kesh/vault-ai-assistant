"""
Python-based intent and entity detector.
All routing decisions are made here — NOT by the LLM.
The LLM is only called to generate the actual text response.
"""
import re
from app.knowledge import PLATFORM_MAP, SECRET_MAP, ENV_MAP, UNSUPPORTED_KEYWORDS, CONFIRM_WORDS, SENSITIVE_PATTERNS


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


def has(text, triggers):
    t = text.lower()
    return any(k in t for k in triggers)


def is_confirm(msg):
    t = msg.strip().lower()
    return any(t == k or t.startswith(k) for k in CONFIRM_WORDS)


def is_sensitive(msg):
    return any(re.search(p, msg, re.IGNORECASE) for p in SENSITIVE_PATTERNS)


def is_unsupported_onboarding(msg):
    """Returns True only when user is trying to USE unsupported tech, not just asking about it."""
    INTENT = ["onboard", "integrate", "set up", "configure", "i need", "we need", "can i use", "can we use"]
    INFO   = ["what is", "what are", "how does", "explain", "tell me", "standard", "rotation", "custom"]
    return has(msg, UNSUPPORTED_KEYWORDS) and has(msg, INTENT) and not has(msg, INFO)


def parse_template(text):
    """
    Parses a structured onboarding form submission.
    Returns dict if valid template, None otherwise.
    Requires app_name + platform + secret_type at minimum.
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

    if result.get("app_name") and result.get("platform") and result.get("secret_type"):
        return result
    return None


def resolve_auth_engine(parsed):
    """Map parsed platform/secret text to Vault auth method and secret engine."""
    plat, auth = detect_platform(parsed.get("platform", ""))
    stype, eng = detect_secret(parsed.get("secret_type", ""))

    if not plat:
        plat, auth = detect_platform(" ".join(parsed.values()))
    if not stype:
        stype, eng = detect_secret(" ".join(parsed.values()))

    return plat, auth, stype, eng
