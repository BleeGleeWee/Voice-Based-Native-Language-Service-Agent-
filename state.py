import json
import operator
import streamlit as st
from typing import Annotated, TypedDict, List, Optional
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

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
    deviation_counter: int   # to track repeated deviations

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
    """
    last_msg = state["messages"][-1]
    last_message = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    text_lower = last_message.lower().strip()
    
    current_stage = state.get("stage", "intro")
    eligible_schemes = state.get("eligible_schemes", [])
    scheme_names = [s['name_hi'] for s in eligible_schemes]

    # --- IMMEDIATE INTERRUPTS ---
    # 0. Null/Silence Check (User Rule: "कर दो" or empty)
    if not text_lower or "कर दो" in text_lower or text_lower == "..." or text_lower == ".":
        return {"current_intent": "null_input"}

    # 1. Greeting Check (Only valid in Intro)
    if current_stage == "intro":
        greeting_keywords = ["नमस्ते", "namaste", "hello", "hi", "hey", "pranam", "sup"]
        if any(word == text_lower for word in greeting_keywords) or any(text_lower.startswith(w) for w in greeting_keywords):
            return {"current_intent": "greeting"}

    # --- LLM CLASSIFICATION ---
    prompt = f"""
    You are the Intent Classifier for a strict Hindi government scheme bot.
    
    CURRENT STAGE: {current_stage}
    AVAILABLE SCHEMES: {scheme_names}

    Analyze the User Input and return JSON with exactly one 'intent'.

    INTENT CATEGORIES:
    1. 'greeting': Basic greetings.
    2. 'query_start': "How to start?", "What should I say?", "Help me", "Start".
    3. 'provide_info': Input contains numbers that look like Age or Income.
    4. 'ask_all_benefits': "What do these schemes do?", "Tell me benefits of all".
    5. 'select_scheme': User names a scheme or asks about one specifically. MUST FUZZY MATCH with AVAILABLE SCHEMES.
    6. 'confirm_apply': "Yes", "Ha", "Apply karna hai", "Aavedan karna hai".
    7. 'deny': "No", "Nahi", "Rehne do".
    8. 'irrelevant': Jokes, Food, Politics, Gibberish, random questions not related to schemes/age/income.

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
        if data.get("age") is not None: new_info["age"] = data["age"]
        if data.get("income") is not None: new_info["income"] = data["income"]
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
        # 1.1 Greeting Reply
        if intent == "greeting":
            response_text = "नमस्ते, आशा करता हूँ आपका दिन अच्छा जा रहा है |"
        
        # 1.3 Start Query
        elif intent == "query_start":
            response_text = "आप पर लागू सरकारी योजनाओं के बारे में अधिक जानने के लिए, कृपया मुझे अपनी उम्र और आय बताएं।"
            next_stage = "collecting_info"
        
        # 1.3.a / 1.3.c Direct Info Provision (Jump to collecting logic)
        elif intent == "provide_info":
             # Pass through to validation logic below
             pass 

        # 1.2 Nonsense
        else: 
            response_text = "क्षमा करें, मैं केवल सरकारी योजनाओं में आपकी सहायता कर सकता हूँ।"

    # ============================================================
    # LAYER 2: DATA COLLECTION (1.3.a - 1.3.c)
    # ============================================================
    if stage == "collecting_info" or (stage == "intro" and intent == "provide_info"):
        
        # 1.3.b Deviation
        if intent == "irrelevant" or intent == "greeting":
             response_text = "कृपया एक मान्य उत्तर दर्ज करें | पात्रता जानने के लिए मुझे आपकी आयु और आय दोनों की आवश्यकता है।"
             next_stage = "collecting_info"

        # 1.3.a Partial Info Check
        elif age is None or income is None:
             response_text = "सही योजना खोजने के लिए मुझे आपकी उम्र और आय दोनों की आवश्यकता होगी |"
             next_stage = "collecting_info"

        # 1.3.c Full Info Validation
        else:
            try:
                age_int = int(age)
                income_int = int(income)
            except:
                age_int = 0; income_int = 0

            # 1.3.c.i Age > 100
            if age_int > 100:
                response_text = "मनुष्य का औसत जीवनकाल 90 साल होता है, कृपया मुझे अपनी सही उम्र बताएं"
                # Reset age so they must enter it again, keep stage same
                state["user_info"]["age"] = None 
                next_stage = "collecting_info"
            
            # 1.3.c.ii Valid Age -> Scan
            else:
                all_schemes = search_schemes_tool()
                # Simple filtering logic
                eligible = [s for s in all_schemes if age_int >= s.get('min_age', 0) and income_int <= s.get('max_income', 99999999)]
                
                # 1.3.c.ii.4 No Schemes Available
                if not eligible:
                    response_text = "क्षमा करें, आपकी आयु और आय के आधार पर अभी कोई योजना उपलब्ध नहीं है।"
                    next_stage = "intro" # Reset flow
                
                # 1.3.c.ii List Schemes
                else:
                    names = "\n".join([f"• {s['name_hi']}" for s in eligible])
                    response_text = f"आपकी जानकारी के आधार पर, आप निम्नलिखित योजनाओं के लिए पात्र हैं:\n\n{names}"
                    next_stage = "schemes_presented"
                    return {"messages": [response_text], "eligible_schemes": eligible, "stage": next_stage}

    # ============================================================
    # LAYER 3 & 4: SCHEME PRESENTATION & DETAIL
    # ============================================================
    elif stage == "schemes_presented":
        
        # 1.3.c.ii.1 Ask Benefits (All)
        if intent == "ask_all_benefits":
            eligible = state.get("eligible_schemes", [])
            descriptions = "\n\n".join([f"**{s['name_hi']}**: {s['description']}" for s in eligible])
            response_text = descriptions
            # Stay in this stage

        # 1.3.c.ii.2 Select Specific Scheme
        elif intent == "select_scheme":
            scheme = state.get("selected_scheme")
            if scheme:
                response_text = f"{scheme['description']}\n\nक्या आप आवेदन करना चाहते हैं?"
                next_stage = "scheme_detail"
            else:
                response_text = "कृपया सूची में से किसी एक योजना का नाम बताएं।"

        # 1.3.c.ii.3 Deviation (Irrelevant)
        elif intent == "irrelevant":
            response_text = "माफ़ कीजिए, मुझे बिल्कुल भी पता नहीं कि आप क्या कह रहे हैं |"
        
        # 1.3.c.ii.1.i Deviation Again / General Confusion
        else:
             response_text = "कृपया चुनें और बताएं कि आप किस योजना के लिए आवेदन करना चाहेंगे?"

    # ============================================================
    # LAYER 5: APPLICATION (Yes/No)
    # ============================================================
    elif stage == "scheme_detail":
        
        scheme = state.get("selected_scheme")

        # 1.3.c.ii.2.i YES
        if intent == "confirm_apply":
            link = get_application_link_tool(scheme)
            response_text = f"ठीक है, यह रहा आवेदन लिंक: [यहाँ क्लिक करें]({link})"
            next_stage = "intro" # Reset
        
        # 1.3.c.ii.2.ii NO
        elif intent == "deny":
            response_text = "धन्यवाद, आपसे मिलकर खुशी हुई, आशा करता हूँ कि भविष्य में मैं आपके काम आ सकूँ।"
            next_stage = "intro" # Reset

        # Fallback for deviation in this specific Yes/No state
        else:
             response_text = "कृपया 'हाँ' या 'नहीं' में उत्तर दें। क्या आप आवेदन करना चाहते हैं?"

    # Fallback safety
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
