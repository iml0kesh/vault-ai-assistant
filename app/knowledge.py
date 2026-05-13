# Static knowledge — auth method and secret engine explanations
# Edit these to match your enterprise Vault documentation

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

CONFIRM_WORDS = [
    "yes", "correct", "confirm", "looks good", "that's right",
    "go ahead", "proceed", "confirmed", "ok", "okay", "sure",
    "yep", "yup", "approved", "all good",
]

SENSITIVE_PATTERNS = [
    r'password\s*[:=]\s*\S+',
    r'passwd\s*[:=]\s*\S+',
    r'token\s*[:=]\s*\S+',
    r'api[_-]?key\s*[:=]\s*\S+',
    r'secret\s*[:=]\s*\S{6,}',
]
