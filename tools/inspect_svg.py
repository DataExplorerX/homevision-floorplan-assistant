import xml.etree.ElementTree as ET
from collections import Counter

path = "cubicasa5k_subset_v2/cubicasa5k/high_quality_architectural/10096/model.svg"

tree = ET.parse(path)
root = tree.getroot()

# SVGs use XML namespaces, which makes tag names look like
# '{http://www.w3.org/2000/svg}g' instead of just 'g'. Strip that off so we
# can inspect tags/attributes without worrying about the namespace prefix.
def strip_ns(tag):
    return tag.split("}")[-1] if "}" in tag else tag

class_counter = Counter()
elements_with_class = []

for elem in root.iter():
    tag = strip_ns(elem.tag)
    cls = elem.attrib.get("class")
    if cls:
        class_counter[cls] += 1
        if len(elements_with_class) < 15:
            elements_with_class.append((tag, cls, dict(elem.attrib)))

print("=== Distinct 'class' attribute values found (with counts) ===")
for cls, count in class_counter.most_common(40):
    print(f"  {count:4d}  {cls}")

print()
print("=== First 15 elements that have a class attribute (full detail) ===")
for tag, cls, attribs in elements_with_class:
    print(f"tag={tag}  class={cls}")
    print(f"  all attribs: {attribs}")

    # Also check for text content or child <text> elements, since room
    # labels are sometimes stored as visible text rather than just a class.
print()
print("=== Any <text> elements and their content (first 20) ===")
count = 0
for elem in root.iter():
    if strip_ns(elem.tag) == "text" and count < 20:
        print(f"  text attribs={elem.attrib}  content={elem.text!r}")
        count += 1
