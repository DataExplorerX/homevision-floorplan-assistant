"""
Checks every caption for a number-word mismatch against its authoritative
bhk_label (which comes directly from parsed room polygons, not from the
LLM). This catches cases where the caption-polishing model miscounted or
misstated the number of bedrooms despite being told to stick to the facts.
"""
import json
import re

WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8,
}

with open("parsed_floorplans_polished.json") as f:
    data = json.load(f)

mismatches = []

for sample in data:
    bhk_label = sample["bhk_label"]
    caption = sample["caption_polished"].lower()

    match = re.match(r"(\d+)bhk", bhk_label.lower())
    if not match:
        continue  # skip Studio/Open-plan entries, nothing numeric to check
    expected_count = int(match.group(1))

    # Look for "<number-word> bedroom" or "<digit> bedroom" anywhere in the caption
    found_counts = set()
    for word, num in WORD_TO_NUM.items():
        if re.search(rf"\b{word}[\s-]bedroom", caption):
            found_counts.add(num)
    for digit_match in re.finditer(r"\b(\d+)[\s-]bedroom", caption):
        found_counts.add(int(digit_match.group(1)))

    if found_counts and expected_count not in found_counts:
        mismatches.append({
            "sample_id": sample["sample_id"],
            "expected": expected_count,
            "caption_says": sorted(found_counts),
            "caption": sample["caption_polished"],
        })

print(f"Checked {len(data)} samples.")
print(f"Found {len(mismatches)} bedroom-count mismatches:\n")
for m in mismatches:
    print(f"  {m['sample_id']}: bhk_label says {m['expected']}BHK, caption implies {m['caption_says']}")
    print(f"    caption: {m['caption']}\n")
