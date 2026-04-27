from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Load vector DB
vectordb = Chroma(
    persist_directory="vector_db",
    embedding_function=embeddings
)

retriever = vectordb.as_retriever()

# Local model
llm = Ollama(model="qwen35")

# Prompt
prompt = ChatPromptTemplate.from_template("""
You are a helpful HashiCorp Vault assistant.

Use the provided context to answer the question.

Context:
{context}

Question:
{question}
""")

# Format retrieved docs
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Modern RAG chain
rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

print("Vault Assistant Ready")

while True:
    query = input("Ask Vault Question: ")

    if query.lower() == "exit":
        break

    result = rag_chain.invoke(query)

    print("\nAnswer:")
    print(result)
    print("\n")