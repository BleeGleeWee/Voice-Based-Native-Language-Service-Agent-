import os
import io
from groq import Groq

def transcribe_audio(audio_input, api_key):
    """
    Transcribes audio from either a file path OR raw bytes (from Streamlit).
    """
    client = Groq(api_key="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")
    
    # 1. If input is a file path (string), read it
    if isinstance(audio_input, str):
        if not os.path.exists(audio_input):
            return "Error: File not found."
        with open(audio_input, "rb") as f:
            file_tuple = (os.path.basename(audio_input), f.read())
            
    # 2. If input is raw bytes (from Streamlit mic_recorder)
    else:
        # Groq needs a filename to know the format, we give it a dummy name "audio.wav"
        file_tuple = ("audio.wav", audio_input)

    try:
        transcription = client.audio.transcriptions.create(
            file=file_tuple,
            model="whisper-large-v3",
            language="hi",
            temperature=0.0
        )
        return transcription.text
    except Exception as e:
        return f"Error during transcription: {str(e)}"