import os
import sounddevice as sd
from scipy.io.wavfile import write
from gtts import gTTS
from groq import Groq
from state import app  # Ensure state.py is in the same folder

# Initialize Groq for STT
client = Groq(api_key="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")

# --- 1. VOICE INPUT (Live Recording) ---
def record_audio(filename="input.wav", duration=6):
    fs = 44100
    print(f"\n--- बोलना शुरू करें ({duration} सेकंड) ---")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    write(filename, fs, recording)
    print("--- रिकॉर्डिंग पूरी हुई। ---")

def transcribe_voice(file_path):
    """Whisper set to Hindi ('hi')"""
    print("--- ट्रांसक्राइब किया जा रहा है... ---")
    try:
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3",
                language="hi"
            )
        return transcription.text
    except Exception as e:
        print(f"STT Error: {e}")
        return ""

# --- 2. VOICE OUTPUT (TTS) ---
def speak_native(text):
    """Converts agent response text to hindi audio and plays it"""
    if not text: return
    print(f"\nAssistant: {text}")
    tts = gTTS(text=text, lang='hi')
    tts.save("response.mp3")
    # Windows command to play audio. 
    # Use 'afplay response.mp3' for Mac or 'mpg123 response.mp3' for Linux
    os.system("start response.mp3")

# --- 3. THE EXECUTION LOOP ---
def run_voice_assistant():
    # thread_id maintains the 'Memory' of the conversation across turns
    config = {"configurable": {"thread_id": "user_session_001"}}

    # STEP 1: Capture live voice
    record_audio("input.wav")

# STEP 2: Convert voice to hindi text
    user_text = transcribe_voice("input.wav")
    if not user_text:
        print("कुछ भी सुनाई नहीं दिया। कृपया फिर से प्रयास करें।")
        return
    print(f"उपयोगकर्ता: {user_text}")

    # STEP 3: Pass text to LangGraph Agent
    # The agent handles Planner -> Executor -> Evaluator
    # We pass 'messages' to maintain the chat history
    inputs = {
        "messages": [user_text],
        "user_info": {"age": 65, "income": 50000} # Hardcoded for demo; Planner updates this
    }

    print("--- एजेंट विचार कर रहा है (Agent Reasoning)... ---")
    try:
        final_state = app.invoke(inputs, config=config)

        # STEP 4: Get the final response from the messages list
        # LangGraph appends the new response to the end of the list
        assistant_response = final_state["messages"][-1]
        
        # STEP 5: Play the Hindi response
        speak_native(assistant_response)

        # DEBUG: Print found schemes if they exist
        if final_state.get("eligible_schemes"):
            print(f"\nपात्र योजनाएं मिलीं: {final_state['eligible_schemes']}")
            
    except Exception as e:
        print(f"Graph Error: {e}")

if __name__ == "__main__":
    run_voice_assistant()





