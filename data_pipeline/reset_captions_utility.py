"""
Removes the caption_polished field from the first N samples, so the next
run of polish_captions_groq.py treats them as not-yet-done and regenerates
them -- fixing the truncated captions left over from the earliest (broken,
150-token) Gemini run.
"""
import json

FILE = "parsed_floorplans_polished.json"
NUM_TO_RESET = 60

with open(FILE) as f:
    data = json.load(f)

for sample in data[:NUM_TO_RESET]:
    sample.pop("caption_polished", None)

with open(FILE, "w") as f:
    json.dump(data, f, indent=2)

remaining = sum(1 for s in data if "caption_polished" in s)
print(f"Cleared captions for the first {NUM_TO_RESET} samples.")
print(f"{remaining}/{len(data)} samples still have a caption -- these will be skipped on the next run.")
