# Vault AI Self-Service Assistant (Local)

An enterprise HashiCorp Vault onboarding assistant that runs fully locally
using Ollama + LangChain + ChromaDB.

---

## Project Structure

```
vault-assistant/
├── docs/                        ← Vault documentation (RAG source)
│   ├── approle_auth.txt
│   ├── kubernetes_auth.txt
│   ├── aws_iam_auth.txt
│   ├── github_auth.txt
│   ├── kv_secret_engine.txt
│   ├── oracle_db_secret_engine.txt
│   ├── ldap_secret_engine.txt
│   ├── vault_policies.txt
│   ├── onboarding_guide.txt
│   └── troubleshooting.txt
├── vector_db/                   ← ChromaDB (auto-created by ingest.py)
├── app.py                       ← Main assistant
├── ingest.py                    ← Builds the vector database
├── requirements.txt             ← Python dependencies
└── README.md
```

---

## Setup Instructions

### Step 1: Install Ollama
Download from https://ollama.com and install.

Pull the recommended lightweight model:
```bash
ollama pull llama3.2:3b
```

Alternative models (if you want better quality):
```bash
ollama pull qwen2.5:3b     # good alternative
ollama pull mistral:7b     # better quality, needs ~5GB RAM
```

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Build the Vector Database
Run this once (or again if you update the docs):
```bash
python ingest.py
```

Expected output:
```
Loaded 10 documents
Split into ~180 chunks
Building vector database...
Vector database created successfully!
```

### Step 4: Start the Assistant
```bash
python app.py
```

---

## Example Questions to Test

**AppRole scenario:**
> My Java application runs on a VM and needs to read API keys from Vault. How do I onboard it?

**Kubernetes scenario:**
> I have a Python microservice running in a Kubernetes pod that needs Oracle DB credentials.

**AWS scenario:**
> My application runs on AWS EC2 and needs to read secrets from Vault.

**GitHub Actions scenario:**
> I want to use Vault secrets in my GitHub Actions deployment workflow.

**Troubleshooting:**
> I'm getting permission denied when my app tries to read from Vault. How do I fix it?

**Policy question:**
> What does a Vault policy look like for KV v2?

**Unsupported (should trigger polite refusal):**
> Can I use OIDC auth for my application?

---

## Supported Auth Methods
| Environment | Auth Method |
|---|---|
| VM / Bare Metal | AppRole Auth |
| AWS EC2 / Lambda / ECS | AWS IAM Auth |
| Kubernetes Pod | Kubernetes Auth |
| GitHub Actions | GitHub Auth |

## Supported Secret Engines
| Secret Type | Secret Engine |
|---|---|
| API Keys / Passwords / Tokens | KV Secret Engine |
| Oracle DB credentials | Oracle Database Secret Engine |
| LDAP / Active Directory | LDAP Secret Engine |

---

## Changing the LLM Model

Open `app.py` and change this line:
```python
llm = Ollama(model="llama3.2:3b")
```

To any other model you have pulled in Ollama:
```python
llm = Ollama(model="qwen2.5:3b")
llm = Ollama(model="mistral:7b")
```

---

## Adding More Documentation

1. Add new `.txt` files to the `docs/` folder
2. Re-run `python ingest.py` to rebuild the vector database
3. Restart `python app.py`

---

## Notes for Manager / Deployment

This project is ready to be:
- Wrapped in a Streamlit or FastAPI UI for team use
- Deployed on an internal server with Ollama installed
- Integrated with the internal Vault Ops ticketing/request workflow
- Extended with more docs as the Vault platform grows

Current stack is fully local — no external API calls, no data leaves the machine.
