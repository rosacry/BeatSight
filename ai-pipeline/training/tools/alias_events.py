#!/usr/bin/env python3
import json, sys, pathlib

ALIAS = {
    "china2": "china",
    "tom_floor": "tom_low",
    "tom_low2": "tom_low"
}

def normalize_components(comps):
    out = []
    for c in comps or []:
        original = c.get("label")
        mapped = ALIAS.get(original, original)
        if mapped != original:
            # keep a hint that this came from a second piece
            if original == "china2":
                c["instance"] = 2
            if original in ("tom_floor", "tom_low2"):
                c["instance"] = 2
            c["label"] = mapped
        out.append(c)
    return out

def main(src, dst):
    with open(src, "r") as f_in, open(dst, "w") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            obj = json.loads(line)
            # If negative_example, enforce empty components
            if obj.get("negative_example"):
                obj["components"] = []
            else:
                obj["components"] = normalize_components(obj.get("components", []))
            f_out.write(json.dumps(obj, separators=(",", ":")) + "\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: alias_events.py <in.jsonl> <out.jsonl>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
