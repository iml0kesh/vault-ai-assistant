from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# ── Embeddings ────────────────────────────────────────────────────────────────
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# ── Load Vector DB ────────────────────────────────────────────────────────────
vectordb = Chroma(
    persist_directory="vector_db",
    embedding_function=embeddings
)

retriever = vectordb.as_retriever(
    search_kwargs={"k": 5}
)

# ── Local LLM (lightweight + fast) ───────────────────────────────────────────
# Recommended models (pick one based on your machine):
#   llama3.2:3b  → fastest, lowest RAM (~2GB)  ← DEFAULT
#   qwen2.5:3b   → good alternative, fast
#   mistral:7b   → better quality, needs ~5GB RAM
llm = OllamaLLM(model="llama3.2:3b")

# ── Enterprise System Prompt ──────────────────────────────────────────────────
# NOTE: Curly braces that are NOT template variables must be doubled {{ }}
# so LangChain does not try to parse them as variables.
SYSTEM_PROMPT = """You are an enterprise HashiCorp Vault Self-Service Assistant.
You behave like a senior internal Vault onboarding engineer.
Answer ONLY from the documentation context provided below. Do not use outside knowledge.

SUPPORTED AUTH METHODS (never recommend others):
- AppRole Auth           -> for VM / Bare Metal / Traditional apps
- AWS IAM Auth           -> for AWS EC2 / Lambda / ECS workloads
- Kubernetes Auth        -> for Kubernetes pods / containers
- GitHub Auth            -> for GitHub Actions / CI/CD workflows

SUPPORTED SECRET ENGINES (never recommend others):
- KV Secret Engine              -> for API keys / passwords / static credentials
- Oracle Database Secret Engine -> for Oracle DB dynamic credentials
- LDAP Secret Engine            -> for LDAP / Active Directory credentials

STRICT RULES:
- Never recommend unsupported auth methods or secret engines.
- Never hallucinate. Only use the context provided.
- If the use case is not supported, reply EXACTLY:
  "This use case is not currently supported by the Vault self-service platform. A Vault engineer will get in touch with you shortly."

HOW TO RESPOND - read the question type carefully:

TYPE 1 - INFORMATIONAL QUESTION
  Examples: "What is AppRole?", "How does Kubernetes auth work?", "What is KV v2?"
  -> Answer the question clearly and concisely from the context.
  -> Do NOT use the onboarding format. Just explain it well.

TYPE 2 - TROUBLESHOOTING QUESTION
  Examples: "I'm getting permission denied", "AppRole login is failing", "Secret not found"
  -> Explain the likely cause and the exact fix from the context.
  -> Do NOT use the onboarding format.

TYPE 3 - ONBOARDING REQUEST (user describes their app and environment)
  Examples: "My Java app on a VM needs Oracle DB credentials", "I have a K8s pod that needs API keys"
  -> Use this EXACT format:

Recommended Authentication Method: <method>
Recommended Secret Engine: <engine>

Onboarding Plan:
1. <step>
2. <step>
3. <step>
4. <step>

Required Inputs:
- Application Name
- Environment (dev / qa / prod)
- Namespace
- Secret Path
- Required Access

Vault Policy Example:
path "<secret-path>" {{ capabilities = ["read"] }}

Best Practices:
- <practice>
- <practice>

TYPE 4 - MISSING INFORMATION
  If the user needs Vault help but has not told you their platform or secret type:
  -> Ask 1-2 specific follow-up questions to determine the right auth method and secret engine.
  -> Do NOT guess.
"""

# ── Prompt Template ───────────────────────────────────────────────────────────
prompt = ChatPromptTemplate.from_template(
    SYSTEM_PROMPT + """
---
Context (Vault documentation):
{context}

User Question: {question}

Answer:"""
)

# ── Format Retrieved Docs ─────────────────────────────────────────────────────
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# ── RAG Chain ─────────────────────────────────────────────────────────────────
rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

# ── Main Loop ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("  Vault Self-Service Assistant - Ready")
print("  Model : llama3.2:3b (local)")
print("  Type  : 'exit' to quit")
print("=" * 60)

while True:
    print()
    query = input("Your Question: ").strip()

    if not query:
        continue

    if query.lower() == "exit":
        print("Goodbye.")
        break

    print("\nThinking...\n")
    result = rag_chain.invoke(query)

    print("-" * 60)
    print(result)
    print("-" * 60)