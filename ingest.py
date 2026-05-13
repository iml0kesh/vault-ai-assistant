"""
Run this once to build the vector database from docs/.
Re-run whenever you add or update docs.
Usage: python ingest.py
"""
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from config.settings import EMBED_MODEL, VECTOR_DB_PATH, DOCS_PATH
import shutil, os

print("Loading documents...")
loader = DirectoryLoader(DOCS_PATH, glob="**/*.txt", loader_cls=TextLoader)
documents = loader.load()
print(f"  Loaded {len(documents)} documents")

splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=80)
chunks   = splitter.split_documents(documents)
print(f"  Split into {len(chunks)} chunks")

print("Loading embedding model...")
embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

if os.path.exists(VECTOR_DB_PATH):
    shutil.rmtree(VECTOR_DB_PATH)
    print("  Cleared old vector database")

print("Building vector database...")
Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=VECTOR_DB_PATH)

print(f"\n{'='*40}")
print(f"  Done! {len(chunks)} chunks indexed.")
print(f"  Run: python run.py")
print(f"{'='*40}\n")
