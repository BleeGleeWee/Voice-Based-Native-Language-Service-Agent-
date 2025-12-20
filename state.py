import json
import operator
import streamlit as st
from typing import Annotated, TypedDict, List
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

# --- 1. CONFIG & SETUP ---
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=st.secrets["GROQ_API_KEY"],
    temperature=0
)

# --- 2. STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    user_info: dict          # stores age, income
    eligible_schemes: List[dict] # stores full scheme objects
    selected_scheme: dict    # currently discussed scheme
    stage: str               # "intro", "collecting_info", "schemes_presented", "scheme_detail"
    current_intent: str      # intent detected by LLM

# --- 3. TOOLS ---

def search_schemes_tool():
    """Tool 1: Eligibility Engine - Scans database for matching schemes."""
    try:
        with open("schemes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def get_application_link_tool(scheme_data: dict):
    """Tool 2: Retrieval System - Fetches the application URL and details."""
    return scheme_data.get('link', '#')

# --- 4. NODES ---

def analyzer_node(state: AgentState):
    """
    Core Intelligence: Hybrid approach (Keywords + LLM with Fuzzy Logic).
    """
    # 1. Safely extract text
    last_msg = state["messages"][-1]
    last_message = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    text_lower = last_message.lower().strip()

    # 2. Context Data
    current_stage = state.get("stage", "intro")
    user_info = state.get("user_info", {})
    eligible_schemes_list = [s['name_hi'] for s in state.get("eligible_schemes", [])]

    # --- RULE LAYER 1: Hallucination Check ---
    if not text_lower or "कर दो" in text_lower:
        return {"current_intent": "null_input"}

    # --- RULE LAYER 2: Hardcoded Keywords (GLOBAL INTERRUPTS) ---
    # FIX: We allow greetings/reset checks at ANY stage now.
    
    greeting_keywords = ["नमस्ते", "namaste", "hello", "hi", "hey", "pranam"]
    if any(word in text_lower for word in greeting_keywords):
        return {"current_intent": "greeting"}

    start_keywords = ["शुरू", "start", "kya bolna", "kya karna", "kaise", "मदद", "help", "reset"]
    # We check if they are NOT trying to give data (age/income)
    if any(word in text_lower for word in start_keywords) and "age" not in text_lower and "income" not in text_lower:
        return {"current_intent": "query_start"}

    # Explicit Denials
    deny_keywords = ["nahi", "no", "rehne do", "nhi", "na"]
    if text_lower in deny_keywords: 
        return {"current_intent": "deny_apply"}

    # --- AI LAYER 3: LLM Analysis (Smart Fuzzy Matching) ---
    prompt = f"""
    You are the brain of 'Sarkari Yojana Sahayak'. Analyze the Hindi input.
    
    Current Stage: {current_stage}
    User Data: Age={user_info.get('age')}, Income={user_info.get('income')}
    
    **AVAILABLE SCHEMES LIST**: {eligible_schemes_list}

    Classify user input into exactly one INTENT:
    1. 'provide_info' : Contains Age (number) OR Income (number).
    2. 'ask_all_details' : "Schemes ke baare me batao", "Benefits kya hai".
    3. 'select_scheme' : User is trying to name a scheme. **FUZZY MATCHING REQUIRED**: If the user says "PM Yashashwag" or "Pre metric", match it to the closest name in the AVAILABLE SCHEMES LIST.
    4. 'confirm_apply' : "Ha", "Yes", "Apply karna hai", "Aavedan".
    5. 'deny_apply' : "Nahi", "No".
    6. 'irrelevant' : Weather, Jokes, Food, Politics (Ice cream, Rain, etc).

    RETURN ONLY RAW JSON:
    {{
        "intent": "string",
        "age": int or null, 
        "income": int or null,
        "matched_scheme_name": "string (EXACT name from the AVAILABLE LIST) or null"
    }}
    
    User Input: "{last_message}"
    """
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        clean_content = response.content.strip().replace('```json', '').replace('```', '')
        data = json.loads(clean_content)
        
        updates = {"current_intent": data.get("intent", "irrelevant")}
        
        # Update user info
        new_info = state.get("user_info", {}).copy()
        if data.get("age"): new_info["age"] = data["age"]
        if data.get("income"): new_info["income"] = data["income"]
        updates["user_info"] = new_info

        # Handle Fuzzy Matched Scheme
        if data.get("matched_scheme_name"):
            found = next((s for s in state.get("eligible_schemes", []) if s['name_hi'] == data["matched_scheme_name"]), None)
            if found:
                updates["selected_scheme"] = found
                updates["current_intent"] = "select_scheme"

        return updates

    except Exception:
        # Fallback for numbers
        import re
        numbers = re.findall(r'\d+', last_message)
        if len(numbers) >= 1:
             return {"current_intent": "provide_info"}
        return {"current_intent": "irrelevant"}


def decision_node(state: AgentState):
    """
    The Rule Engine: Maps Intents + Stage to specific responses.
    """
    intent = state.get("current_intent")
    stage = state.get("stage", "intro")
    user_info = state.get("user_info", {})
    age = user_info.get("age")
    income = user_info.get("income")
    
    response_text = ""
    next_stage = stage 

    # --- GLOBAL HANDLERS (Priority 1) ---
    # If user says Hello or Restart, we RESET everything regardless of current stage.
    if intent == "greeting":
        return {
            "messages": ["नमस्ते, आशा करता हूँ आपका दिन अच्छा जा रहा है |"],
            "stage": "intro", # Force reset
            "user_info": {},  # Optional: clear data on greeting if you want strict reset
            "eligible_schemes": []
        }
    
    if intent == "query_start":
        return {
            "messages": ["आप पर लागू सरकारी योजनाओं के बारे में अधिक जानने के लिए, कृपया मुझे अपनी उम्र और आय बताएं।"],
            "stage": "collecting_info"
        }

    # --- CASE 0: Null Input ---
    if intent == "null_input":
        return {"messages": ["माफ़ करें, मैं आपको समझ नहीं पाया। क्या आप कृपया फिर से दोहरा सकते हैं?"]}

    # --- LAYER 1: Intro ---
    if stage == "intro":
        if intent == "provide_info":
             pass # Pass to Layer 2 logic
        else:
            response_text = "क्षमा करें, मैं केवल सरकारी योजनाओं में आपकी सहायता कर सकता हूँ।"

    # --- LAYER 2: Collecting Info ---
    # We enter here if stage is collecting_info OR if user provided info in intro stage
    if intent == "provide_info" or (stage == "collecting_info" and intent not in ["greeting", "irrelevant"]):
        if not age or not income:
            response_text = "सही योजना खोजने के लिए मुझे आपकी उम्र और आय दोनों की आवश्यकता होगी |"
            next_stage = "collecting_info"
        else:
            # TOOL 1 USAGE: Search Database
            schemes = search_schemes_tool()
            eligible = [s for s in schemes if int(age) >= s['min_age'] and int(income) <= s['max_income']]
            
            if eligible:
                names = "\n".join([f"{i+1}. {s['name_hi']}" for i, s in enumerate(eligible)])
                response_text = f"आपकी जानकारी के आधार पर, आप निम्नलिखित योजनाओं के लिए पात्र हैं:\n{names}"
                next_stage = "schemes_presented"
                return {"messages": [response_text], "eligible_schemes": eligible, "stage": next_stage}
            else:
                response_text = "क्षमा करें, आपकी आयु और आय के आधार पर अभी कोई योजना उपलब्ध नहीं है।"
                next_stage = "intro" 

    elif stage == "collecting_info" and intent == "irrelevant":
         response_text = "कृपया एक मान्य उत्तर दर्ज करें | पात्रता जानने के लिए मुझे आपकी आयु और आय दोनों की आवश्यकता है।"

    # --- LAYER 3: Schemes Presented ---
    elif stage == "schemes_presented":
        
        if intent == "ask_all_details":
            eligible = state.get("eligible_schemes", [])
            details = "\n\n".join([f"**{s['name_hi']}**: {s['description']}" for s in eligible])
            response_text = f"यहाँ योजनाओं का विवरण दिया गया है:\n{details}\n\nबताएं कि आप किस योजना के लिए आवेदन करना चाहेंगे?"
        
        elif intent == "select_scheme":
            scheme = state.get("selected_scheme")
            if scheme:
                response_text = f"{scheme['name_hi']}: {scheme['description']}\n\nक्या आप आवेदन करना चाहते हैं?"
                next_stage = "scheme_detail"
            else:
                response_text = "कृपया उस योजना का नाम स्पष्ट रूप से बताएं जो सूची में है।"

        elif intent == "irrelevant":
             response_text = "कृपया चुनें और बताएं कि आप किस योजना के लिए आवेदन करना चाहेंगे?"
        
        else:
             response_text = "कृपया चुनें और बताएं कि आप किस योजना के लिए आवेदन करना चाहेंगे?"

    # --- LAYER 4: Scheme Detail ---
    elif stage == "scheme_detail":
        scheme = state.get("selected_scheme")
        
        if intent == "confirm_apply":
            link = get_application_link_tool(scheme)
            response_text = f"बढ़िया! आप इस लिंक पर जाकर आवेदन कर सकते हैं: [यहाँ क्लिक करें]({link})"
            next_stage = "intro" 
        
        elif intent == "deny_apply":
            response_text = "धन्यवाद, आपसे मिलकर खुशी हुई, आशा करता हूँ कि भविष्य में मैं आपके काम आ सकूँ।"
            next_stage = "intro"
        
        else:
            response_text = "कृपया 'हाँ' या 'नहीं' में उत्तर दें। क्या आप आवेदन करना चाहते हैं?"

    # Fallback
    if not response_text:
        response_text = "माफ़ करें, मैं समझ नहीं पाया।"

    return {"messages": [response_text], "stage": next_stage}

# --- 5. GRAPH CONSTRUCTION ---
workflow = StateGraph(AgentState)
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("decision_maker", decision_node)
workflow.add_edge(START, "analyzer")
workflow.add_edge("analyzer", "decision_maker")
workflow.add_edge("decision_maker", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
