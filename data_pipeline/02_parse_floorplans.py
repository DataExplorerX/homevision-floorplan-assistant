"""
Parse every sample in a CubiCasa5k subset folder, extract its room list from
model.svg, derive a BHK (bedroom) count, and print a summary so we can sanity
-check the parsing logic across many real samples before building anything
on top of it.

Usage (from the folder containing cubicasa5k_subset_v2/):
    python parse_floorplans.py
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

SUBSET_ROOT = Path("cubicasa5k_subset_v2/cubicasa5k/high_quality_architectural")
OUTPUT_JSON = "parsed_floorplans.json"


def strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def extract_rooms(svg_path: Path) -> list[str]:
    """
    Returns a list of room-type strings, e.g. ["Bedroom", "Bedroom", "Bath",
    "Kitchen Kitchenette", "LivingRoom"], one entry per <g class="Space ...">
    element found. "Undefined" spaces are kept (as "Undefined") since they're
    real rooms in the drawing whose type just wasn't specified by the
    original annotator -- we don't want to silently drop them and undercount
    a unit's total room count.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    rooms = []
    for elem in root.iter():
        if strip_ns(elem.tag) != "g":
            continue
        cls = elem.attrib.get("class", "")
        tokens = cls.split()
        if tokens and tokens[0] == "Space":
            room_type = " ".join(tokens[1:]) if len(tokens) > 1 else "Undefined"
            rooms.append(room_type)
    return rooms


def is_likely_multi_unit(rooms: list[str]) -> bool:
    """
    Detects floor plans that likely represent an entire multi-unit building
    floor (common in CubiCasa5k's Finnish apartment-building samples) rather
    than a single dwelling -- which would otherwise get a misleading BHK
    label (e.g. "1BHK" derived from the one Bedroom-tagged room found
    anywhere in a file that actually contains several merged apartments).

    Signal: more than one EXACT "Kitchen" room. A single dwelling
    essentially never has two full kitchens. Note this must be an exact
    match, not a substring check -- "Kitchen Scullery" (a legitimate
    secondary prep room attached to ONE kitchen) would otherwise cause
    false positives on entirely normal single-family homes.
    """
    kitchen_count = sum(1 for r in rooms if r == "Kitchen")
    return kitchen_count > 1


def derive_bhk_label(rooms: list[str]) -> str:
    bedroom_count = sum(1 for r in rooms if r == "Bedroom")
    if bedroom_count == 0:
        # No explicit bedroom -- likely a studio, or bedroom function is
        # folded into a LivingRoom/Undefined space. Being honest about this
        # rather than guessing a bedroom count that isn't actually labeled.
        return "Studio/Open-plan (no separate bedroom labeled)"
    return f"{bedroom_count}BHK"


def build_caption(rooms: list[str], bhk_label: str) -> str:
    """A simple, factual, template-based caption -- deliberately not an LLM
    call, so the caption can never contain a fact that isn't actually in the
    parsed room list. (We can optionally have an LLM *rephrase* this more
    naturally later, but the underlying facts should always come from here,
    not be invented by a model.)"""
    if not rooms:
        return f"{bhk_label}. No room data available."

    room_counts: dict[str, int] = {}
    for r in rooms:
        room_counts[r] = room_counts.get(r, 0) + 1

    parts = []
    for room_type, count in room_counts.items():
        label = room_type if room_type != "Undefined" else "unspecified room"
        parts.append(f"{count} {label}" if count > 1 else label)

    return f"{bhk_label} with " + ", ".join(parts) + "."


def main():
    if not SUBSET_ROOT.exists():
        raise SystemExit(f"Can't find {SUBSET_ROOT} -- check you're running this from the right folder.")

    sample_dirs = sorted(p for p in SUBSET_ROOT.iterdir() if p.is_dir())
    print(f"Found {len(sample_dirs)} sample folders under {SUBSET_ROOT}")

    results = []
    bhk_tally: dict[str, int] = {}
    excluded_multi_unit = []

    for sample_dir in sample_dirs:
        svg_path = sample_dir / "model.svg"
        image_path = sample_dir / "F1_scaled.png"
        if not svg_path.exists() or not image_path.exists():
            continue

        rooms = extract_rooms(svg_path)

        if is_likely_multi_unit(rooms):
            excluded_multi_unit.append(sample_dir.name)
            continue

        bhk_label = derive_bhk_label(rooms)
        caption = build_caption(rooms, bhk_label)

        results.append({
            "sample_id": sample_dir.name,
            "image_path": str(image_path),
            "rooms": rooms,
            "bhk_label": bhk_label,
            "caption": caption,
        })
        bhk_tally[bhk_label] = bhk_tally.get(bhk_label, 0) + 1

    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nParsed {len(results)} samples successfully. Saved to {OUTPUT_JSON}")
    if excluded_multi_unit:
        print(f"Excluded {len(excluded_multi_unit)} likely multi-unit floor plans "
              f"(2+ exact 'Kitchen' rooms): {excluded_multi_unit}")
    print("\n=== BHK distribution across this subset ===")
    for label, count in sorted(bhk_tally.items(), key=lambda x: -x[1]):
        print(f"  {count:3d}  {label}")

    print("\n=== First 5 parsed samples (full detail) ===")
    for r in results[:5]:
        print(f"\nsample_id: {r['sample_id']}")
        print(f"  rooms: {r['rooms']}")
        print(f"  caption: {r['caption']}")


if __name__ == "__main__":
    main()