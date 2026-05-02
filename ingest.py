from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import os

# ── Load all .txt docs from docs/ folder ──────────────────────────────────────
print("Loading documents...")
loader = DirectoryLoader(
    "docs",
    glob="**/*.txt",
    loader_cls=TextLoader
)
documents = loader.load()
print(f"Loaded {len(documents)} documents")

# ── Split into chunks ─────────────────────────────────────────────────────────
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,
    chunk_overlap=80
)
chunks = text_splitter.split_documents(documents)
print(f"Split into {len(chunks)} chunks")

# ── Embeddings ────────────────────────────────────────────────────────────────
print("Loading embedding model...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# ── Build Vector DB ───────────────────────────────────────────────────────────
print("Building vector database...")

# Remove old vector_db if it exists (fresh rebuild)
import shutil
if os.path.exists("vector_db"):
    shutil.rmtree("vector_db")
    print("Removed old vector database")

vectordb = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="vector_db"
)

print("=" * 50)
print(f"Vector database created successfully!")
print(f"Total chunks indexed: {len(chunks)}")
print("Run app.py to start the assistant.")
print("=" * 50)
