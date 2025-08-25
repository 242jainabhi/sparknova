import os
import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI

from db.faiss_store import search_faiss
from backend.embeddings import embed_texts
from dotenv import load_dotenv

# Load .env file
load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
CHAT_MODEL = os.getenv("CHAT_MODEL","gpt-4o-mini")
DB_PATH = os.getenv("DB_PATH","db/messages.sqlite")
FAISS_INDEX = os.getenv("FAISS_INDEX","db/faiss_index")

client = OpenAI(api_key=OPENAI_API_KEY)

def load_channels_from_env():
    no_of_channels = int(os.getenv("NO_OF_CHANNELS", 5))
    channels = []
    for i in range(1, no_of_channels + 1):
        label = os.getenv(f"TEAM_{i}_NAME","").strip()
        chname = os.getenv(f"CHANNEL_{i}_NAME","").strip()
        team_id = os.getenv(f"TEAM_{i}_ID","").strip()
        channel_id = os.getenv(f"CHANNEL_{i}_ID","").strip()
        if label and chname and team_id and channel_id:
            channels.append({
                "label": f"{label} / {chname}",
                "channel_label": f"{label}:{chname}",
                "team_id": team_id,
                "channel_id": channel_id
            })
    print("Loaded channels:", channels)
    return channels

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to ["http://localhost:8501"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")

# Mount Socket.IO to FastAPI without replacing it
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

class QueryRequest(BaseModel):
    query: str
    channel_label: str
    top_k: int = 5

@app.get("/channels")
def channels():
    return {"channels": load_channels_from_env()}

@app.post("/query")
def query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    matches = search_faiss(DB_PATH, FAISS_INDEX, embed_texts, req.query, top_k=min(10, max(1, req.top_k)), channel_filter=req.channel_label)
    if not matches:
        return {"answer": "No matches found. Try re-ingesting or widening your query.", "matches": []}

    context = "\n\n---\n\n".join(m["text"][:2000] for m in matches)

    chat = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role":"system", "content":"You are a helpful support assistant. Use only the provided context to answer. If the answer isn't in context, say you don't know."},
            {"role":"user", "content": f"Question: {req.query}\n\nContext:\n{context}\n\nAnswer concisely with steps if applicable."}
        ],
        temperature=0.2
    )
    answer = chat.choices[0].message.content

    return {
        "answer": answer,
        "matches": [
            {"score": m["score"], "channel_label": m["channel_label"], "snippet": m["text"][:500], "id": m["id"]}
            for m in matches
        ]
    }
