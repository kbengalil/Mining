"""
One-off script: ingest Rick Rule Symposium transcript chunks into the RAG knowledge base.
Run once: python ingest_rick_rule_symposium.py
"""

import os
import time
from dotenv import load_dotenv
from pathlib import Path
import requests
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
SOURCE_URL = "https://www.youtube.com/watch?v=2mTjXPc6KlU"

CHUNKS = [
    {
        "title": "Junior Mining: Knowledge Business, Not Asset Business",
        "category": "management",
        "content": """Rick Rule on why junior mining companies are fundamentally knowledge businesses:

"People make a mistake that the juniors are asset-centric businesses. They're not. They're knowledge businesses. Investing in exploration is the same as investing in technology. It's answering a series of unanswered questions. So the science is more important than the molecule."

This means when evaluating a junior miner, the quality of the people — geologists, management — matters more than the asset itself. A great team with a mediocre asset will outperform a poor team with a great asset.""",
    },
    {
        "title": "The Top 1% Mining Operators: Serial Success",
        "category": "management",
        "content": """Rick Rule on identifying the elite 1% of mining operators:

"The 1% have names. The Lines, the Freelands, the Quartermains, the Rossbitys. There are groups of people who have built institutions, organizations that have been serially successful over 30 years."

Example: Ross Beaty — Rick has been involved in 14 Ross Beaty companies over 35 years. 12 of 14 have been 10-baggers or better.

Key criteria:
- You want management teams, not just the chief ego — the entire organization must have a track record of serial success
- The success must be applicable to the task at hand. Someone successful in gold mining may or may not succeed in oil and gas exploration
- The rare compound operator (geology + finance) — like Ross Beaty or Bob Quartermain — is the most valuable find

The hybrid operator who understands both the geology and the capital markets is extremely rare and extremely valuable in junior mining.""",
    },
    {
        "title": "Three Investor Mistakes in Junior Mining",
        "category": "investor_framework",
        "content": """Rick Rule on the three most common mistakes junior mining investors make:

1. LAZINESS — "Money is made on the delta between price and value. If you don't spend enough time to identify what something is worth, its price is meaningless. It has no meaning."

2. PATIENCE — "If enjoying a 10-bagger takes 5 years and you allocate 3 months, you're going to fail." Building a company and enjoying a 10-fold return is more often than not a 5 or 6 year job.

3. TENACITY — "In most of the 10-baggers I've enjoyed in my career, I've been exposed to a 50% price decline in the stock while I owned the stock. It takes a strong opinion of value to hold a stock and buy more during a 50% price decline."

"Most investors prefer to feel as opposed to think. Which is why most investors fail. Your opinion about something is irrelevant if it's not an informed opinion." """,
    },
    {
        "title": "The Paladin Investment Framework: Buying in Hated Sectors",
        "category": "investor_framework",
        "content": """Rick Rule's most important investment — Paladin Energy — illustrates the full junior mining investment process:

THE SETUP: Uranium had been in a bear market for 20 years. "When people thought of it, they thought of Hiroshima and Nagasaki and Three-Mile Island. It wasn't that they were bored of it, they hated it — which is why I liked it. I knew it was cheap."

THE OPERATOR: John Borshoff had a 1.8 million AUD market cap and no money. But he had a billion-dollar geological database given to him as severance from a West German uranium company. "I don't have to explore. I just have to stake stuff I already discovered." Rick's response: "That's the best answer I ever heard."

THE FINANCING: $2 million placement when market cap was $1.8M — instantly owned ~50% of the company. Plus warrants at 12.5 cents.

THE DRAWDOWN: Stock went from 10 cents to a penny. "If you own a stock at a dime and it's selling for a penny, you don't have a hold. You have a buy or you have a sell." Rick revisited all his premises, decided he was right and the market was wrong, and bought more.

THE RESULT: Stock moved from half a cent to $10 in seven years. With a live 12.5-cent warrant in a $3 market: "That's as much fun as an old man can have with his clothes on."

THE LESSON: Enter in hate. Back a zealot. Revisit your thesis when challenged. Have the courage of your convictions. Know when to sell (he sold near $10; it then fell to 60 cents).""",
    },
    {
        "title": "Private Placements and Warrants: Only Work in Bear Markets",
        "category": "investor_framework",
        "content": """Rick Rule on private placements and warrants:

A private placement is a direct share sale to a small group of investors at a negotiated price — bypassing the public market. Shares are typically restricted (can't be sold) for 4-6 months.

A warrant is a bonus attached to the placement: the right to buy additional shares at a fixed price in the future. If the stock rises significantly, the warrant becomes extremely valuable.

WHY BEAR MARKETS ONLY: "In bull markets like this, when you want to invest, everybody else wants to invest too. And you can't get good financing terms. Right now, I'm doing almost no private placements because people aren't giving me warrants."

"Why would I sign up to get restricted stock when I could get free stock in the market if I don't get a warrant?"

Bear markets flip the leverage: companies are desperate for capital, so sophisticated investors can negotiate discounts and warrants. Bull markets eliminate this edge entirely.

The Paladin warrant (12.5 cents, exercisable when stock was at $3) illustrates the optionality value: a warrant is a legally guaranteed right to buy at the old price no matter how high the stock goes.""",
    },
    {
        "title": "Prospect Generator Model: The Arithmetically Predictable Path to 100-Baggers",
        "category": "business_model",
        "content": """Rick Rule on the prospect generator model in junior mining:

THE PROBLEM WITH EXPLORATION: "The probability of success in exploration, as defined in my first year geology course 50 years ago, is that one in 3,000 anomalies becomes a mine." Backing the right scientists can cut those odds to roughly 1 in 50 — still very long.

THE PROSPECT GENERATOR SOLUTION: Instead of drilling one project with all your money, a prospect generator company:
1. Uses geological expertise to identify and acquire promising land packages
2. Options those packages to larger mining companies
3. The major pays for ALL the expensive drilling to earn a majority stake
4. The prospect generator retains 20-30% of each project — for free

"Rather than having a whole lottery ticket, you get 30% of a lottery ticket, but somebody else bought you the ticket."

WHY IT WORKS MATHEMATICALLY: With 1-in-50 odds and 30 projects (all drilled at others' expense), you statistically own pieces of multiple winners. "For somebody who wants to occasionally enjoy a hundred-bagger rather than a ten-bagger, the only arithmetically predictable way to do that is in the prospect generators."

Rick owns all 17 publicly listed pure prospect generators. Known names include: Altius Minerals, Almaden Minerals, Riverside Resources, Eurasian Minerals (EMX), Lara Exploration, Millrock Resources, Transition Metals.

The key differentiator: the prospect generator does NOT continuously dilute shareholders to fund drilling — the partner pays for it.""",
    },
    {
        "title": "Investing in Hated Commodities: Where Easy Money Is Made",
        "category": "commodity_analysis",
        "content": """Rick Rule on contrarian commodity investing:

"The easy money is made when stuff is hated. There's no easy money left in the sector. There are certain sectors that in the next 10 years under almost any scenario will do well, but the easy money has all been made."

"You make the most money in a hated sector. Uranium was truly a hated sector. It had been a bear market for 20 years. When people thought of it, they thought of Hiroshima and Nagasaki. It wasn't that they were bored of it — they hated it. Which is why I liked it."

On identifying hated commodities:
- Lead: "The only commodity in the world that is still hated — the only major commodity — is probably lead." Note: many lead-zinc-silver deposits are disguised as silver plays. "These silver projects are often lead projects in drag."
- When something is in hate, the investor universe is small, the sellers are exhausted, and any positive development creates outsized price moves

The process: identify the hated commodity → find the best operator in that space → finance them in a bear market (with warrants) → wait 5 years → sell into euphoria.""",
    },
]


def embed(text: str) -> list[float]:
    key = os.environ["GEMINI_API_KEY"]
    resp = requests.post(
        f"{GEMINI_EMBED_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={"content": {"parts": [{"text": text}]}, "outputDimensionality": 768},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    for i, chunk in enumerate(CHUNKS):
        print(f"[{i+1}/{len(CHUNKS)}] Embedding: {chunk['title']}")
        vector = embed(chunk["title"] + "\n\n" + chunk["content"])
        sb.table("knowledge_base").insert({
            "title": chunk["title"],
            "category": chunk["category"],
            "content": chunk["content"],
            "embedding": vector,
            "source_url": SOURCE_URL,
        }).execute()
        print(f"  OK Inserted")
        time.sleep(1)  # avoid rate limits

    print(f"\nDone. {len(CHUNKS)} chunks inserted.")


if __name__ == "__main__":
    main()
