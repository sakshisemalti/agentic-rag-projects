import asyncio, time
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

# ---- MCP (streamable_http) ----
from mcp.server.fastmcp import FastMCP

# ---- Your RAG + Ingest imports ----
from .rag import answer_with_docs_async            # must return (answer, sources, contexts)
from .ingest import run_ingest_async               # your async ingest job

# ========== MCP SERVER ==========
mcp = FastMCP(
    name="company-kb",
    instructions="Provide tools to query company knowledge and take simple actions.",
    json_response=True,
)

# Tool schemas
class AskParams(BaseModel):
    question: str = Field(...)
    category: str | None = None

class AskResult(BaseModel):
    answer: str
    sources: List[str]
    contexts: List[str]

# In-memory store of decisions so you can audit what got approved/rejected and for which claim
_decisions: Dict[str, Dict[str, Any]] = {}

@mcp.tool(description="Ask the RAG system by passing question and category and get answer + sources + contexts. Call this ONLY ONCE per claim evaluation.")
async def rag_ask(params: AskParams) -> AskResult:
    answer, sources, contexts = await answer_with_docs_async(params.question, params.category)
    return AskResult(answer=answer, sources=sources, contexts=contexts)

@mcp.tool(description="Approve a compliant expense claim and record the approval. Pass the claim_id being approved.")
async def approve(claim_id: str, reason: Optional[str] = None) -> str:
    _decisions[claim_id] = {"status": "APPROVED", "reason": reason, "ts": time.time()}
    print(f"APPROVED claim {claim_id}: {reason}")
    return f"APPROVED:{claim_id}"

@mcp.tool(description="Reject a non-compliant expense claim and record the rejection. Pass the claim_id being rejected.")
async def reject(claim_id: str, reason: Optional[str] = None) -> str:
    _decisions[claim_id] = {"status": "REJECTED", "reason": reason, "ts": time.time()}
    print(f"REJECTED claim {claim_id}: {reason}")
    return f"REJECTED:{claim_id}"

# Export a Starlette app with streamable HTTP MCP endpoint at /mcp
app = mcp.streamable_http_app()

# ========== STATIC / UI ==========
static_dir = (Path(__file__).resolve().parent / "static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ========== INGEST STATE ==========
_ingest_lock = asyncio.Lock()
_ingest_task: asyncio.Task | None = None
_ingest_last: Dict[str, Any] = {
    "status": "idle",      # idle | running | succeeded | failed
    "started_at": None,
    "finished_at": None,
    "stats": None,         # {"documents":..., "chunks":...}
    "error": None,
}

# ========== ROUTE HANDLERS ==========
async def ui_handler(request: Request):
    """Root page -> serve your index.html if present, else a small hello."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return PlainTextResponse("Company Knowledge Assistant (MCP + Starlette)", status_code=200)

async def ask_handler(request: Request):
    """POST /ask  -> call RAG directly (same impl as before)."""
    try:
        payload = await request.json()
        question = payload.get("question") or ""
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not question.strip():
        return JSONResponse({"error": "Missing 'question'"}, status_code=400)

    start = time.perf_counter()
    category = payload.get("category") or "policies"

    answer, sources, contexts = await answer_with_docs_async(question, category)
    elapsed = time.perf_counter() - start
    print(f"⏱️ /ask execution took {elapsed:.2f} seconds")

    return JSONResponse({
        "answer": answer,
        "sources": sources,
        "contexts": contexts
    })

async def ingest_job():
    """Background ingest job."""
    _ingest_last.update({
        "status": "running",
        "started_at": time.time(),
        "finished_at": None,
        "stats": None,
        "error": None
    })
    try:
        stats = await run_ingest_async()
        _ingest_last.update({
            "status": "succeeded",
            "finished_at": time.time(),
            "stats": stats
        })
    except Exception as e:
        _ingest_last.update({
            "status": "failed",
            "finished_at": time.time(),
            "error": str(e)
        })

async def ingest_handler(request: Request):
    """POST /ingest  -> kick off ingest once."""
    global _ingest_task
    async with _ingest_lock:
        if _ingest_task and not _ingest_task.done():
            return JSONResponse({"ok": False, "message": "Ingestion already running"}, status_code=409)
        _ingest_task = asyncio.create_task(ingest_job())
    return JSONResponse({"ok": True, "message": "Ingestion started"})

async def ingest_status_handler(request: Request):
    """GET /ingest/status"""
    return JSONResponse({"ok": True, **_ingest_last})

async def mcp_health(request: Request):
    """GET /mcp/health -> optional MCP health endpoint."""
    return JSONResponse({"ok": True})

async def decisions_handler(request: Request):
    """GET /decisions -> inspect what's been approved/rejected so far (debug aid)."""
    return JSONResponse({"ok": True, "decisions": _decisions})

# ========== ROUTES ==========
app.router.add_route("/", ui_handler, methods=["GET"])
app.router.add_route("/mcp/health", mcp_health, methods=["GET"])
app.router.add_route("/ask", ask_handler, methods=["POST"])
app.router.add_route("/ingest", ingest_handler, methods=["POST"])
app.router.add_route("/ingest/status", ingest_status_handler, methods=["GET"])
app.router.add_route("/decisions", decisions_handler, methods=["GET"])