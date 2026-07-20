import json

with open("parsed_floorplans_polished.json") as f:
    data = json.load(f)

with_caption = [s["sample_id"] for s in data if "caption_polished" in s]
without_caption = [s["sample_id"] for s in data if "caption_polished" not in s]

print(f"Total samples in file: {len(data)}")
print(f"With caption: {len(with_caption)}")
print(f"Without caption: {len(without_caption)}")
print()
print("Sample IDs WITH a caption:")
print(with_caption)
print()
print("Sample IDs WITHOUT a caption:")
print(without_caption)
