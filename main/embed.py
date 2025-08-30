import os
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LORE_DIR = os.path.join(PROJECT_ROOT, "lore")
DB_DIR = os.path.join(PROJECT_ROOT, "chroma_db")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

def build_or_load_db():
    """
    Builds a new ChromaDB database from documents in the LORE_DIR or loads an existing one.
    """
    # Initialize the embedding model
    print("Initializing embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    if os.path.exists(DB_DIR):
        print(f"Loading existing database from {DB_DIR}...")
        vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    else:
        # Build a new database if it doesn't exist
        print(f"Database not found. Building new database from documents in {LORE_DIR}...")
        
        # 1. Load the documents from the 'lores' directory
        loader = DirectoryLoader(LORE_DIR, glob="**/*.txt", show_progress=True)
        documents = loader.load()
        print(f"Loaded {len(documents)} documents.")

        # 2. Split the documents into smaller chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=750, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)
        print(f"Split documents into {len(texts)} chunks.")

        # 3. Create the ChromaDB database with the text chunks
        print("Creating new vector database and embedding chunks...")
        vectordb = Chroma.from_documents(
            documents=texts,
            embedding=embeddings,
            persist_directory=DB_DIR
        )
        print(f"Successfully created and persisted database at {DB_DIR}.")
    return vectordb

if __name__ == "__main__":
    # Run the build/load process
    db = build_or_load_db()

    # --- Test the database with a sample query ---
    print("\n--- Running a test query ---")
    query = "What is the story of how Ganesha broke his tusk?"
    
    # Retrieve the most relevant document chunks
    # k=3 means it will retrieve the top 3 most similar chunks
    results = db.similarity_search(query, k=3)

    if results:
        print(f"Query: '{query}'")
        print("\nFound relevant documents:")
        for i, doc in enumerate(results):
            print(f"\n--- Result {i+1} ---")
            print(f"Source: {os.path.basename(doc.metadata.get('source', 'Unknown'))}")
            print(f"Content: \n{doc.page_content}")
            print("------------------")
    else:
        print("No relevant documents found for the query.")