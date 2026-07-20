"""
Rewrites each floor plan's template caption into a natural sentence using
Groq's free tier (Llama 3.1 8B Instant) -- same strict, facts-only
constraint as before: only rephrase what's in the room list, never invent
square footage/price/amenities.

Requires:
    pip install groq
    export GROQ_API_KEY=...   (get one free, no card, at console.groq.com/keys)

Usage:
    python polish_captions_groq.py
"""
import json
import time

from groq import Groq
from groq import RateLimitError, APIStatusError

INPUT_JSON = "parsed_floorplans.json"
OUTPUT_JSON = "parsed_floorplans_polished.json"
MODEL = "llama-3.1-8b-instant"  # small/fast model, plenty for simple rewording

# Free tier allows 30 requests/minute -- 2.5s between calls keeps us
# comfortably under that with margin to spare.
SECONDS_BETWEEN_CALLS = 2.5

SYSTEM_PROMPT = """You write ONE natural, plain sentence describing the \
NON-BEDROOM features of a house/apartment floor plan, in a neutral, \
factual tone (like a simple real-estate listing line, not flowery language).

STRICT RULES:
- The bedroom count is handled separately and already stated elsewhere --
  do NOT mention bedrooms or bedroom count in your sentence at all.
- Only mention rooms/features that are explicitly in the provided room list.
- Never invent square footage, price, number of floors, amenities, or \
  location details -- none of that data was provided to you.
- If a room type is "Undefined" or "UserDefined", you may omit it or \
  refer to it generically as "an additional room" -- do not guess what \
  it actually is.
- Keep it to one sentence, plain and clear.
- Do not use the words "cozy", "charming", "stunning", or other real-estate \
  filler adjectives -- stay factual.
"""


def bhk_prefix(bhk_label: str) -> str:
    """
    Authoritative opening clause derived directly from parsed data -- this
    can never be wrong about the bedroom count, since it comes straight
    from counting "Bedroom" polygons, not from anything an LLM claims.
    """
    if bhk_label.startswith("Studio"):
        return "This is a studio/open-plan layout with no separately labeled bedroom."
    count = bhk_label.replace("BHK", "")
    word = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five"}.get(count, count)
    plural = "" if count == "1" else "s"
    return f"This is a {bhk_label} home with {word} bedroom{plural}."


def polish_one(client: Groq, bhk_label: str, rooms: list[str], max_retries: int = 4) -> str:
    non_bedroom_rooms = [r for r in rooms if r != "Bedroom"]
    room_list_str = ", ".join(non_bedroom_rooms) if non_bedroom_rooms else "no other rooms recorded"
    user_prompt = f"Room list (excluding bedrooms, already accounted for): {room_list_str}"
    prefix = bhk_prefix(bhk_label)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=300,
            )
            text = response.choices[0].message.content
            if text:
                return f"{prefix} {text.strip()}"
            print(f"    (empty response on attempt {attempt + 1}, retrying...)")
        except RateLimitError as e:
            wait = 15 * (attempt + 1)
            print(f"    (rate limited: {e}. Waiting {wait}s and retrying...)")
            time.sleep(wait)
        except APIStatusError as e:
            wait = 2 ** attempt
            print(f"    (API error: {e}. Waiting {wait}s and retrying...)")
            time.sleep(wait)

    raise RuntimeError(f"Failed to get a caption after {max_retries} attempts for: {bhk_label}")


def main():
    with open(INPUT_JSON) as f:
        samples = json.load(f)

    try:
        with open(OUTPUT_JSON) as f:
            previous = json.load(f)
        already_done = {s["sample_id"]: s["caption_polished"] for s in previous if "caption_polished" in s}
        print(f"Resuming: found {len(already_done)} already-polished captions from a previous run.")
    except FileNotFoundError:
        already_done = {}

    client = Groq()  # reads GROQ_API_KEY from environment

    # Reattach every previously-completed caption immediately, up front --
    # not incrementally as the loop reaches each one. Doing it incrementally
    # was the bug: if the run was interrupted (or the file was inspected)
    # partway through, samples later in the list hadn't been reattached yet
    # and looked like they'd never been generated at all, even though their
    # captions genuinely existed in already_done the whole time.
    restored = 0
    for sample in samples:
        if sample["sample_id"] in already_done:
            sample["caption_polished"] = already_done[sample["sample_id"]]
            restored += 1
    print(f"Restored {restored} previously-completed captions immediately.")

    # Save right away too, so even if this run is interrupted before
    # generating anything new, the file still reflects everything we
    # already had -- never fewer than we started with.
    with open(OUTPUT_JSON, "w") as f:
        json.dump(samples, f, indent=2)

    for i, sample in enumerate(samples, 1):
        if "caption_polished" in sample:
            print(f"[{i}/{len(samples)}] {sample['sample_id']}: (already done)")
            continue

        polished = polish_one(client, sample["bhk_label"], sample["rooms"])
        sample["caption_polished"] = polished
        print(f"[{i}/{len(samples)}] {sample['sample_id']}: {polished}")
        time.sleep(SECONDS_BETWEEN_CALLS)

        with open(OUTPUT_JSON, "w") as f:
            json.dump(samples, f, indent=2)

    print(f"\nDone. Saved {len(samples)} polished captions to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
