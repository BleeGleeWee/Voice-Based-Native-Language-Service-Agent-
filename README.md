# सरकारी योजना सहायक 🏛️ (Hindi Agent)

🔴 Live Demo: [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://native-lang-agent-ml.streamlit.app/)

**Sarkari Yojana Sahayak** is a voice-first, agentic AI system designed to assist rural users in discovering and applying for government welfare schemes in their native language (Hindi). Unlike simple chatbots, this system uses a **Finite State Machine (FSM)** via LangGraph to guide the user through a structured conversation flow—from eligibility checks to final application—while handling errors, interruptions, and memory context.


## 🚀 Key Features
* **🎙️ Voice-First Interface:** Complete hands-free experience. The user speaks in Hindi, and the agent replies with a natural, human-like male voice (using Microsoft Edge Neural TTS).
* **🧠 Agentic Workflow:** Powered by **LangGraph**, the system moves through distinct logical stages (Greeting → Data Collection → Scheme Presentation → Application).
* **💾 Contextual Memory:** The agent remembers critical user details (Age, Income) across multiple conversation turns.
* **🛡️ Robust Failure Handling:** Automatically detects silence (e.g., phantom "Kar do" inputs from Whisper), handles nonsense queries, and politely guides the user back to the correct flow.
* **🔗 Deep Linking:** Provides direct, clickable application links to official government portals upon user request.

## 🛠️ Tech Stack
* **Frontend:** Streamlit, Streamlit-Mic-Recorder
* **Orchestration:** LangGraph (State Machine & Graph Theory)
* **LLM:** Llama-3.3-70b-Versatile (via Groq API)
* **Speech-to-Text (STT):** Whisper-Large-v3 (via Groq)
* **Text-to-Speech (TTS):** Microsoft Edge-TTS (`hi-IN-MadhurNeural`)
* **Data Source:** JSON-based local scheme database (`schemes.json`)

---

# System Architecture & Logic Flow

The **Sarkari Yojana Sahayak** is not a simple chatbot. It is a state-aware agent designed on the **Planner-Evaluator-Executor** architecture. It uses a **Finite State Machine (FSM)** implemented via **LangGraph** to ensure deterministic reliability while maintaining the flexibility of an LLM.

---

## 1. Agentic Lifecycle (Planner-Evaluator-Executor)
This diagram illustrates the core cognitive loop of the agent. Unlike a standard RAG pipeline, this system evaluates its own outputs before speaking to the user.

<div align="center">
  <img width="784" height="1136" alt="Agent Lifecycle" src="https://github.com/user-attachments/assets/2647733a-bec5-4de5-b17d-6d9be5675076" />

</div>

### **How it Works:**
1.  **Planner (Perception):** The agent listens to the audio, transcribes it, and identifies the user's **Intent** (e.g., "Giving Income Info") and extracts **Entities** (Age: 25, Income: 20k).
2.  **Executor (Action):** Based on the plan, it executes tools—specifically querying the `schemes.json` database or updating the session memory.
3.  **Evaluator (Logic Check):** Before responding, the agent checks:
    * *Did I get the necessary data?* (If not, ask follow-up).
    * *Is the data valid?* (If age is 200, reject it).
    * *Did the tool return results?* (If yes, present schemes).

---

## 2. LangGraph Component Design
This diagram visualizes the internal code structure within `state.py`. It shows how the **Analyzer Node** (LLM) hands off control to the **Decision Node** (Python Logic) to ensure accurate scheme retrieval.

<div align="center">
  <img width="784" height="861" alt="Lang-Graph" src="https://github.com/user-attachments/assets/49be57db-b059-4d23-b78c-0ef0388fcb90" />

</div>

### **Key Components:**
* **Analyzer Node:** Uses `Llama-3-70b` to understand context and nuance (e.g., correcting "PM Yashwag" to "PM Yashasvi").
* **Decision Node:** A rigid rule engine that enforces business logic. It prevents the LLM from hallucinating fake schemes.
* **State Memory:** Persists user data (Age/Income) across multiple conversation turns so the user doesn't have to repeat themselves.

---

## 3. Conversation Logic Flowchart
The agent follows a strict **Depth-Layered Conversation Flow**. This ensures users are guided step-by-step from greeting to application without getting lost.

<div align="center">
  <img width="784" height="1816" alt="Conversation Flow" src="https://github.com/user-attachments/assets/9dccb18d-11c3-4b26-80ca-eb1969f98485" />
</div>

### **Depth Layers:**
* **Layer 0 (Start):** User must initiate with keywords like "Shuru" or "Start".
* **Layer 1 (Data Collection):** The agent insists on getting valid Age and Income before proceeding.
* **Layer 2 (Scheme Presentation):** Eligible schemes are listed point-wise.
* **Layer 3 (Detail & Application):** Deep linking to government portals (`.gov.in`) upon user request.
* **Error Handling:** If the user stays silent or speaks nonsense, the agent attempts to realign the conversation twice before politely ending it.
---


# 💬 Sample Conversation Log
```
User: "नमस्ते" (Namaste)
Agent: "नमस्ते, आशा करता हूँ आपका दिन अच्छा जा रहा है |" (Status: ✅ Greeting Intent Detected)

User: "मुझे आईस्क्रिम खाना है" (I want to eat ice cream)
Agent: "क्षमा करें, मैं केवल सरकारी योजनाओं में आपकी सहायता कर सकता हूँ।" (Status: 🛡️ Irrelevant Input Rejected)

User: "मेरी उम्र 120 साल है..." (My age is 120...)
Agent: "मनुष्य का औसत जीवनकाल 90 साल होता है, कृपया मुझे अपनी सही उम्र बताएं" (Status: 🛡️ Logic Guardrail - Biological Impossibility Rejected)

User: "अच्छा, मेरी उम्र 15 साल है" (Okay, my age is 15)
Agent: "सही योजना खोजने के लिए मुझे आपकी उम्र और आय दोनों की आवश्यकता होगी |" (Status: 🧠 Memory - Retained Age, Planner requested missing Income)

User: "मेरी आय 5000 है" (My income is 5000)
Agent: "आपकी जानकारी के आधार पर, आप निम्नलिखित योजनाओं के लिए पात्र हैं:-
1. अल्पसंख्यक प्री-मैट्रिक छात्रवृत्ति
2. पीएम यशस्वी छात्रवृत्ति योजना..." (Status: 🛠️ Tool Call - Database Search Executed)

User: "पियन यशाश्री चात्रपृत्त योजना" (Mispronounced Scheme Name)
Agent: "पीएम यशस्वी छात्रवृत्ति योजना: OBC, EBC और DNT श्रेणी के मेधावी छात्रों के लिए उच्च स्तरीय शिक्षा छात्रवृत्ति। क्या आप आवेदन करना चाहते हैं?" (Status: 🤖 AI Reasoning - Fuzzy Matching Corrected 'Pian Yashashri' to 'PM Yashasvi')

User: (Silence/Background Noise detected as text"कर दो" )
Agent: "माफ़ करें, मैं आपको समझ नहीं पाया। क्या आप कृपया फिर से दोहरा सकते हैं?" (Status: 🔁 Failure Handling - Null/Ambiguous Input Detected)

User: "जी हाँ" (Yes)
Agent: "बढ़िया! आप इस लिंक पर जाकर आवेदन कर सकते हैं: [यहाँ क्लिक करें]" (Status: 🛠️ Tool Call - Application Link Retrieved)

```

---

## ⚙️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/BleeGleeWee/Voice-Based-Native-Language-Service-Agent-
cd Voice-Based-Native-Language-Service-Agent-

```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

```

### 3. Windows Virtual Environment setup (py version 3.10.11)

```bash
python -m venv agent_env

```

### 4. Activate the virtual environment

```bash
agent_env\Scripts\activate

```

### 5. Configure Secrets

Create a file named `.streamlit/secrets.toml` in the root directory.

> **⚠️ Security Warning:** Never upload this file to GitHub. Add it to your `.gitignore`.

```toml
GROQ_API_KEY = "your_groq_api_key_here"

```

### 6. Run the Application

```bash
streamlit run streamlit_app.py

```
---
## Repo - Structure
```
Sarkari-Yojana-Sahayak/
├── .streamlit/
│   └── secrets.toml       # API keys configuration (NOT pushed to GitHub)
├── schemes.json           # Knowledge Base (Eligibility Rules & Data)
├── state.py               # Core Agent Logic (LangGraph State Machine)
├── streamlit_app.py       # Frontend Interface (UI, Audio I/O)
├── stt.py                 # Speech-to-Text Utility
├── requirements.txt       # Project Dependencies
└── README.md              # Documentation
```
---
Built this project for CredResolve Job(Role - AI/ML Engg) Assignment!
