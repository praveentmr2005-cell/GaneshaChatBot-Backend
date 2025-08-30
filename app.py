import subprocess
import os
import uuid
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# --- Add the project's root directory (Backend) to the Python path ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# --- Final, API-driven imports ---
from main.agent import get_ganesh_response, GaneshResponse
from main.tts import speak
from main.stt import transcribe_audio_gemini

app = Flask(__name__)
CORS(app)

# --- In-memory chat history storage ---
chat_histories = {}

# --- Configuration ---
SESSIONS_DIR = os.path.join(PROJECT_ROOT, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
# --- FIX: Define a base URL for constructing full audio URLs ---
BASE_URL = "http://localhost:5000"

def get_session_paths(session_id):
    """Helper function to generate all necessary paths for a given session_id."""
    session_folder = os.path.join(SESSIONS_DIR, session_id)
    paths = {
        "session": session_folder,
        "uploads": os.path.join(session_folder, "uploads"),
        "converted": os.path.join(session_folder, "converted"),
        "audio_out": os.path.join(session_folder, "audio_out")
    }
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    return paths

@app.route("/transcribe", methods=["POST"])
def transcribe():
    try:
        session_id = request.form.get("session_id")
        if not session_id or "audio" not in request.files:
            return jsonify({"error": "session_id and audio file are required"}), 400

        paths = get_session_paths(session_id)
        history = chat_histories.get(session_id, [])

        audio_file = request.files["audio"]
        file_id = str(uuid.uuid4())
        input_path = os.path.join(paths["uploads"], f"{file_id}.webm")
        audio_file.save(input_path)

        # Convert to WAV format for the Gemini API
        wav_path = os.path.join(paths["converted"], f"{file_id}.wav")
        convert_cmd = ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path]
        subprocess.run(convert_cmd, check=True, capture_output=True, text=True)

        # --- Transcription via Gemini API ---
        text = transcribe_audio_gemini(wav_path)
        
        output_audio_path = os.path.join(paths["audio_out"], "output.wav")

        if not text:
            ganesha_response = GaneshResponse(
                lang='en', blessing_open='',
                answer='I am sorry, I could not hear anything in your message. Please speak clearly.',
                blessing_close='', refusal=True, refusal_reason='Empty transcription'
            )
            speak(ganesha_response.answer, ganesha_response.lang, output_audio_path)
        else:
            print(f"[{session_id}] Transcribed: {text}")
            ganesha_response = get_ganesh_response(text, history)
            history.append({"role": "user", "content": text})
            history.append({"role": "ganesha", "content": ganesha_response.to_dict()})
            chat_histories[session_id] = history
            
            res = ganesha_response.blessing_open + ganesha_response.answer + ganesha_response.blessing_close
            speak(res, ganesha_response.lang, output_audio_path)

        return jsonify({
            "id": file_id,
            "transcription": text,
            "ganesha_response": ganesha_response.to_dict(),
            # --- FIX: Use the full, absolute URL for audio playback ---
            "audio_url": f"{BASE_URL}/audio/{session_id}/output.wav"
        })

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "A subprocess (ffmpeg) failed.", "details": e.stderr}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected server error occurred.", "details": str(e)}), 500

@app.route('/audio/<session_id>/<filename>')
def serve_audio(session_id, filename):
    session_audio_path = os.path.join(SESSIONS_DIR, session_id, "audio_out")
    return send_from_directory(session_audio_path, filename)

@app.route('/text-message', methods=['POST'])
def process_text_message():
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        text = data.get("message")
        # --- NEW: Get the speak_response flag from the frontend ---
        speak_response = data.get("speak_response", False)

        if not session_id or not text:
            return jsonify({"error": "session_id and message are required"}), 400

        paths = get_session_paths(session_id)
        history = chat_histories.get(session_id, [])
        
        print(f"[{session_id}] Received text: '{text}' (Speak response: {speak_response})")
        
        ganesha_response = get_ganesh_response(text, history)
        history.append({"role": "user", "content": text})
        history.append({"role": "ganesha", "content": ganesha_response.to_dict()})
        chat_histories[session_id] = history

        audio_url = None
        # --- NEW: Conditionally generate audio based on the flag ---
        if speak_response:
            output_audio_path = os.path.join(paths["audio_out"], "output.wav")
            res = ganesha_response.blessing_open + ganesha_response.answer + ganesha_response.blessing_close
            speak(res, ganesha_response.lang, output_audio_path)
            # --- FIX: Use the full, absolute URL for audio playback ---
            audio_url = f"{BASE_URL}/audio/{session_id}/output.wav"

        return jsonify({
            "id": str(uuid.uuid4()),
            "transcription": text,
            "ganesha_response": ganesha_response.to_dict(),
            "audio_url": audio_url
        })

    except Exception as e:
        return jsonify({"error": "An unexpected server error occurred.", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)

