"""
One-off ingest: single Jonathan Goodman chunk on what investors get wrong.
Run once: python ingest_goodman_chunk.py
"""

import os
from pathlib import Path
import requests as http
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SOURCE_URL = "https://www.youtube.com/watch?v=9bEbOEoz0Qs&list=PLZ3xLt17RP6o&index=5"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"

CHUNK = {
    "title": "Jonathan Goodman on What Investors Get Wrong and Active Ownership",
    "content": (
        "Investors have real advantages over strategic investors like Dundee: they can move faster "
        "and exit a position quickly when they identify a problem. A strategic investor sometimes "
        "has to live with a bad position.\n\n"
        "When a company puts out a PEA and the economics aren't working, the stock gets hammered. "
        "To me, that's sometimes a great opportunity — there's still exploration upside, and there "
        "are different ways to attack the problem: different metallurgical approaches, different "
        "mining methods, drilling deeper. Some of these situations get overdone and real "
        "opportunities get created through the process.\n\n"
        "At Dundee, we spend a lot of time working with our investee companies — sometimes rolling "
        "up our sleeves and disagreeing with their approach or pushing them to do something "
        "different. We're not shy or bashful with the companies we invest in.\n\n"
        "What investors most often get wrong: they back people who tell them things that aren't "
        "true — and often those people aren't even trying to lie. The studies they produce are "
        "marketing documents, best-case scenarios, not rigorous engineering. Don't just look at a "
        "track record at face value. Don't say 'they bought a company for a dollar and sold it for "
        "five, they must be smart' — sometimes they were lucky, and the buyer who paid five went "
        "bankrupt because he didn't do his homework. Look deeper: at resumes, backgrounds, and the "
        "full story behind both the successes and the failures."
    ),
}


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
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    existing = supabase.table("knowledge_base").select("id").eq("source_url", SOURCE_URL).limit(1).execute()
    if existing.data:
        print("Already ingested — skipping.")
        return

    print(f"Embedding: {CHUNK['title']}")
    vector = embed(CHUNK["content"])

    supabase.table("knowledge_base").insert({
        "category": "expert_interview",
        "title": CHUNK["title"],
        "content": CHUNK["content"],
        "source_url": SOURCE_URL,
        "speaker": "Jonathan Goodman",
        "embedding": vector,
    }).execute()

    print("Done — 1 chunk added to knowledge base.")


if __name__ == "__main__":
    main()
