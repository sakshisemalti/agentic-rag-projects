import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

from dotenv import load_dotenv
import os

load_dotenv()

# ----------------------------
# MCP + Agent Configuration
# ----------------------------
DEFAULT_MCP_URL = "http://localhost:8000/mcp"
AGENT_TIMEOUT_SECONDS = 90        # hard stop per claim so it never hangs indefinitely
RECURSION_LIMIT = 15              # each LLM turn + each tool call counts as a step

# IMPORTANT: tightened to force convergence.
# The previous loop (rag_ask called repeatedly forever) happened because nothing
# stopped the model from re-calling rag_ask. This prompt makes the call budget explicit.
SYSTEM_PROMPT = """You are an HR Expense Compliance Agent.

Follow these steps EXACTLY, in order, for the claim given to you:

1) Call the rag_ask tool EXACTLY ONCE, passing the claim's category as "category" and a
   clear question asking what the expense policy says relevant to this claim.
   Do NOT call rag_ask a second time for this claim, even if the answer seems incomplete.
   Use whatever policy information you get back.

2) Evaluate the claim strictly against the retrieved policy text.

3) Call EXACTLY ONE of the following tools, passing the claim_id:
   - approve(claim_id, reason) if the claim is compliant
   - reject(claim_id, reason) if the claim is NOT compliant
   Do NOT call more than one of these, and do NOT call either more than once.

4) After the tool call succeeds, respond with ONLY a JSON object (no markdown fences,
   no extra prose) in this exact shape:
   {"decision": "approve" | "reject", "reason": "<one sentence>", "violated_clause": "<optional>"}

You must never call the same tool twice for the same claim. If you are unsure, make your
best decision with the information you already have rather than calling a tool again.
"""

ASK_TEMPLATE = """Claim to evaluate:
- claim_id: {claim_id}
- date: {date}
- category: {category}
- description: {description}
- amount: {amount} {currency}
- receipt_available: {receipt_available}
- pre_approved: {pre_approved}
- employee_context: {employee_context}

Follow the steps in your instructions exactly. Remember: rag_ask once, then exactly one
of approve/reject (passing claim_id="{claim_id}"), then output the final JSON only.
"""

# ----------------------------
# Helpers
# ----------------------------
def load_claims_from_bytes(file_bytes: bytes) -> Dict[str, Any]:
    return json.loads(file_bytes.decode("utf-8"))

async def build_agent(mcp_url: str, model: str = "gpt-4o-mini", temperature: float = 0.0):
    client = MultiServerMCPClient(
        {
            "tools": {
                "url": mcp_url,
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()
    llm = ChatOpenAI(model=model, temperature=temperature)
    agent = create_agent(llm, tools)
    return agent

async def process_one_claim(agent, claim: Dict[str, Any], employee_ctx: str) -> Dict[str, Any]:
    user_content = ASK_TEMPLATE.format(
        claim_id=claim.get("claim_id"),
        date=claim.get("date"),
        category=claim.get("category"),
        description=claim.get("description"),
        amount=claim.get("amount"),
        currency=claim.get("currency"),
        receipt_available=claim.get("receipt_available"),
        pre_approved=claim.get("pre_approved"),
        employee_context=employee_ctx,
    )

    try:
        response = await asyncio.wait_for(
            agent.ainvoke(
                {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ]
                },
                config={"recursion_limit": RECURSION_LIMIT},
            ),
            timeout=AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return {
            "claim_id": claim.get("claim_id"),
            "category": claim.get("category"),
            "amount": f"{claim.get('amount')} {claim.get('currency')}",
            "decision_trace": f"ERROR: agent timed out after {AGENT_TIMEOUT_SECONDS}s "
                               f"(likely stuck looping on a tool call).",
            "raw_messages": None,
        }
    except Exception as e:
        return {
            "claim_id": claim.get("claim_id"),
            "category": claim.get("category"),
            "amount": f"{claim.get('amount')} {claim.get('currency')}",
            "decision_trace": f"ERROR: {type(e).__name__}: {e}",
            "raw_messages": None,
        }

    try:
        final_msg = response["messages"][-1].content
    except Exception:
        final_msg = str(response)

    # Keep the full trace so you can debug tool call loops in the UI if needed
    try:
        raw_messages = [
            f"{m.__class__.__name__}: {getattr(m, 'content', '')}"
            for m in response.get("messages", [])
        ]
    except Exception:
        raw_messages = None

    return {
        "claim_id": claim.get("claim_id"),
        "category": claim.get("category"),
        "amount": f"{claim.get('amount')} {claim.get('currency')}",
        "decision_trace": final_msg,
        "raw_messages": raw_messages,
    }

async def process_claims(agent, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    employee = data.get("employee", {})
    claims: List[Dict[str, Any]] = data.get("claims", [])
    employee_ctx = f"{employee.get('department','')}, {employee.get('designation','')}, {employee.get('location','')}"

    results = []
    for claim in claims:
        result = await process_one_claim(agent, claim, employee_ctx)
        results.append(result)
    return results

# ----------------------------
# Streamlit App
# ----------------------------
st.set_page_config(page_title="HR Expense Agent (MCP)", page_icon="💼", layout="wide")
st.title("💼 HR Expense Compliance Agent (MCP + RAG)")

with st.sidebar:
    st.header("Settings")
    mcp_url = st.text_input("MCP Server URL", value=DEFAULT_MCP_URL)
    model = st.text_input("OpenAI Model", value="gpt-4o-mini")
    temperature = st.slider("LLM Temperature", 0.0, 1.0, 0.0, 0.1)
    st.caption("MCP server should expose tools: rag_ask, approve, reject.")

uploaded = st.file_uploader("Upload claims JSON", type=["json"])

col1, col2 = st.columns([1, 1])
with col1:
    run_btn = st.button("Run Agent on Claims", type="primary", use_container_width=True)
with col2:
    st.write("")

if run_btn:
    if not uploaded:
        st.error("Please upload a claims JSON file first.")
        st.stop()

    try:
        data = load_claims_from_bytes(uploaded.getvalue())
    except Exception as e:
        st.error(f"Failed to parse JSON: {e}")
        st.stop()

    employee = data.get("employee", {})
    st.subheader("Employee")
    st.json(employee)

    with st.spinner("Connecting to MCP server and building agent..."):
        try:
            agent = asyncio.run(build_agent(mcp_url=mcp_url, model=model, temperature=temperature))
        except Exception as e:
            st.error(f"Failed to connect/build agent: {e}")
            st.stop()

    st.info(f"Found {len(data.get('claims', []))} claim(s). Running decisions + actions...")
    with st.spinner("Evaluating claims and taking actions..."):
        try:
            results = asyncio.run(process_claims(agent, data))
        except Exception as e:
            st.error(f"Agent run failed: {e}")
            st.stop()

    st.success("Done!")
    st.subheader("Results")
    for r in results:
        with st.expander(f"Claim {r['claim_id']} — {r['category']} — {r['amount']}", expanded=False):
            st.markdown("**Decision / Action Trace**")
            st.write(r["decision_trace"])
            if r.get("raw_messages"):
                with st.expander("Full message trace (debug)", expanded=False):
                    for m in r["raw_messages"]:
                        st.text(m)

    st.caption(
        "The agent evaluates each claim against policy, then finalizes it as approved or rejected. "
        "Your MCP server performs the actual actions via its tools."
    )