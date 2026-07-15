# Company Knowledge Assistant

A Retrieval-Augmented Generation (RAG) application for answering questions over internal company documents, extended with an **agentic layer** that uses the RAG pipeline as a tool to make automated decisions (e.g. HR expense compliance approvals).

The project has two layers:

1. **RAG Pipeline** — FastAPI + LangChain + OpenAI + Cohere Rerank + PostgreSQL/pgvector + Redis Semantic Cache + LangSmith + RAGAS. Ingests company documents and answers grounded questions over them.
2. **Agentic Layer** — An MCP (Model Context Protocol) server exposes the RAG pipeline and action tools (`approve` / `reject`) to LLM agents. A Streamlit app runs an HR Expense Compliance Agent that reads claims, consults company policy via RAG, and takes actions autonomously.

---

# Features

## RAG Pipeline
- FastAPI backend with a simple web interface
- Document ingestion from PDF, Markdown, DOCX, and TXT files
- Recursive document chunking
- OpenAI embeddings (`text-embedding-3-small`)
- PostgreSQL with pgvector for vector storage
- HNSW indexing for efficient similarity search
- Cohere Rerank for improved retrieval quality
- GPT-4o Mini for answer generation
- Redis Semantic Cache for caching semantically similar queries
- LangSmith tracing for observability and debugging
- RAGAS evaluation pipeline for measuring retrieval quality
- Docker and Docker Compose support

## Agentic Layer
- MCP server (built with `FastMCP`) exposing the RAG pipeline as a callable tool (`rag_ask`)
- Action tools (`approve`, `reject`) that let an agent take real decisions, tied to a `claim_id`
- Streamlit front end (HR Expense Compliance Agent) that:
  - Loads a batch of expense claims from an uploaded JSON file
  - Uses a LangChain agent (`create_agent`) connected to the MCP server via `langchain_mcp_adapters`
  - Retrieves the relevant policy via `rag_ask`, evaluates each claim, and calls `approve` or `reject`
  - Displays a per-claim decision trace, including a debug view of every tool call
- In-memory decision log on the MCP server (`/decisions`) for auditing what was approved/rejected
- Streamable HTTP MCP transport (`/mcp`), so any MCP-compatible agent/client can connect, not just the bundled Streamlit app

---

# Architecture

```text
                    Company Documents
                           │
                           ▼
                  Document Loaders
                           │
                           ▼
                  Text Chunking
                           │
                           ▼
             OpenAI Embeddings
                           │
                           ▼
             PostgreSQL + pgvector
                           │
                           ▼
                Vector Retrieval
                           │
                           ▼
                Cohere Reranker
                           │
                           ▼
           Redis Semantic Cache
                           │
                           ▼
                 GPT-4o Mini
                           │
                           ▼
                      Response
```

## Agentic Layer (built on top of the RAG pipeline)

```text
              Streamlit UI (HR Expense Agent)
                           │
                claims.json uploaded
                           │
                           ▼
            LangChain Agent (create_agent)
                           │
              langchain_mcp_adapters
             (MultiServerMCPClient, streamable_http)
                           │
                           ▼
                     MCP Server
                    (FastMCP /mcp)
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
             rag_ask    approve    reject
                 │
                 ▼
         RAG Pipeline (see diagram above)
                 │
                 ▼
       Policy answer + sources + contexts
                 │
                 ▼
     Agent evaluates claim against policy
                 │
                 ▼
     Calls approve(claim_id) or reject(claim_id)
                 │
                 ▼
        Decision recorded + JSON verdict
           returned to Streamlit UI
```

---

# Tech Stack

| Component | Technology |
|-----------|------------|
| Backend (RAG API) | FastAPI |
| Framework | LangChain |
| LLM | OpenAI GPT-4o Mini |
| Embeddings | OpenAI text-embedding-3-small |
| Vector Database | PostgreSQL + pgvector |
| Vector Index | HNSW |
| Reranking | Cohere Rerank |
| Cache | Redis Semantic Cache |
| Observability | LangSmith |
| Evaluation | RAGAS |
| Agent orchestration | LangChain (`create_agent`) |
| Agent-tool protocol | MCP (`FastMCP`, streamable HTTP) |
| Agent-tool client | `langchain_mcp_adapters` (`MultiServerMCPClient`) |
| Agent front end | Streamlit |
| Containerization | Docker & Docker Compose |

---

# Project Structure

```text
.
├── Dockerfile
├── docker-compose.yml
├── README.md
├── requirements.txt
├── app
│   ├── api.py              # FastAPI app: RAG endpoints + ingest
│   ├── mcp_server.py        # FastMCP server: rag_ask, approve, reject tools + /mcp, /decisions
│   ├── rag.py               # Core RAG pipeline (retrieval, rerank, generation)
│   ├── ingest.py             # Document ingestion job
│   ├── utils.py
│   ├── eval_ragas.py         # RAGAS evaluation pipeline
│   └── static
│       ├── index.html
│       └── style.css
├── agent
│   └── streamlit_app.py      # HR Expense Compliance Agent (Streamlit UI)
├── docs
│   └── screenshots
│       ├── rag-ui.png
│       ├── agentic-ui.png
│       └── langsmith-trace.png
├── data
├── init-db
│   └── init.sql
└── seed
    └── qna_test.json
```

---

# How It Works

## 1. Document Ingestion

When **Ingest Data** is clicked:

1. The frontend sends a `POST /ingest` request.
2. FastAPI starts an asynchronous ingestion job.
3. Documents are loaded from the `data/` directory.
4. Documents are split into chunks.
5. OpenAI embeddings are generated.
6. Chunks are stored in PostgreSQL using pgvector.
7. An HNSW vector index is created for efficient retrieval.

### Supported File Types

- PDF
- Markdown
- DOCX
- TXT

---

## 2. Question Answering (RAG)

When a user asks a question:

1. The frontend sends the question to `POST /ask`.
2. Relevant document chunks are retrieved from PostgreSQL.
3. Cohere Rerank reranks the retrieved chunks.
4. Redis Semantic Cache checks whether a semantically similar question has already been answered.
5. GPT-4o Mini generates an answer using only the retrieved context.
6. The API returns the answer along with the retrieved sources and contexts.

**Screenshot — RAG Web UI:**

![RAG UI](docs/screenshots/rag-ui.png)

---

## 3. Agentic Expense Compliance Workflow

This layer sits on top of the RAG pipeline and turns it into a tool an agent can call, rather than something a human queries directly.

1. The MCP server (`app/mcp_server.py`) starts and exposes three tools over streamable HTTP at `/mcp`:
   - `rag_ask(question, category)` — wraps the RAG pipeline (`answer_with_docs_async`) and returns an answer, sources, and contexts.
   - `approve(claim_id, reason)` — records an approval decision for a specific claim.
   - `reject(claim_id, reason)` — records a rejection decision for a specific claim.
2. The Streamlit app (`agent/streamlit_app.py`) is given a JSON file of expense claims.
3. For each claim, a LangChain agent (built with `create_agent` and connected to the MCP server via `MultiServerMCPClient`) is instructed to:
   - Call `rag_ask` **exactly once** to retrieve the relevant expense policy.
   - Evaluate the claim strictly against that policy.
   - Call **exactly one** of `approve` or `reject`, passing the `claim_id`.
   - Return a final JSON verdict (`decision`, `reason`, optional `violated_clause`).
4. The agent run is bounded by a recursion limit and a hard timeout, so a claim that can't converge fails visibly instead of hanging.
5. Results — including a full per-claim tool-call trace for debugging — are displayed in the Streamlit UI.
6. All decisions are also recorded server-side and can be inspected via `GET /decisions` on the MCP server.

**Screenshot — Agentic UI (Streamlit HR Expense Agent):**

![Agentic UI](docs/screenshots/agentic-ui.png)

---

# Redis Semantic Cache

The application uses **Redis Semantic Cache** through LangChain to reduce repeated LLM calls.

Benefits include:

- Faster responses
- Lower OpenAI API cost
- Reduced latency
- Better user experience

---

# Cohere Rerank

Retrieved document chunks are reranked using Cohere before being passed to the LLM.

Model used:

```text
rerank-multilingual-v3.0
```

Benefits include:

- Improved retrieval precision
- Better answer quality
- Less irrelevant context

---

# LangSmith Integration

LangSmith provides tracing and observability for every LangChain execution.

When enabled, it records:

- Prompt execution
- Retrieval steps
- LLM calls
- Reranking
- Chain execution
- Agent tool calls (`rag_ask`, `approve`, `reject`) when the agentic layer is used

This makes debugging and performance analysis much easier — including tracking down agent loops or non-converging tool calls.

**Screenshot — LangSmith Trace:**

![LangSmith Trace](docs/screenshots/langsmith-trace.png)

---

# Evaluation with RAGAS

The repository includes an evaluation pipeline using **RAGAS**.

Run:

```bash
python app/eval_ragas.py
```

The evaluation pipeline:

1. Reads questions from `seed/qna_test.json`.
2. Sends each question to the `/ask` endpoint.
3. Collects retrieved contexts.
4. Computes RAGAS metrics including:
   - Faithfulness
   - Answer Relevancy
   - Context Precision
   - Context Recall

This helps evaluate retrieval and generation quality over time. RAGAS evaluates the underlying RAG pipeline directly (via `/ask`), independent of whether it's queried by a human or by the agentic layer's `rag_ask` tool.

---

# Local Development

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure environment variables

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"

export REDIS_URL="redis://localhost:6379"

export OPENAI_API_KEY="your_openai_api_key"

export COHERE_API_KEY="your_cohere_api_key"

export LANGSMITH_API_KEY="your_langsmith_api_key"

export LANGSMITH_TRACING=true

export LANGSMITH_PROJECT="company-knowledge-assistant"

export DATA_DIR="data"

# Agentic layer
export MCP_SERVER_URL="http://localhost:8000/mcp"
```

## 3. Start the RAG API + MCP server

The MCP server is mounted on the same FastAPI/Starlette app as the RAG API, so one process serves both:

```bash
uvicorn app.mcp_server:app --reload
```

The application will be available at:

```
http://localhost:8000
```

The MCP endpoint will be available at:

```
http://localhost:8000/mcp
```

## 4. Start the agentic UI (optional)

In a separate terminal, once the server above is running and documents have been ingested:

```bash
streamlit run agent/streamlit_app.py
```

Upload a claims JSON file and click **Run Agent on Claims** to see the agent retrieve policy, evaluate each claim, and approve/reject it via the MCP tools.

---

# Docker

The repository includes a `Dockerfile` and `docker-compose.yml` for running the complete application stack.

Start all services:

```bash
docker compose up --build
```

This starts:

- FastAPI + MCP application
- PostgreSQL with pgvector
- Redis

Open the application at:

```
http://localhost:8000
```

The Streamlit agent UI is not included in Docker Compose by default — run it locally with `streamlit run agent/streamlit_app.py` pointed at the containerized MCP server (`MCP_SERVER_URL=http://localhost:8000/mcp`).

---

# Environment Variables

| Variable | Description |
|-----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis server URL |
| `OPENAI_API_KEY` | OpenAI API key |
| `COHERE_API_KEY` | Cohere API key |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_TRACING` | Enables LangSmith tracing |
| `LANGSMITH_PROJECT` | LangSmith project name |
| `DATA_DIR` | Directory containing company documents |
| `RETRIEVAL_K` | Number of retrieved chunks before reranking (optional) |
| `MCP_SERVER_URL` | URL of the MCP server's `/mcp` endpoint, used by the Streamlit agent |

---

# API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the frontend |
| `/ingest` | POST | Starts document ingestion |
| `/ingest/status` | GET | Returns ingestion status |
| `/ask` | POST | Answers a user question (RAG) |
| `/mcp` | POST/GET/DELETE | Streamable HTTP MCP endpoint exposing `rag_ask`, `approve`, `reject` tools |
| `/mcp/health` | GET | MCP server health check |
| `/decisions` | GET | Lists all approve/reject decisions recorded by the agent, keyed by `claim_id` |

---

# MCP Tools

| Tool | Arguments | Description |
|------|-----------|--------------|
| `rag_ask` | `question: str`, `category: str \| None` | Runs the RAG pipeline and returns `answer`, `sources`, `contexts` |
| `approve` | `claim_id: str`, `reason: str \| None` | Records an approval for the given claim |
| `reject` | `claim_id: str`, `reason: str \| None` | Records a rejection for the given claim |

---

# Future Improvements

- Hybrid Search (BM25 + Vector Search)
- Streaming responses
- Conversation history
- Authentication and authorization
- Source highlighting in the UI
- Automatic document synchronization
- Multi-user support
- Cloud deployment (AWS, Azure, or GCP)
- Persistent (database-backed) decision log instead of in-memory `_decisions`
- Additional agent tools beyond approve/reject (e.g. request-more-info, escalate-to-human)
- Multi-agent workflows (e.g. separate policy-lookup agent and decision agent)
- Streamlit agent packaged into Docker Compose alongside the API