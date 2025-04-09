# from dotenv import load_dotenv
# load_dotenv()


# import os
# import httpx
# from typing import TypedDict, Any
# from langgraph.graph import StateGraph
# from langchain_core.runnables import RunnableLambda

# # Load MCP server URLs from .env
# PARSER_URL = os.getenv("LOAN_PARSER_URL")
# CREDIT_URL = os.getenv("CREDIT_ANALYZER_URL")
# RISK_URL = os.getenv("RISK_ASSESSOR_URL")

# # State schema
# class State(TypedDict):
#     output: Any

# # MCP call wrapper
# def call_mcp_server(url):
#     async def fn(state: State) -> State:
#         print(f"[DEBUG] Calling {url} with payload:", state["output"])
#         async with httpx.AsyncClient() as client:
#             response = await client.post(url, json=state["output"])
#             response.raise_for_status()
#             return {"output": response.json()}
#     return RunnableLambda(fn).with_config({"run_name": f"CallMCP::{url.split(':')[2]}"})

# # Build LangGraph
# def build_graph():
#     graph = StateGraph(State)

#     graph.add_node("LoanParser", call_mcp_server(PARSER_URL))
#     #graph.add_node("CreditAnalyzer", call_mcp_server(CREDIT_URL))

#     async def credit_node(state: State) -> State:
#         async with httpx.AsyncClient() as client:
#             response = await client.post(CREDIT_URL, json=state["output"])
#             response.raise_for_status()
#             credit_data = response.json()

#             # Merge the original loan fields for RiskAssessor
#             credit_data["fields"] = state["output"].get("fields", {})
#             print("[DEBUG] Merged credit data with fields:", credit_data)

#             return {"output": credit_data}

#     graph.add_node("CreditAnalyzer", RunnableLambda(credit_node).with_config({"run_name": "CallMCP::credit_analyzer"}))

#     graph.add_node("RiskAssessor", call_mcp_server(RISK_URL))

#     graph.set_entry_point("LoanParser")
#     graph.add_edge("LoanParser", "CreditAnalyzer")
#     graph.add_edge("CreditAnalyzer", "RiskAssessor")
#     graph.set_finish_point("RiskAssessor")



#     return graph.compile()


from dotenv import load_dotenv
load_dotenv()

import os
import httpx
from typing import TypedDict, Any
from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda

# Load MCP server URLs from .env
PARSER_URL = os.getenv("LOAN_PARSER_URL")
CREDIT_URL = os.getenv("CREDIT_ANALYZER_URL")
RISK_URL = os.getenv("RISK_ASSESSOR_URL")

# State schema
class State(TypedDict):
    output: Any

# MCP call wrapper
def call_mcp_server(url):
    async def fn(state: State) -> State:
        print(f"[DEBUG] Calling {url} with payload:", state["output"])
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=state["output"])
            response.raise_for_status()
            return {"output": response.json()}
    return RunnableLambda(fn).with_config({"run_name": f"CallMCP::{url.split(':')[2]}"})

# Build LangGraph
def build_graph():
    graph = StateGraph(State)

    graph.add_node("LoanParser", call_mcp_server(PARSER_URL))
    graph.add_node("CreditAnalyzer", call_mcp_server(CREDIT_URL))  # Cleaned!
    graph.add_node("RiskAssessor", call_mcp_server(RISK_URL))

    graph.set_entry_point("LoanParser")
    graph.add_edge("LoanParser", "CreditAnalyzer")
    graph.add_edge("CreditAnalyzer", "RiskAssessor")
    graph.set_finish_point("RiskAssessor")

    return graph.compile()
