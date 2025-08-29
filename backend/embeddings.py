# backend/embeddings.py
# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


# def embed_texts(texts, model="nomic-embed-text"):
#     """
#     Create embeddings for a list of texts using Ollama.
#     Uses a small optimized embedding model and batching.
#     """
#     if not texts:
#         return []

#     # Ollama API: send entire list of texts in one go
#     resp = requests.post(
#         f"{OLLAMA_HOST}/api/embeddings",
#         json={"model": model, "prompt": texts},
#         timeout=120,  # increase timeout if needed
#     )

#     resp.raise_for_status()
#     data = resp.json()

#     # Depending on Ollama version:
#     # - If batching is supported, `data["data"]` is a list of embeddings
#     # - If not, fallback to handling single embedding
#     if "data" in data:
#         return [item["embedding"] for item in data["data"]]
#     elif "embedding" in data:  # single text
#         return [data["embedding"]]
#     else:
#         raise RuntimeError(f"Unexpected embedding response: {data}")





import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def embed_texts(texts, model="mistral"):
    embeddings = []
    for text in texts:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": model, "prompt": text}
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings.append(data["embedding"])
    return embeddings
