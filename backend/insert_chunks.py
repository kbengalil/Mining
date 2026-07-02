"""Insert pre-processed chunks from temp_chunks.json into the knowledge base."""
import json
import os
import sys
from pathlib import Path

import requests as http
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"


def embed(text: str) -> list[float]:
    key = os.environ["GEMINI_API_KEY"]
    resp = http.post(
        f"{EMBED_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={"content": {"parts": [{"text": text}]}, "outputDimensionality": 768},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def main():
    source_url = sys.argv[1] if len(sys.argv) > 1 else None
    chunks_file = Path(__file__).parent / "temp_chunks.json"
    chunks = json.loads(chunks_file.read_text(encoding="utf-8"))

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    if source_url:
        existing = supabase.table("knowledge_base").select("id").eq("source_url", source_url).limit(1).execute()
        if existing.data:
            print("Already ingested — skipping.")
            return

    print(f"Inserting {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] {chunk['title']}")
        vector = embed(chunk["content"])
        supabase.table("knowledge_base").insert({
            "category": "expert_interview",
            "title": chunk["title"],
            "content": chunk["content"],
            "source_url": source_url,
            "embedding": vector,
        }).execute()

    print(f"\nDone! {len(chunks)} chunks added.")


if __name__ == "__main__":
    main()
