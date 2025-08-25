# Teams Q&A AI (Streamlit + FastAPI + FAISS)

Local prototype to query historical Microsoft Teams channel conversations with RAG.
- One-time/scheduled sync fetches **messages + replies** from 5 fixed Teams channels.
- Embeds and stores in **FAISS** (no scraping at query time).
- Streamlit UI for querying (dropdown to pick channel + text input).
- FastAPI backend for search + LLM answering.
- Extensible: add Jira/Salesforce later as new ingestion pipelines.

## Prereqs
- Python 3.10+
- An Entra ID app with Graph **application permissions**:
  - ChannelMessage.Read.All
  - Team.ReadBasic.All
  - Channel.ReadBasic.All
  - Group.Read.All
  - Grant admin consent
- OpenAI API key (or adapt embeddings/LLM to your provider)

## Setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in TENANT_ID, CLIENT_ID, CLIENT_SECRET, and your 5 channels
```

## Sync Teams Messages (one-time / scheduled)
```bash
python scripts/sync_teams.py
```
This will:
- Pull root channel messages **and** thread replies.
- Store into SQLite at `db/messages.sqlite`.
- Create/refresh FAISS index at `db/faiss_index`.

## Run Services
Backend (FastAPI):
```bash
uvicorn backend.main:app --reload --port 8000
```

UI (Streamlit):
```bash
streamlit run app/ui.py
```

Open http://localhost:8501 and ask a question.

## Notes
- Re-run `sync_teams.py` on a schedule to keep the index current.
- The system never calls Graph at query time — it only searches FAISS.
- To extend with Salesforce/Jira later: add new ingestion scripts that write to the same SQLite + FAISS with `source` metadata.
