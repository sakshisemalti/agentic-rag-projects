# Company Knowledge Assistant

Company Knowledge Assistant is a simple web-based Retrieval-Augmented Generation (RAG) app for company documents. The UI lets you ingest files into a Postgres-backed vector store and ask questions that are answered from cached document context.

## How it works

- The browser UI is served from `app/static/index.html`.
- Clicking **Ingest Data** calls `POST /ingest` on `app/api.py`.
- `app/api.py` calls `app/ingest.py`, which loads documents from `data/`, chunks them, and writes vectors into Postgres via `app/utils.py`.
- Clicking **Ask** calls `POST /ask` on `app/api.py`.
- `app/api.py` uses `app/rag.py` to build a retrieval chain, query the vector store, rerank with Cohere, and generate an answer with OpenAI.
- Redis is used as a semantic cache via `langchain_redis.RedisSemanticCache` in `app/rag.py`.
- Evaluation is done through `app/eval_ragas.py`, which uses `ragas` and OpenAI to score QA responses against `seed/qna_test.json`.

## Quick start

### Local development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables for Postgres, Redis, and OpenAI:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
export REDIS_URL="redis://localhost:6379"
export OPENAI_API_KEY="sk-..."
```

3. Start the app server:

```bash
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

4. Open the UI at:

```bash
http://localhost:8000
```

### Docker / Compose

The project includes `docker-compose.yml` with three services:

- `postgres` for the vector database with `pgvector`
- `redis` for semantic caching
- `app` for the FastAPI service

Start the stack with:

```bash
docker-compose up --build
```

Then open `http://localhost:8000`.

## Usage

- Use the UI **Ingest Data** button to load documents from the `data/` directory and build the vector index in Postgres.
- Use the UI **Ask** button to submit a question. The app routes the query through `app/rag.py` and returns an answer with source context.
- The ingest status is visible in the UI and updates as the background process runs.

## Evaluation

- `python app/eval_ragas.py` runs an evaluation loop using `ragas`.
- It sends a sample question to `/ask`, collects the answer, and evaluates faithfulness, answer relevance, and retrieval precision/recall.
- This script is not required for normal app usage, but it is useful for dashboard/testing of model performance.

## Project layout

```
.
├── Dockerfile
├── docker-compose.yml
├── README.md
├── requirements.txt
├── app
│   ├── api.py
│   ├── eval_ragas.py
│   ├── ingest.py
│   ├── rag.py
│   ├── utils.py
│   └── static
│       ├── index.html
│       └── style.css
├── data
│   ├── announcements
│   ├── faqs
│   │   ├── travel-faq.txt
│   │   └── vpn-faq.md
│   ├── guides
│   │   └── vpn-setup.md
│   ├── handbooks
│   └── policies
├── init-db
│   └── init.sql
└── seed
    └── qna_test.json
```

## Environment variables

- `DATABASE_URL` — Postgres connection string used by `app/utils.py`.
- `REDIS_URL` — Redis URL used by `app/rag.py` for semantic caching.
- `OPENAI_API_KEY` — OpenAI key used by the QA and evaluation flows.
- `DATA_DIR` — Optional custom data directory (default: `data`).

## Notes

- The UI and API are not separate repos or services; the FastAPI app serves both the frontend and backend from `app/api.py`.
- Ingestion happens through `app/ingest.py` and the Postgres vector store configured in `app/utils.py`.
- Retrieval answers are generated in `app/rag.py`, with reranking via Cohere and caching via Redis.
- `docker-compose.yml` builds and runs the full stack including Postgres, Redis, and the FastAPI app.
