import json
import operator
import streamlit as st
from typing import Annotated, TypedDict, List
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
import re

# --- 1. CONFIG & SETUP ---
try:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        groq_api_key=st.secrets["GROQ_API_KEY"], 
        temperature=0
    )
except Exception as e:
    st.error("Error initializing LLM. Please check your GROQ_API_KEY.")

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
    """Tool 1: Load schemes."""
    try:
        with open("schemes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def get_application_link_tool(scheme_data: dict):
    """Tool 2: Get Link."""
    return scheme_data.get('link', '#')

# --- 4. NODES ---

def analyzer_node(state: AgentState):
    """
    STRICT INTENT CLASSIFIER.
    Does not generate text. Only categorizes input.
    """
    last_msg = state["messages"][-1]
    last_message = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    text_lower = last_message.lower().strip()
    
    current_stage = state.get("stage", "intro")
    eligible_schemes = state.get("eligible_schemes", [])
    scheme_names = [s['name_hi'] for s in eligible_schemes]

    # --- IMMEDIATE INTERRUPTS ---
    # 1. Null/Silence Check (User Rule)
    if not text_lower or "कर दो" in text_lower or text_lower == "...":
        return {"current_intent": "null_input"}

    # 2. Greeting Check (Only valid in Intro or neutral states)
    if current_stage == "intro":
        greeting_keywords = ["नमस्ते", "namaste", "hello", "hi", "hey", "pranam"]
        if any(word in text_lower for word in greeting_keywords):
            return {"current_intent": "greeting"}

        start_keywords = ["शुरू", "start", "kya bolna", "kya karna", "kaise", "मदद", "help", "kahan se"]
        if any(word in text_lower for word in start_keywords) and "age" not in text_lower:
            return {"current_intent": "query_start"}

    # 3. Explicit Denials (Universal)
    deny_keywords = ["nahi", "no", "rehne do", "nhi", "na", "cancel"]
    if text_lower in deny_keywords: 
        return {"current_intent": "deny"}

    # --- LLM CLASSIFICATION ---
    prompt = f"""
    You are the 'Intent Classifier' for a strict Hindi government scheme bot.
    
    CURRENT STAGE: {current_stage}
    AVAILABLE SCHEMES: {scheme_names}

    Analyze the Hindi User Input and return JSON with exactly one 'intent'.

    INTENT CATEGORIES:
    1. 'greeting': Only basic greetings (Namaste, Hello).
    2. 'query_start': User asking "How to start?", "What to do?".
    3. 'provide_info': Input contains numbers that look like Age or Income.
    4. 'ask_all_details': "Sab batao", "Details do", "What are these?".
    5. 'select_scheme': User names a scheme or asks about one. MUST FUZZY MATCH with AVAILABLE SCHEMES.
    6. 'confirm_apply': "Yes", "Ha", "Apply karna hai".
    7. 'deny': "No", "Nahi".
    8. 'irrelevant': Jokes, Food, Politics, Gibberish, random questions.

    OUTPUT FORMAT:
    {{
        "intent": "string",
        "age": int or null, 
        "income": int or null,
        "matched_scheme_name": "string (Exact name from AVAILABLE SCHEMES) or null"
    }}

    User Input: "{last_message}"
    """
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        clean_content = response.content.strip().replace('```json', '').replace('```', '')
        data = json.loads(clean_content)
        
        intent = data.get("intent", "irrelevant")
        updates = {"current_intent": intent}

        # Save extracted entities
        new_info = state.get("user_info", {}).copy()
        if data.get("age"): new_info["age"] = data["age"]
        if data.get("income"): new_info["income"] = data["income"]
        updates["user_info"] = new_info

        # Handle Scheme Selection Logic
        if data.get("matched_scheme_name"):
            found = next((s for s in eligible_schemes if s['name_hi'] == data["matched_scheme_name"]), None)
            if found:
                updates["selected_scheme"] = found
                updates["current_intent"] = "select_scheme"
        
        return updates

    except Exception:
        return {"current_intent": "irrelevant"}


def decision_node(state: AgentState):
    """
    STRICT RULE ENGINE.
    Enforces the logic flow layers exactly as requested.
    """
    intent = state.get("current_intent")
    stage = state.get("stage", "intro")
    
    user_info = state.get("user_info", {})
    age = user_info.get("age")
    income = user_info.get("income")
    
    response_text = ""
    next_stage = stage 

    # --- GLOBAL INTERRUPT: NULL INPUT ---
    if intent == "null_input":
        return {"messages": ["माफ़ करें, मैं आपको समझ नहीं पाया। क्या आप कृपया फिर से दोहरा सकते हैं?"]}

    # ============================================================
    # LAYER 1: INTRO / BASICS
    # ============================================================
    if stage == "intro":
        if intent == "greeting":
            response_text = "नमस्ते, आशा करता हूँ आपका दिन अच्छा जा रहा है |"
        
        elif intent == "query_start":
            response_text = "आप पर लागू सरकारी योजनाओं के बारे में अधिक जानने के लिए, कृपया मुझे अपनी उम्र और आय बताएं।"
            next_stage = "collecting_info"
        
        elif intent == "provide_info":
            # Jump straight to validation logic below
            pass 
        
        else: # Nonsense / Irrelevant at start
            response_text = "क्षमा करें, मैं केवल सरकारी योजनाओं में आपकी सहायता कर सकता हूँ।"

    # ============================================================
    # LAYER 2: DATA COLLECTION
    # ============================================================
    # Logic: User is providing info OR we are waiting for info
    if stage == "collecting_info" or (stage == "intro" and intent == "provide_info"):
        
        # 1.3.b Deviation / Irrelevant during data collection
        if intent == "irrelevant" and stage == "collecting_info":
            response_text = "कृपया एक मान्य उत्तर दर्ज करें | पात्रता जानने के लिए मुझे आपकी आयु और आय दोनों की आवश्यकता है।"
            next_stage = "collecting_info"

        # 1.3.a Partial Info Check
        elif not age or not income:
             if intent != "greeting": # Don't scold if they just said Hi
                response_text = "सही योजना खोजने के लिए मुझे आपकी उम्र और आय दोनों की आवश्यकता होगी |"
                next_stage = "collecting_info"
        
        # 1.3.c Full Info Validation
        else:
            try:
                age_int = int(age)
                income_int = int(income)
            except:
                age_int = 0; income_int = 0

            # Rule: Age > 100
            if age_int > 100:
                response_text = "मनुष्य का औसत जीवनकाल 90 साल होता है, कृपया मुझे अपनी सही उम्र बताएं"
                # Reset age to force re-entry, keep stage
                state["user_info"]["age"] = None 
                next_stage = "collecting_info"
            
            # Rule: Valid Age -> Scan Schemes
            else:
                all_schemes = search_schemes_tool()
                eligible = [s for s in all_schemes if age_int >= s['min_age'] and income_int <= s['max_income']]
                
                if not eligible:
                    response_text = "क्षमा करें, आपकी आयु और आय के आधार पर अभी कोई योजना उपलब्ध नहीं है।"
                    next_stage = "intro" # Reset
                else:
                    # List schemes pointwise
                    names = "\n".join([f"{i+1}. {s['name_hi']}" for i, s in enumerate(eligible)])
                    response_text = f"आपकी जानकारी के आधार पर, आप निम्नलिखित योजनाओं के लिए पात्र हैं:\n\n{names}"
                    next_stage = "schemes_presented"
                    return {"messages": [response_text], "eligible_schemes": eligible, "stage": next_stage}

    # ============================================================
    # LAYER 3: SCHEME SELECTION
    # ============================================================
    elif stage == "schemes_presented":
        
        # 1.3.c.1 Describe All
        if intent == "ask_all_details":
            eligible = state.get("eligible_schemes", [])
            details = "\n\n".join([f"**{s['name_hi']}**: {s['description']}" for s in eligible])
            response_text = f"यहाँ योजनाओं का विवरण दिया गया है:\n{details}\n\nबताएं कि आप किस योजना के लिए आवेदन करना चाहेंगे?"
        
        # 1.3.c.2 Select Specific
        elif intent == "select_scheme":
            scheme = state.get("selected_scheme")
            if scheme:
                response_text = f"{scheme['name_hi']}: {scheme['description']}\n\nक्या आप आवेदन करना चाहते हैं?"
                next_stage = "scheme_detail"
            else:
                response_text = "कृपया उस योजना का नाम स्पष्ट रूप से बताएं जो सूची में है।"

        # 1.3.c.3 Deviation (Random topic after list)
        elif intent == "irrelevant" or intent == "greeting":
            response_text = "माफ़ कीजिए, मुझे बिल्कुल भी पता नहीं कि आप क्या कह रहे हैं |"
            # Note: You asked for this reply, but usually we'd want to nudge them back. 
            # I will adhere to your script.
        
        # 1.3.c.1.i Deviation Loop (Catch-all if they don't pick a scheme)
        else:
             response_text = "कृपया चुनें और बताएं कि आप किस योजना के लिए आवेदन करना चाहेंगे?"

    # ============================================================
    # LAYER 4: APPLICATION / DETAIL
    # ============================================================
    elif stage == "scheme_detail":
        
        scheme = state.get("selected_scheme")

        # 1.3.c.2.i Apply (Yes)
        if intent == "confirm_apply":
            link = get_application_link_tool(scheme)
            response_text = f"बढ़िया! आप इस लिंक पर जाकर आवेदन कर सकते हैं: [यहाँ क्लिक करें]({link})"
            next_stage = "intro" # Reset after success
        
        # 1.3.c.2.ii Deny (No)
        elif intent == "deny":
            response_text = "धन्यवाद, आपसे मिलकर खुशी हुई, आशा करता हूँ कि भविष्य में मैं आपके काम आ सकूँ।"
            next_stage = "intro" # Reset
        
        # Deviation in detail stage
        else:
            response_text = "कृपया 'हाँ' या 'नहीं' में उत्तर दें। क्या आप आवेदन करना चाहते हैं?"

    # Fallback if nothing matched
    if not response_text:
        response_text = "माफ़ करें, मैं समझ नहीं पाया।"

    return {"messages": [response_text], "stage": next_stage}

# --- 5. GRAPH ---
workflow = StateGraph(AgentState)
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("decision_maker", decision_node)
workflow.add_edge(START, "analyzer")
workflow.add_edge("analyzer", "decision_maker")
workflow.add_edge("decision_maker", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)