"""
RAG setup — vector store + embeddings + LLM.
Loaded once at startup.
"""
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_core.output_parsers import StrOutputParser
from config.settings import LLM_MODEL, EMBED_MODEL, VECTOR_DB_PATH, RETRIEVER_K


embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
vectordb   = Chroma(persist_directory=VECTOR_DB_PATH, embedding_function=embeddings)
retriever  = vectordb.as_retriever(search_kwargs={"k": RETRIEVER_K})
llm        = OllamaLLM(model=LLM_MODEL)


def get_context(query: str) -> str:
    """Retrieve relevant doc chunks for a query."""
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)


def ask(prompt: str) -> str:
    """Send a prompt to the LLM and return the response."""
    return StrOutputParser().invoke(llm.invoke(prompt))
