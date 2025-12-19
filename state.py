import json
import operator
from typing import Annotated, TypedDict, List
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

# --- 1. स्टेट परिभाषा ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    user_info: dict  # आयु और आय स्टोर करने के लिए
    eligible_schemes: List[str]
    is_complete: bool
    current_action: str # "info", "apply", "no", "irrelevant", या "execute"

# मॉडल इनिशियलाइजेशन (अपडेटेड मॉडल नाम के साथ)
GROQ_API_KEY = "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"
llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY, temperature=0)

# --- 2. टूल्स ---
def search_schemes_tool():
    """लोकल डेटाबेस से योजनाओं को लोड करने का टूल"""
    try:
        with open("schemes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# --- 3. नोड्स (तर्क और निर्णय) ---

def extractor_node(state: AgentState):
    """AI Extractor: इरादे की पहचान और जानकारी निकालना"""
    last_message = state["messages"][-1]
    user_info = state.get("user_info", {})

    prompt = f"""
    आप एक इंटेलिजेंट एजेंट हैं। इस हिंदी इनपुट का विश्लेषण करें: "{last_message}"
    
    1. Intent: क्या उपयोगकर्ता 'जानकारी दे रहा है' (info), 'आवेदन करना चाहता है' (apply), 'मना कर रहा है' (no), या 'असंगत बात' (irrelevant) कर रहा है?
    2. Data: यदि 'info' है, तो आयु (age) और आय (income) निकालें।
    3. Contradiction: यदि नई आयु पुरानी आयु ({user_info.get('age')}) से अलग है, तो 'flag_contradiction' को true करें।

    केवल JSON वापस करें:
    {{"intent": "info", "age": 25, "income": 20000, "flag_contradiction": false}}
    """
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        data = json.loads(response.content.strip().replace('```json', '').replace('```', ''))
        
        # विसंगति संभालना (Contradiction Handling)
        new_messages = []
        if data.get("flag_contradiction"):
            new_messages.append("मैंने नोट किया कि आपकी आयु पहले अलग थी। क्या आप नई जानकारी के साथ आगे बढ़ना चाहते हैं?")

        # डेटा अपडेट करें
        if data.get("age"): user_info["age"] = data["age"]
        if data.get("income"): user_info["income"] = data["income"]
        
        return {"user_info": user_info, "current_action": data.get("intent", "info"), "messages": new_messages}
    except:
        return {"current_action": "irrelevant"}

def planner_node(state: AgentState):
    """Planner: इरादे के आधार पर अगला कदम तय करना"""
    intent = state.get("current_action")
    user_info = state.get("user_info", {})

    # Failure Handling: असंबंधित इनपुट (जैसे आइसक्रीम)
    if intent == "irrelevant":
        return {"messages": ["क्षमा करें, मैं केवल सरकारी योजनाओं में आपकी सहायता कर सकता हूँ। कृपया अपनी आयु या आय बताएं।"], "is_complete": False}

    # Incomplete Info: यदि जानकारी गायब है
    if not user_info.get("age") or not user_info.get("income"):
        return {"messages": ["पात्रता जानने के लिए मुझे आपकी आयु और आय दोनों की आवश्यकता है।"], "is_complete": False}

    # Application Intent: यदि उपयोगकर्ता आवेदन करना चाहता है
    if intent == "apply":
        return {"messages": ["बहुत अच्छा! आवेदन के लिए आपको आधार कार्ड की आवश्यकता होगी। क्या मैं प्रक्रिया शुरू करूँ?"], "is_complete": True}

    return {"current_action": "execute"}

def executor_node(state: AgentState):
    """Executor: पात्रता इंजन (यही फंक्शन मिसिंग था)"""
    user_info = state.get("user_info", {})
    age = int(user_info.get("age", 0))
    income = int(user_info.get("income", 0))

    schemes = search_schemes_tool()
    valid_schemes = []

    for s in schemes:
        if age >= s['min_age'] and income <= s['max_income']:
            valid_schemes.append(s['name_hi'])
            
    return {"eligible_schemes": valid_schemes}

def evaluator_node(state: AgentState):
    """Evaluator: अंतिम परिणाम और फीडबैक"""
    schemes = state.get("eligible_schemes", [])
    if not schemes:
        msg = "क्षमा करें, आपकी जानकारी के आधार पर कोई योजना नहीं मिली।"
    else:
        msg = f"आप इन योजनाओं के लिए पात्र हैं: {', '.join(schemes)}। क्या आप आवेदन करना चाहते हैं?"
    
    return {"messages": [msg], "is_complete": True}

# --- 4. ग्राफ़ निर्माण ---
workflow = StateGraph(AgentState)

workflow.add_node("extractor", extractor_node)
workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("evaluator", evaluator_node)

workflow.add_edge(START, "extractor")
workflow.add_edge("extractor", "planner")

# कंडीशनल एज: प्लानर तय करेगा कि एक्जीक्यूटर पर जाना है या रुकना है
workflow.add_conditional_edges(
    "planner",
    lambda x: "executor" if x["current_action"] == "execute" else "end",
    {"executor": "executor", "end": END}
)

workflow.add_edge("executor", "evaluator")
workflow.add_edge("evaluator", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)