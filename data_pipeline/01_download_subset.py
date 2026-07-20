"""
Selectively download a small subset of the CubiCasa5k dataset without
pulling the entire 5.5GB zip file.

How this works: the zip file format stores a "central directory" -- a table
of contents -- at the END of the file, listing every entry and exactly which
byte range it occupies. The `remotezip` library fetches just that small
central directory first (via an HTTP range request for the end of the
file), then lets us request only the specific entries we actually want,
each fetched with its own small range request. Zenodo's storage backend
supports this, so we never have to pull the full archive.

Usage:
    pip install remotezip
    python download_subset.py
"""
from remotezip import RemoteZip

ZENODO_URL = "https://zenodo.org/records/2613548/files/cubicasa5k.zip?download=1"
OUTPUT_DIR = "cubicasa5k_subset_v2"
NUM_SAMPLES = 60
PREFERRED_SUBSETS = ["high_quality_architectural", "high_quality", "colorful"]


def main():
    print("Connecting to remote zip (this only reads the file listing, not the data)...")
    with RemoteZip(ZENODO_URL) as zf:
        all_names = zf.namelist()
        print(f"Total entries in archive: {len(all_names)}")

        sample_folders = sorted({
            "/".join(name.split("/")[:3])
            for name in all_names
            if name.count("/") >= 2 and not name.endswith("/")
        })

        # Report how many distinct samples exist per subset, so we can see
        # the real distribution instead of assuming.
        from collections import Counter
        subset_counts = Counter(f.split("/")[1] for f in sample_folders)
        print(f"Samples per subset: {dict(subset_counts)}")

        # Pick samples preferring high_quality_architectural first, falling
        # back to the other subsets only if we still need more.
        chosen_folders = []
        for subset in PREFERRED_SUBSETS:
            if len(chosen_folders) >= NUM_SAMPLES:
                break
            matching = [f for f in sample_folders if f.split("/")[1] == subset]
            needed = NUM_SAMPLES - len(chosen_folders)
            chosen_folders.extend(matching[:needed])

        chosen_folders = set(chosen_folders)
        entries_to_extract = [
            name for name in all_names
            if "/".join(name.split("/")[:3]) in chosen_folders
        ]

        print(f"Extracting {len(entries_to_extract)} files "
              f"from {len(chosen_folders)} sample folders into {OUTPUT_DIR}/ ...")
        print("(fetching one file at a time over the network -- this prints progress as it goes)")

        import os
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for i, name in enumerate(entries_to_extract, 1):
            zf.extract(name, path=OUTPUT_DIR)
            if i % 20 == 0 or i == len(entries_to_extract):
                print(f"  {i}/{len(entries_to_extract)} files fetched...")

    print("Done. Run this to inspect the structure:")
    print(f"  find {OUTPUT_DIR} -maxdepth 4 | head -30")


if __name__ == "__main__":
    main()
