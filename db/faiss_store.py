import os
import sqlite3
import numpy as np
import faiss

def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)

def get_sqlite(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            channel_label TEXT NOT NULL,
            team_id TEXT,
            channel_id TEXT,
            root_id TEXT,
            UNIQUE(channel_id, root_id) ON CONFLICT REPLACE
        );
    """)
    return conn

def save_faiss(index_dir: str, index: faiss.Index, ids: np.ndarray):
    ensure_dirs(index_dir)
    faiss.write_index(index, os.path.join(index_dir, "index.faiss"))
    np.save(os.path.join(index_dir, "ids.npy"), ids)

def load_faiss(index_dir: str):
    index_path = os.path.join(index_dir, "index.faiss")
    ids_path = os.path.join(index_dir, "ids.npy")
    if not (os.path.exists(index_path) and os.path.exists(ids_path)):
        return None, None
    index = faiss.read_index(index_path)
    ids = np.load(ids_path)
    return index, ids

def build_faiss_from_sqlite(db_path: str, index_dir: str, embed_fn, channel_filter: str | None = None):
    conn = get_sqlite(db_path)
    cur = conn.cursor()
    if channel_filter:
        cur.execute("SELECT id, text FROM docs WHERE channel_label = ? ORDER BY id", (channel_filter,))
    else:
        cur.execute("SELECT id, text FROM docs ORDER BY id")
    rows = cur.fetchall()
    if not rows:
        return None, None

    ids = np.array([r[0] for r in rows], dtype=np.int64)
    texts = [r[1] for r in rows]

    vectors = np.array(embed_fn(texts), dtype="float32")
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)  # cosine-like if vectors are normalized by model
    index.add(vectors)
    save_faiss(index_dir, index, ids)
    return index, ids

def search_faiss(db_path: str, index_dir: str, embed_fn, query: str, top_k: int = 5, channel_filter: str | None = None):
    index, ids = load_faiss(index_dir)
    if index is None or ids is None:
        # try to build if missing
        index, ids = build_faiss_from_sqlite(db_path, index_dir, embed_fn, channel_filter=None)
        if index is None:
            return []

    qvec = np.array(embed_fn([query]), dtype="float32")
    D, I = index.search(qvec, top_k)
    matches = []
    conn = get_sqlite(db_path)
    cur = conn.cursor()
    for rank, idx in enumerate(I[0]):
        if idx < 0 or idx >= len(ids):
            continue
        row_id = int(ids[idx])
        if channel_filter:
            cur.execute("SELECT id, text, channel_label, team_id, channel_id, root_id FROM docs WHERE id = ? AND channel_label = ?", (row_id, channel_filter))
        else:
            cur.execute("SELECT id, text, channel_label, team_id, channel_id, root_id FROM docs WHERE id = ?", (row_id,))
        rec = cur.fetchone()
        if not rec:
            continue
        matches.append({
            "id": rec[0],
            "text": rec[1],
            "channel_label": rec[2],
            "team_id": rec[3],
            "channel_id": rec[4],
            "root_id": rec[5],
            "score": float(D[0][rank])
        })
    return matches
