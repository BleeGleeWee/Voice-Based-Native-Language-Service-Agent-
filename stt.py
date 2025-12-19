import os
from groq import Groq

client = Groq(api_key="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")

def transcribe_audio(file_path):
    with open(file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(file_path, file.read()),
            model="whisper-large-v3",
            language="hi" # Change to your chosen language (e.g., 'te', 'hi')
        )
    return transcription.text