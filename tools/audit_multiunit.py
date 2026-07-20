"""
Flags samples that likely represent a whole multi-unit building floor
rather than a single dwelling -- using duplicate "kitchen-like" rooms as
the signal, since a genuine single home essentially never has more than
one kitchen.
"""
import json
from collections import Counter

with open("parsed_floorplans.json") as f:
    data = json.load(f)

suspicious = []

for sample in data:
    kitchen_count = sum(1 for r in sample["rooms"] if r == "Kitchen")  # exact match, not substring
    if kitchen_count > 1:
        suspicious.append((sample["sample_id"], sample["bhk_label"], kitchen_count, sample["rooms"]))

print(f"Checked {len(data)} samples.")
print(f"Found {len(suspicious)} likely multi-unit floor plans (2+ kitchens):\n")
for sample_id, bhk_label, kitchen_count, rooms in suspicious:
    print(f"  {sample_id} (labeled {bhk_label}): {kitchen_count} kitchen-type rooms")
    print(f"    full room list: {rooms}\n")