# Company Knowledge Assistant

A Retrieval-Augmented Generation (RAG) application for answering questions over internal company documents using **FastAPI**, **LangChain**, **OpenAI**, **Cohere Rerank**, **PostgreSQL + pgvector**, **Redis Semantic Cache**, **LangSmith**, and **RAGAS**.

The application provides a simple web interface for ingesting company documents into a vector database and asking grounded questions. Responses are generated strictly from the retrieved document context.

---

# Features

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

---

# Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI |
| Framework | LangChain |
| LLM | OpenAI GPT-4o Mini |
| Embeddings | OpenAI text-embedding-3-small |
| Vector Database | PostgreSQL + pgvector |
| Vector Index | HNSW |
| Reranking | Cohere Rerank |
| Cache | Redis Semantic Cache |
| Observability | LangSmith |
| Evaluation | RAGAS |
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
│   ├── api.py
│   ├── rag.py
│   ├── ingest.py
│   ├── utils.py
│   ├── eval_ragas.py
│   └── static
│       ├── index.html
│       └── style.css
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

## 2. Question Answering

When a user asks a question:

1. The frontend sends the question to `POST /ask`.
2. Relevant document chunks are retrieved from PostgreSQL.
3. Cohere Rerank reranks the retrieved chunks.
4. Redis Semantic Cache checks whether a semantically similar question has already been answered.
5. GPT-4o Mini generates an answer using only the retrieved context.
6. The API returns the answer along with the retrieved sources and contexts.

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

This makes debugging and performance analysis much easier.

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

This helps evaluate retrieval and generation quality over time.

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
```

## 3. Start the application

```bash
uvicorn app.api:app --reload
```

The application will be available at:

```
http://localhost:8000
```

---

# Docker

The repository includes a `Dockerfile` and `docker-compose.yml` for running the complete application stack.

Start all services:

```bash
docker compose up --build
```

This starts:

- FastAPI application
- PostgreSQL with pgvector
- Redis

Open the application at:

```
http://localhost:8000
```

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

---

# API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the frontend |
| `/ingest` | POST | Starts document ingestion |
| `/ingest/status` | GET | Returns ingestion status |
| `/ask` | POST | Answers a user question |

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
