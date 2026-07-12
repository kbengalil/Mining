"""
Backfill the `speaker` column in knowledge_base by reading chunk titles.
The ingest scripts prefix every title with the speaker name (e.g. "Rick Rule on X").
"""

import os
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# Known speakers — order matters (longer/more specific first)
KNOWN_SPEAKERS = [
    "Rick Rule",
    "Kevin McLean",
    "David Lotan",
    "Don Durant",
    "Bob Quartermain",
]

def detect_speaker(titles: list[str]) -> str | None:
    votes = defaultdict(int)
    for title in titles:
        for speaker in KNOWN_SPEAKERS:
            if speaker.lower() in title.lower():
                votes[speaker] += 1
    if not votes:
        return None
    return max(votes, key=votes.__getitem__)

# Load all rows
rows = sb.table("knowledge_base").select("id, title, source_url, speaker").execute().data
print(f"Total rows: {len(rows)}\n")

# Group by source_url
by_source = defaultdict(list)
for r in rows:
    by_source[r["source_url"]].append(r)

# Detect speaker per source and update
for source, chunks in sorted(by_source.items(), key=lambda x: -(len(x[1]))):
    titles = [c["title"] for c in chunks]
    speaker = detect_speaker(titles)
    ids = [c["id"] for c in chunks]

    print(f"Source: {source}")
    print(f"  Chunks: {len(chunks)}  ->  Speaker: {speaker}")

    if speaker:
        sb.table("knowledge_base").update({"speaker": speaker}).in_("id", ids).execute()
        print(f"  OK Updated {len(ids)} rows")
    else:
        print(f"  UNKNOWN - Could not detect speaker - manual fix needed")
    print()

print("Done.")
