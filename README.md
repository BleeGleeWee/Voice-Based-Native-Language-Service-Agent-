# Sarkari Yojana Sahayak 🏛️ (Voice-Based Native Language Agent)

🔴 Live Demo: [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://native-lang-agent-ml.streamlit.app/)

**Sarkari Yojana Sahayak** is a voice-first, agentic AI system designed to assist rural users in discovering and applying for government welfare schemes in their native language (Hindi). Unlike simple chatbots, this system uses a **Finite State Machine (FSM)** via LangGraph to guide the user through a structured conversation flow—from eligibility checks to final application—while handling errors, interruptions, and memory context.
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

# 🏗️ System Architecture & Logic Flow

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

### 3. Configure Secrets

Create a file named `.streamlit/secrets.toml` in the root directory.

> **⚠️ Security Warning:** Never upload this file to GitHub. Add it to your `.gitignore`.

```toml
GROQ_API_KEY = "your_groq_api_key_here"

```

### 4. Run the Application

```bash
streamlit run streamlit_app.py

```

## 📂 Project Structure

* `streamlit_app.py`: Main entry point. Handles UI, Voice Recording, and Edge-TTS playback.
* `state.py`: The brain of the agent. Contains LangGraph nodes, State definition, and LLM prompts.
* `schemes.json`: Database containing scheme rules, descriptions, and application links.
* `stt.py`: Helper module for handling Audio transcription via Whisper.
* `requirements.txt`: List of dependencies.

---
Built this project for CredResolve Job(Role - AI/ML Engg) Assignment!
