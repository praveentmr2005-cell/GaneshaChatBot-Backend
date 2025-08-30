# This file should be located at: main/agent.py
import os
import re
import sys
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List, Dict

# --- FIX: Add the project's root directory (Backend) to the Python path ---
# This ensures that absolute imports from 'main' work reliably.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# It's good practice to handle potential import errors for genai
try:
    import google.generativeai as genai
except ImportError:
    print("Error: The 'google-generativeai' package is not installed. Please install it using 'pip install google-generativeai'")
    genai = None

# Use new import paths for LangChain components
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# --- FIX: Use absolute imports from the 'main' package ---
# Now that the project root is on the path, these imports will work.
from .prompt import prompt as main_prompt
from .prompt_classifier import prompt as classifier_prompt

# --- Configuration ---
load_dotenv()

# --- RAG Setup: Load the Vector Database ---
# The path to the DB should be constructed from the main folder
DB_DIR = os.path.join(PROJECT_ROOT, "main", "chroma_db")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

print("RAG Agent: Initializing embeddings...")
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

print(f"RAG Agent: Loading vector database from {DB_DIR}...")
vector_db = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
print("RAG Agent: Database loaded successfully.")

# --- Initialize the language model client ---
client = None
if genai:
    try:
        print("Loading GenAI model...")
        genai.configure(api_key=os.getenv("GENAI_API_KEY"))
        client = genai.GenerativeModel('gemini-1.5-flash-latest')
        print("GenAI model client initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize GenAI client: {e}")
else:
    print("GenAI client could not be initialized because the package is missing.")


# --- Define the response structure using Pydantic ---
class GaneshResponse(BaseModel):
    lang: str
    blessing_open: str
    answer: str
    blessing_close: str
    refusal: bool = False
    refusal_reason: Optional[str] = ""

    def to_dict(self):
        """Converts the Pydantic model to a JSON-serializable dictionary."""
        return self.model_dump()

# --- Main function to get the RAG-powered and conversation-aware response ---
def get_ganesh_response(user_input: str, history: List[Dict] = None) -> GaneshResponse:
    if history is None:
        history = []

    if not client:
        return GaneshResponse(
            lang='en', blessing_open='',
            answer='I apologize, my connection to the divine consciousness is currently unavailable. Please try again later.',
            blessing_close='', refusal=True, refusal_reason='LLM client not loaded'
        )
    
    # --- 1. LLM ROUTER: Classify the user's intent first ---
    print(f"Agent received text: '{user_input}'")
    classifier_full_prompt = classifier_prompt.format(question=user_input)
    
    try:
        response = client.generate_content(classifier_full_prompt)
        classification = response.text.strip().upper()
        print(f"Classification result: '{classification}'")
        
        if classification not in ['YES', 'NO']:
            print(f"Unexpected classification result: '{classification}'. Defaulting to refusal.")
            classification = 'NO'
            
    except Exception as e:
        print(f"Error during classification: {e}. Defaulting to refusal.")
        classification = 'NO'

    if classification == 'NO':
        return GaneshResponse(
            lang='en', blessing_open='',
            answer="My child, my wisdom is for matters of the spirit. Your question seems to be outside this realm. Please ask about life's obstacles, wisdom, or our sacred traditions.",
            blessing_close='May you find the guidance you seek.', refusal=True, refusal_reason='Inappropriate topic classified by router'
        )

    # --- 2. CONVERSATIONAL RAG: Use history to improve retrieval ---
    print("Classification approved. Proceeding with RAG workflow...")
    
    recent_history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]])
    search_query = f"{recent_history_text}\n\nuser: {user_input}"
    
    print("RAG Step 1: Retrieving context from database with conversational query...")
    docs = vector_db.similarity_search(search_query, k=3)
    static_context = "\n\n".join([doc.page_content for doc in docs])
    print(f"RAG Step 1: Found {len(docs)} relevant document chunks.")

    # --- 3. AUGMENT PROMPT: Combine static docs and chat history ---
    formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-6:]])
    
    final_prompt = main_prompt.format(
        context=static_context,
        history=formatted_history,
        question=user_input
    )
    
    # --- 4. GENERATE RESPONSE from the main model ---
    print("RAG Step 2: Generating final response from LLM...")
    try:
        response = client.generate_content(final_prompt)
        raw_response_text = response.text
        
        json_start = raw_response_text.find('{')
        json_end = raw_response_text.rfind('}') + 1
        
        if json_start != -1 and json_end != 0:
            json_string = raw_response_text[json_start:json_end]
            sanitized_json_string = re.sub(r'[\x00-\x1f]', '', json_string)
            parsed_data = GaneshResponse.model_validate_json(sanitized_json_string)
        else:
            raise ValueError("No JSON object found in the LLM response.")
            
    except Exception as e:
        print(f"Failed to generate or parse LLM response. Error: {e}")
        parsed_data = GaneshResponse(
            lang='en', blessing_open='',
            answer="I heard your words, but my thoughts are unclear at this moment. Please rephrase your question, and I shall try again to offer guidance.",
            blessing_close='', refusal=True, refusal_reason=f'LLM call or JSON parsing failed: {str(e)}'
        )
    
    return parsed_data
