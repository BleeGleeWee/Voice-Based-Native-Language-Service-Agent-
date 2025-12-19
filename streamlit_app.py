import streamlit as st
from streamlit_mic_recorder import mic_recorder
from groq import Groq
from state import app  # आपके LangGraph एजेंट का लॉजिक
import io
import base64
from gtts import gTTS

# --- 1. सेशन स्टेट इनिशियलाइजेशन (सबसे ऊपर) ---
# यह एरर रोकने और फीडबैक लूप को नियंत्रित करने के लिए अनिवार्य है
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if "last_played_idx" not in st.session_state:
    st.session_state.last_played_idx = -1 

if "chat_history" not in st.session_state:
    # असिस्टेंट का पहला ग्रीटिंग (Assistant speaks first)
    greeting = "नमस्ते! मैं आपका सरकारी योजना सहायक हूँ। अपनी पात्रता जानने के लिए कृपया अपनी आयु और आय बताएं।"
    st.session_state.chat_history = [{"role": "assistant", "text": greeting}]

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "hi_session_" + str(hash("agentic_hindi"))

# --- 2. UI कॉन्फ़िगरेशन और स्टाइलिंग ---
st.set_page_config(page_title="सरकारी योजना सहायक", layout="centered")

st.markdown("""
    <style>
    .stApp { background: transparent !important; }
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-image: url("https://www.hindustantimes.com/ht-img/img/2024/02/16/1600x900/Cloud-text-of--India--written-in-56-Languages--Int_1708105329979.jpg");
        background-size: cover; filter: blur(10px) brightness(0.15); z-index: -1;
    }
    .chat-container { display: flex; flex-direction: column; gap: 10px; padding: 10px; }
    .bubble { padding: 15px; border-radius: 15px; max-width: 85%; color: white; margin-bottom: 5px; }
    .assistant { background: rgba(255, 75, 75, 0.25); align-self: flex-start; border-left: 5px solid #ff4b4b; }
    .user { background: rgba(255, 255, 255, 0.15); align-self: flex-end; border-right: 5px solid #ddd; text-align: right; }
    .stButton>button { border-radius: 50%; width: 40px; height: 40px; padding: 0; }
    </style>
""", unsafe_allow_html=True)

# Groq क्लाइंट इनिशियलाइजेशन
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. हेल्पर फंक्शन्स ---
def text_to_speech_b64(text):
    """टेक्स्ट को ऑडियो (Base64) में बदलता है"""
    try:
        tts = gTTS(text=text, lang='hi')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return base64.b64encode(fp.getvalue()).decode()
    except Exception:
        return ""

# --- 4. मुख्य इंटरफेस ---
st.title("सरकारी योजना सहायक 🏛️")
st.write("अपनी जानकारी साझा करें और पात्र योजनाएं खोजें।")

# केवल नए असिस्टेंट मैसेज को ऑटोप्ले करें (Feedback loop protection)
current_last_idx = len(st.session_state.chat_history) - 1
if st.session_state.chat_history[-1]["role"] == "assistant" and st.session_state.last_played_idx < current_last_idx:
    audio_b64 = text_to_speech_b64(st.session_state.chat_history[-1]["text"])
    if audio_b64:
        st.markdown(f'<audio autoplay src="data:audio/mp3;base64,{audio_b64}"></audio>', unsafe_allow_html=True)
        st.session_state.last_played_idx = current_last_idx

# चैट हिस्ट्री प्रदर्शित करें (Subtitles style)
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for i, chat in enumerate(st.session_state.chat_history):
    role_class = "assistant" if chat["role"] == "assistant" else "user"
    col1, col2 = st.columns([0.88, 0.12]) if chat["role"] == "assistant" else st.columns([0.12, 0.88])
    
    with (col1 if chat["role"] == "assistant" else col2):
        st.markdown(f'<div class="bubble {role_class}"><b>{"सहायक" if chat["role"] == "assistant" else "आप"}:</b><br>{chat["text"]}</div>', unsafe_allow_html=True)
    
    if chat["role"] == "assistant":
        with col2:
            if st.button("🔊", key=f"btn_{i}"): # Replay icon
                b64 = text_to_speech_b64(chat["text"])
                st.markdown(f'<audio autoplay src="data:audio/mp3;base64,{b64}"></audio>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.write("---")

# --- 5. सुरक्षित वॉइस इनपुट (Voice-first interaction) ---
if not st.session_state.is_processing:
    st.subheader("अपनी आवाज में जानकारी दें:")
    # 'key' को गतिशील बनाया गया है ताकि पुराने इनपुट रिपीट न हों
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
        # A. STT (Hindi Whisper)
        transcription = client.audio.transcriptions.create(
            file=("input.wav", audio_input['bytes']),
            model="whisper-large-v3", 
            language="hi"
        )
        user_text = transcription.text
        st.session_state.chat_history.append({"role": "user", "text": user_text})

        # B. एजेंट रीजनिंग (LangGraph Planner-Executor-Evaluator loop)
        config = {"configurable": {"thread_id": st.session_state.thread_id}, "recursion_limit": 15}
        try:
            # एजेंट खुद तय करेगा कि जानकारी पूरी है या नहीं (Failure Handling)
            result = app.invoke({"messages": [user_text]}, config=config)
            assistant_reply = result["messages"][-1]
            st.session_state.chat_history.append({"role": "assistant", "text": assistant_reply})
        except Exception as e:
            st.error(f"त्रुटि: {e}")
            
    st.session_state.is_processing = False
    st.rerun()