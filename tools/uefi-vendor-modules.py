#!/usr/bin/env python3
"""Record the vendor DXE modules found in this phone's own UEFI, and compare them with the platform.

The generated file holds names and GUIDs only -- no firmware bytes. It is the evidence for mapping
the platform's inherited driver list (from the negroni board) onto the drivers this phone actually
provides. A match by name is a hint, not a proof; a GUID match would be proof, and the platform's
binaries are not available to compare against.

Usage:
  python3 tools/uefi-vendor-modules.py \
      --dirs <unpacked-fv-dir> [<unpacked-fv-dir> ...] \
      --out docs/uefi-vendor-modules.json
  python3 tools/uefi-vendor-modules.py --check docs/uefi-vendor-modules.json
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DXE_INC = os.path.join(REPO, "uefi", "files", "Platforms", "Xiaomi", "cupidPkg",
                       "Include", "DXE.inc")
REFERENCE = re.compile(r"Binaries/([A-Za-z0-9_.-]+)/([A-Za-z0-9_./-]+\.(?:inf|efi))")


def read_unpacked(directories):
    modules = []
    for root in directories:
        if not os.path.isdir(root):
            print("uefi-vendor-modules: no directory at %s" % root, file=sys.stderr)
            continue
        for entry in sorted(os.listdir(root)):
            directory = os.path.join(root, entry)
            index = os.path.join(directory, "index.txt")
            if not os.path.isfile(index):
                continue
            fields = {}
            for line in open(index, encoding="utf-8"):
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
            name_file = os.path.join(directory, "name.txt")
            name = None
            if os.path.isfile(name_file):
                lines = open(name_file, encoding="utf-8", errors="replace").read().splitlines()
                if lines and lines[0].strip():
                    name = lines[0].strip()
            modules.append({
                "guid": fields.get("guid"),
                "type": fields.get("type"),
                "size": int(fields.get("size", 0)),
                "name": name,
                "directory": entry,
                "sections": [s for s in fields.get("sections", "").split(",") if s.strip()],
            })
    return sorted(modules, key=lambda m: (m["name"] or "", m["guid"] or ""))


def platform_references():
    text = open(DXE_INC, encoding="utf-8").read()
    return sorted({path for _board, path in REFERENCE.findall(text) if path.endswith(".inf")})


def normalize(name):
    name = name.lower()
    name = re.sub(r"(dxe|la|app|driver)$", "", name)
    return re.sub(r"[^a-z0-9]", "", name)


def build(directories):
    modules = read_unpacked(directories)
    refs = platform_references()
    wanted = {os.path.basename(path)[:-4] for path in refs}
    by_name = {}
    for module in modules:
        if module["name"]:
            by_name.setdefault(normalize(module["name"]), []).append(module["name"])
    matched, missing = {}, []
    for want in sorted(wanted):
        names = by_name.get(normalize(want))
        if names:
            matched[want] = names
        else:
            missing.append(want)
    return {
        "device": "cupid",
        "source": "the vendor DXE modules in this phone's own uefi_a.img, read with "
                  "tools/uefi-fv-unpack.py",
        "note": "Names and GUIDs only, no firmware bytes. A name match is a hint, not a GUID proof: "
                "the platform's binaries come from another board (negroni) and are not available "
                "here to compare.",
        "module_count": len(modules),
        "named_module_count": sum(1 for m in modules if m["name"]),
        "modules": modules,
        "platform_references": refs,
        "name_matches": matched,
        "not_found_by_name": missing,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dirs", nargs="*", default=[],
                        help="directories of unpacked FFS files (each with index.txt / name.txt)")
    parser.add_argument("--out", default="docs/uefi-vendor-modules.json")
    parser.add_argument("--check")
    args = parser.parse_args()

    data = build(args.dirs)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if args.dirs:
            text = json.dumps(build(args.dirs), indent=2, ensure_ascii=False) + "\n"
            current = open(args.check, encoding="utf-8").read()
            if current != text:
                print("uefi-vendor-modules: %s does not match the generator" % args.check)
                return 1
        else:
            # the unpacked firmware is not committed, so CI can only validate the shape
            current = json.load(open(args.check, encoding="utf-8"))
            required = ("module_count", "named_module_count", "modules",
                        "platform_references", "name_matches", "not_found_by_name")
            absent = [key for key in required if key not in current]
            if absent:
                print("uefi-vendor-modules: missing keys: %s" % ", ".join(absent))
                return 1
        print("uefi-vendor-modules: %s is consistent" % args.check)
        return 0
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("uefi-vendor-modules: wrote %s (%d modules, %d named, %d of %d platform names matched)"
          % (args.out, data["module_count"], data["named_module_count"],
             len(data["name_matches"]), len(data["platform_references"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
