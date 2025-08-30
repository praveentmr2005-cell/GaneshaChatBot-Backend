# This file should be located at: main/stt.py
import google.generativeai as genai
import os
from dotenv import load_dotenv

# --- Load environment variables from the project root .env file ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Use the same Gemini API Key as your agent ---
API_KEY = os.getenv("GENAI_API_KEY_1") # --- FIX: HARDCODED KEY FOR TESTING ---
if API_KEY:
    genai.configure(api_key=API_KEY)

def transcribe_audio_gemini(file_path: str) -> str:
    """
    Transcribes an audio file using the native Gemini API.

    Args:
        file_path (str): The path to the audio file (.wav).

    Returns:
        str: The transcribed text.
    """
    try:
        if not API_KEY:
            raise ValueError("GENAI_API_KEY not found in environment variables.")

        print("🎙️ Uploading audio to Gemini API for transcription...")
        
        # 1. Upload the audio file to the Gemini File API
        audio_file = genai.upload_file(path=file_path)

        # 2. Initialize the Gemini 1.5 Flash model
        model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

        # 3. Generate content with a prompt and the audio file
        # This tells the model what to do with the audio.
        response = model.generate_content(
            ["Please transcribe the following audio.", audio_file]
        )

        # 4. The transcribed text is in the response
        transcribed_text = response.text.strip()
        print(f"Gemini transcription result: '{transcribed_text}'")

        # Clean up the uploaded file from the server
        genai.delete_file(audio_file.name)

        return transcribed_text

    except Exception as e:
        print(f"An error occurred while calling the Gemini STT API: {e}")
        return ""

if __name__ == "__main__":
    # To test this file directly, create a sample audio file named 'test.wav'
    # in the 'main' directory.
    print("Running Gemini STT test...")
    if os.path.exists("test.wav"):
        transcription = transcribe_audio_gemini("test.wav")
        print(f"\nFinal Transcription: {transcription}")
    else:
        print("Please create a 'test.wav' file in the 'main' directory to run this test.")


