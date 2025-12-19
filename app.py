import os
from state import app  # Assuming the graph is in state.py
from main import record_audio, transcribe_voice, speak_native

def start_government_assistant():
    # thread_id is mandatory for Conversation Memory
    config = {"configurable": {"thread_id": "unique_user_session_101"}}
    
    print("सरकारी योजना सहायक (Hindi Gov Scheme Assistant)")
    
    while True:
        # 1. Capture Voice
        record_audio("input.wav", duration=5)
        
        # 2. Transcription (STT)
        user_text = transcribe_voice("input.wav")
        if not user_text.strip():
            print("खाली इनपुट मिला। कृपया फिर से प्रयास करें।")
            continue
            
        print(f"User: {user_text}")
        if "रोकें" in user_text or "बंद करें" in user_text: break # Exit keywords

        # 3. Process with LangGraph (Memory is handled by thread_id)
        # Note: We don't need to re-pass user_info; the checkpointer remembers it!
        final_state = app.invoke(
            {"messages": [user_text]}, 
            config=config
        )

        # 4. Output Response (TTS)
        assistant_reply = final_state["messages"][-1]
        speak_native(assistant_reply)

        # 5. Result Display
        if final_state.get("eligible_schemes"):
            print(f"पात्र योजनाएं: {final_state['eligible_schemes']}")

if __name__ == "__main__":
    start_government_assistant()