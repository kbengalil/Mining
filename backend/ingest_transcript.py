"""
Ingest a YouTube interview transcript into the RAG knowledge base.

Usage:
    python ingest_transcript.py <youtube_url> "<speaker_name>"

Example:
    python ingest_transcript.py https://www.youtube.com/watch?v=XXXXX "Rick Rule"
"""

import json
import os
import re
import sys
from pathlib import Path

import requests as http
from dotenv import load_dotenv
from supabase import create_client
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"


def extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if not match:
        raise ValueError(f"Could not extract video ID from: {url}")
    return match.group(1)


def fetch_transcript(youtube_url: str) -> str:
    video_id = extract_video_id(youtube_url)
    transcript = YouTubeTranscriptApi().fetch(video_id)
    return " ".join(entry.text for entry in transcript)


def _call_gemini_chunk(prompt: str) -> list[dict]:
    import time
    key = os.environ["GEMINI_API_KEY"]
    for attempt in range(3):
        resp = http.post(
            GEMINI_URL,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            timeout=120,
        )
        if resp.ok:
            break
        print(f"Gemini error {resp.status_code} (attempt {attempt+1}/3): {resp.text[:200]}")
        if attempt < 2:
            time.sleep(30)
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def clean_and_chunk(raw: str, speaker: str) -> list[dict]:
    chunk_size = 10000
    segments = [raw[i:i+chunk_size] for i in range(0, min(len(raw), 40000), chunk_size)]
    all_chunks = []
    for seg_num, segment in enumerate(segments, 1):
        if seg_num > 1:
            time.sleep(15)
        print(f"  Processing segment {seg_num}/{len(segments)}...")
        prompt = f"""You are processing a YouTube interview transcript featuring {speaker}, a mining investment expert.

The raw transcript is auto-generated: missing punctuation, capitalization errors, garbled technical terms.

Your task:
1. Clean the text (fix punctuation, capitalization, and mining/finance terms like NPV, IRR, NI 43-101, capex, opex, PEA, PFS, etc.)
2. Split it into chunks where EACH chunk covers exactly ONE specific topic or idea.
3. Give each chunk a descriptive title that includes the speaker name.
4. Remove filler words, repeated phrases, and off-topic small talk.

Return ONLY a valid JSON array — no markdown, no explanation:
[
  {{"title": "{speaker} on jurisdiction risk", "content": "...cleaned text..."}},
  {{"title": "{speaker} on management quality", "content": "...cleaned text..."}}
]

Raw transcript segment:
{segment}"""
        all_chunks.extend(_call_gemini_chunk(prompt))
    return all_chunks


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
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    youtube_url = sys.argv[1]
    speaker = sys.argv[2]
    preview = "--preview" in sys.argv

    print(f"Fetching transcript: {youtube_url}")
    raw = fetch_transcript(youtube_url)
    print(f"  {len(raw)} characters fetched.")

    print("Cleaning and chunking with Gemini...")
    chunks = clean_and_chunk(raw, speaker)
    print(f"  {len(chunks)} chunks created.\n")

    if preview:
        for i, chunk in enumerate(chunks, 1):
            print(f"{'='*60}")
            print(f"CHUNK {i}/{len(chunks)}: {chunk['title']}")
            print(f"{'='*60}")
            print(chunk["content"])
            print()
        print("Preview only — nothing was inserted. Run without --preview to save to the knowledge base.")
        return

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    existing = supabase.table("knowledge_base").select("id").eq("source_url", youtube_url).limit(1).execute()
    if existing.data:
        print(f"Already ingested — skipping. This URL is already in the knowledge base.")
        return

    print("Embedding and inserting into knowledge base...")
    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] {chunk['title']}")
        vector = embed(chunk["content"])
        supabase.table("knowledge_base").insert({
            "category": "expert_interview",
            "title": chunk["title"],
            "content": chunk["content"],
            "source_url": youtube_url,
            "embedding": vector,
        }).execute()

    print(f"\nDone! {len(chunks)} chunks added to the RAG knowledge base.")


if __name__ == "__main__":
    main()
