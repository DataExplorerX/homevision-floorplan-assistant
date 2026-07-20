"""
Parses a natural-language floor plan request into two parts:
  1. bhk_filter -- an exact structured filter (e.g. "2BHK"), or None if the
     user didn't specify a bedroom count.
  2. semantic_query -- the remaining "soft" description (balcony, style,
     layout feel) to rank results by similarity.

This split matters because bedroom count is a hard fact that embeddings are
bad at enforcing exactly (see the earlier test where a Studio outranked an
actual 2BHK for a "2 bedroom" query) -- so we pull it out and apply it as a
precise SQL filter instead, and let semantic search do only the job it's
actually good at: ranking by soft, descriptive qualities.
"""
import json

from groq import Groq

MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You extract structured information from a house-hunting \
request. Respond with ONLY a JSON object, no other text, in this exact shape:

{"bhk_filter": "1BHK" | "2BHK" | "3BHK" | "4BHK" | "Studio" | null, "semantic_query": "<string>"}

Rules:
- bhk_filter: if the user specifies a bedroom count (e.g. "2 bedroom", \
  "two-bedroom", "2BHK", "3 bed"), set it to the matching label. If they \
  say "studio" or "no separate bedroom" or "open-plan with no bedroom", \
  use "Studio". If they don't mention bedroom count or layout type at all, \
  use null.
- semantic_query: the rest of the request describing amenities, style, or \
  layout feel (e.g. "with a balcony", "modern kitchen", "open plan") --
  strip out the bedroom-count phrase itself since that's handled separately.
  If nothing else was said, just restate the general request.
- Never include markdown code fences, explanations, or any text outside \
  the JSON object itself.
"""


def parse_query(client: Groq, user_message: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=200,
        temperature=0,  # deterministic -- this is a structured extraction task, not creative writing
    )
    raw = response.choices[0].message.content.strip()

    # Small defensive cleanup in case the model wraps the JSON in code fences
    # despite being told not to -- cheap insurance, models don't always
    # follow formatting instructions perfectly.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


if __name__ == "__main__":
    # Quick manual test -- run this file directly to try a few examples.
    import os

    client = Groq()  # reads GROQ_API_KEY from environment
    test_messages = [
        "show me a 2 bedroom apartment with a balcony",
        "I want a small studio with just one bathroom",
        "a big house with 4 bedrooms and a garage",
        "something with a nice open kitchen",
    ]
    for msg in test_messages:
        result = parse_query(client, msg)
        print(f"\"{msg}\"\n  -> {result}\n")
