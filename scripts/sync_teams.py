import os
import requests
import msal
import sqlite3
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from db.faiss_store import get_sqlite, build_faiss_from_sqlite
from backend.embeddings import embed_texts

load_dotenv()

GRAPH = "https://graph.microsoft.com/v1.0"
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
DB_PATH = os.getenv("DB_PATH","db/messages.sqlite")
FAISS_INDEX = os.getenv("FAISS_INDEX","db/faiss_index")

def html_to_text(content: str) -> str:
    if not content:
        return ""
    soup = BeautifulSoup(content, "lxml")
    return soup.get_text(separator=" ", strip=True)

def get_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    res = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in res:
        raise RuntimeError(f"Token error: {res}")
    return res["access_token"]

def headers():
    return {"Authorization": f"Bearer {get_token()}"}

def fetch_all_pages(url: str):
    results = []
    while url:
        r = requests.get(url, headers=headers())
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return results

def fetch_channel_messages_with_replies(team_id: str, channel_id: str):
    roots = fetch_all_pages(f"{GRAPH}/teams/{team_id}/channels/{channel_id}/messages")
    threads = []
    for root in roots:
        rid = root.get("id")
        rtext = html_to_text(root.get("body", {}).get("content", ""))
        replies = fetch_all_pages(f"{GRAPH}/teams/{team_id}/channels/{channel_id}/messages/{rid}/replies")
        parts = []
        if rtext:
            parts.append(f"ROOT: {rtext}")
        for rep in replies:
            t = html_to_text(rep.get("body", {}).get("content", ""))
            if t:
                parts.append(f"REPLY: {t}")
        merged = "\n".join(parts).strip()
        threads.append({"root_id": rid, "text": merged})
    return threads

def load_channels_from_env():
    no_of_channels = int(os.getenv("NO_OF_CHANNELS", 5))
    channels = []

    for i in range(1, no_of_channels + 1):
        team_id = os.getenv(f"TEAM_{i}_ID","").strip()
        channel_id = os.getenv(f"CHANNEL_{i}_ID","").strip()
        team_name = os.getenv(f"TEAM_{i}_NAME","").strip()
        channel_name = os.getenv(f"CHANNEL_{i}_NAME","").strip()
        if team_id and channel_id and team_name and channel_name:
            channels.append({
                "team_id": team_id,
                "channel_id": channel_id,
                "channel_label": f"{team_name}:{channel_name}"
            })
    return channels

def upsert_threads(conn: sqlite3.Connection, channel_label: str, team_id: str, channel_id: str, threads: list[dict]):
    cur = conn.cursor()
    for th in threads:
        text = th["text"]
        if not text:
            continue
        cur.execute(
            "INSERT INTO docs (text, channel_label, team_id, channel_id, root_id) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(channel_id, root_id) DO UPDATE SET text=excluded.text, channel_label=excluded.channel_label, team_id=excluded.team_id",
            (text, channel_label, team_id, channel_id, th["root_id"])
        )
    conn.commit()

def main():
    chans = load_channels_from_env()
    if not chans:
        raise SystemExit("No channels configured in .env")

    conn = get_sqlite(DB_PATH)
    total = 0
    for c in chans:
        print(f"Fetching: {c['channel_label']}")
        threads = fetch_channel_messages_with_replies(c["team_id"], c["channel_id"])
        upsert_threads(conn, c["channel_label"], c["team_id"], c["channel_id"], threads)
        print(f"  Upserted {len(threads)} threads.")
        total += len(threads)

    # Rebuild FAISS from all docs
    print("Building FAISS index from SQLite...")
    build_faiss_from_sqlite(DB_PATH, FAISS_INDEX, embed_texts, channel_filter=None)
    print(f"Done. Total threads indexed: {total}")

if __name__ == "__main__":
    main()
