import streamlit as st
from streamlit_mic_recorder import mic_recorder
from state import app  # Importing the logic from your state.py file
import base64
import edge_tts
import asyncio
import re
import uuid   
from stt import transcribe_audio

# --- 1. SETUP & SESSION STATE ---
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if "last_played_idx" not in st.session_state:
    st.session_state.last_played_idx = -1 

if "app_started" not in st.session_state:
    st.session_state.app_started = False

# Define Greeting Text (Strictly from Requirement 0)
greeting_text = "नमस्ते! मैं आपका सरकारी योजना सहायक हूँ। बताइए मैं आपकी कैसे मदद कर सकता हूँ?"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "text": greeting_text}]

if "thread_id" not in st.session_state:
    # Unique ID per session to maintain independent memory
    st.session_state.thread_id = f"session_{str(uuid.uuid4())}"

# --- 2. DYNAMIC UI CONFIGURATION ---
st.set_page_config(page_title="सरकारी योजना सहायक", layout="centered")

if not st.session_state.app_started:
    # --- START SCREEN CSS ---
    bg_filter = "brightness(0.3)" 
    
    button_style = """
    .stButton>button { 
        background-color: black !important; 
        color: white !important; 
        border-radius: 30px; 
        border: 2px solid white;
        padding: 15px 40px;
        font-size: 20px;
        box-shadow: 0px 4px 15px rgba(255,255,255,0.2);
        margin-top: 20px;
    }
    .stButton>button:hover { 
        background-color: #333 !important; 
        transform: scale(1.05);
        border-color: #FFD700;
        color: #FFD700 !important;
    }
    """
else:
    # --- MAIN APP CSS ---
    bg_filter = "blur(8px) brightness(0.4)" 
    button_style = """
    .stButton>button { 
        border-radius: 50%; 
        width: 40px; 
        height: 40px; 
        padding: 0; 
        background-color: rgba(255,255,255,0.9); 
        color: black; 
        border: none; 
    }
    .stButton>button:hover { background-color: #FFD700; }
    """

st.markdown(f"""
    <style>
    .stApp {{ background: transparent !important; }}
    .stApp::before {{
        content: ""; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-image: url("https://www.hindustantimes.com/ht-img/img/2024/02/16/1600x900/Cloud-text-of--India--written-in-56-Languages--Int_1708105329979.jpg");
        background-size: cover; 
        filter: {bg_filter}; 
        transition: filter 0.8s ease-in-out; 
        z-index: -1;
    }}
    
    .chat-container {{ display: flex; flex-direction: column; gap: 10px; padding: 10px; }}
    .bubble {{ padding: 15px; border-radius: 15px; max-width: 85%; color: white; margin-bottom: 5px; font-size: 16px; }}
    
    .assistant {{ 
        background: rgba(220, 20, 60, 0.25); 
        align-self: flex-start; 
        border-left: 5px solid #ff4b4b; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        backdrop-filter: blur(2px);
    }}
    
    .user {{ background: rgba(0, 0, 0, 0.6); align-self: flex-end; border-right: 5px solid #ddd; text-align: right; box-shadow: 2px 2px 10px rgba(0,0,0,0.3); }}
    
    /* Inject Dynamic Button Styles */
    {button_style}
    
    .start-container {{ 
        display: flex; 
        flex-direction: column;
        align-items: center; 
        width: 100%;
    }}
    
    .spacer {{
        height: 30vh; 
    }}
    
    h1 {{ text-shadow: 2px 2px 8px #000000; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---

def format_message(text):
    # Converts Markdown links to HTML with gold styling
    text = re.sub(
        r'\[(.*?)\]\((.*?)\)', 
        r'<a href="\2" target="_blank" style="color: #FFD700; text-decoration: underline; font-weight: bold;">\1</a>', 
        text
    )
    text = text.replace('\n', '<br>')
    return text

async def edge_tts_generate(text, filename):
    communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural")
    await communicate.save(filename)

def text_to_speech_b64(text):
    # Cleans text of markdown/HTML before speaking
    clean_text = re.sub(r'<.*?>', '', text)        
    clean_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_text)
    clean_text = clean_text.replace("*", "")       
    clean_text = clean_text.replace("#", "")       
    clean_text = clean_text.strip()
    
    temp_file = "temp_audio.mp3"
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(edge_tts_generate(clean_text, temp_file))
        
        with open(temp_file, "rb") as f:
            audio_bytes = f.read()
            
        return base64.b64encode(audio_bytes).decode()
        
    except Exception:
        return ""

# --- 4. MAIN LOGIC ---

# A. START SCREEN
if not st.session_state.app_started:
    st.markdown("<div class='start-container'>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: white; font-size: 3.5rem; margin-top: 50px;'>सरकारी योजना सहायक 🏛️</h1>", unsafe_allow_html=True)
    st.markdown("<div class='spacer'></div>", unsafe_allow_html=True)
    st.write("") 
    if st.button("सहायक शुरू करें"):
        st.session_state.app_started = True
        st.rerun()
        
    st.markdown("</div>", unsafe_allow_html=True)

# B. MAIN CHAT APP
else:
    st.title("सरकारी योजना सहायक 🏛️")

    # --- AUTOPLAY LOGIC ---
    current_last_idx = len(st.session_state.chat_history) - 1
    if st.session_state.chat_history[-1]["role"] == "assistant" and st.session_state.last_played_idx < current_last_idx:
        text_to_speak = st.session_state.chat_history[-1]["text"]
        audio_b64 = text_to_speech_b64(text_to_speak)
        if audio_b64:
            autoplay_html = f"""
                <audio autoplay="autoplay">
                <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
                </audio>
            """
            st.markdown(autoplay_html, unsafe_allow_html=True)
            st.session_state.last_played_idx = current_last_idx

    # --- CHAT DISPLAY ---
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for i, chat in enumerate(st.session_state.chat_history):
        role_class = "assistant" if chat["role"] == "assistant" else "user"
        col1, col2 = st.columns([0.88, 0.12]) if chat["role"] == "assistant" else st.columns([0.12, 0.88])
        
        with (col1 if chat["role"] == "assistant" else col2):
            formatted_text = format_message(chat["text"])
            st.markdown(
                f'<div class="bubble {role_class}">'
                f'<b>{"सहायक" if chat["role"] == "assistant" else "आप"}:</b><br>'
                f'{formatted_text}'
                f'</div>', 
                unsafe_allow_html=True
            )
        
        if chat["role"] == "assistant":
            with col2:
                if st.button("🔊", key=f"btn_{i}"):
                    b64 = text_to_speech_b64(chat["text"])
                    st.markdown(f'<audio autoplay src="data:audio/mp3;base64,{b64}"></audio>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("---")

    # --- VOICE INPUT ---
    if not st.session_state.is_processing:
        st.subheader("अपनी आवाज में जानकारी दें:")
        audio_input = mic_recorder(
            start_prompt="बोलना शुरू करें 🎤", 
            stop_prompt="रोकें 🛑", 
            key=f"rec_{len(st.session_state.chat_history)}" 
        )
    else:
        st.info("⌛ सहायक विचार कर रहा है... कृपया प्रतीक्षा करें।")
        audio_input = None

    if audio_input:
        st.session_state.is_processing = True
        with st.spinner("पहचाना जा रहा है..."):
            try:
                # 1. Transcribe Audio
                user_text = transcribe_audio(audio_input['bytes'], st.secrets["GROQ_API_KEY"])
                
                # 2. Handle Silence/Errors
                if not user_text.strip() or "Error" in user_text: 
                    user_text = "..." 
                
                # 3. Append User Message
                st.session_state.chat_history.append({"role": "user", "text": user_text})

                # 4. Invoke Agent Logic (state.py)
                config = {"configurable": {"thread_id": st.session_state.thread_id}, "recursion_limit": 10}
                result = app.invoke({"messages": [user_text]}, config=config)
                
                # 5. Append Assistant Response
                if result and "messages" in result:
                    st.session_state.chat_history.append({"role": "assistant", "text": result["messages"][-1]})
                else:
                    st.session_state.chat_history.append({"role": "assistant", "text": "तकनीकी त्रुटि। कृपया पुनः प्रयास करें।"})

            except Exception as e:
                st.error(f"System Error: {str(e)}")
                
        st.session_state.is_processing = False
        st.rerun()
