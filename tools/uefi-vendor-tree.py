#!/usr/bin/env python3
"""Build a Binaries/cupid tree from this phone's own vendor DXE modules.

For each module with a PE32/TE image, write an EDK2 binary INF with the module's real FILE_GUID and
copy the image beside it. The format follows the binary INF used in the local Mu-Silicium tree.

Nothing generated here is committed: these are the phone's proprietary drivers. They are staged
under uefi/files/Binaries/cupid/ so a build that is given the vendor binaries can find them.

Usage:
  python3 tools/uefi-vendor-tree.py \
      --dirs <unpacked-fv-dir> [<unpacked-fv-dir> ...] \
      --inventory docs/uefi-vendor-modules.json \
      --out uefi/files/Binaries/cupid
"""

import argparse
import json
import os
import re
import shutil
import sys
import struct

SAFE = re.compile(r"[^A-Za-z0-9_-]")


def find_pe(raw):
    """Return the offset of an embedded PE32 image with a valid PE signature, or None."""
    at = 0
    while True:
        i = raw.find(b"MZ", at)
        if i < 0:
            return None
        if i + 0x40 <= len(raw):
            pe = struct.unpack_from("<I", raw, i + 0x3C)[0]
            if 0 < pe < len(raw) and raw[i + pe:i + pe + 4] == b"PE\0\0":
                return i
        at = i + 1


def safe_name(name):
    return SAFE.sub("_", name).strip("_")


def render_inf(name, guid, payload):
    entry = "PE32|%s.efi|*" % name if payload == "pe32.efi" else "TE|%s.efi|*" % name
    return ("[Defines]\n"
            "  INF_VERSION                    = 0x0001001B\n"
            "  BASE_NAME                      = %s\n"
            "  FILE_GUID                      = %s\n"
            "  MODULE_TYPE                    = DXE_DRIVER\n"
            "  VERSION_STRING                 = 1.0\n"
            "  ENTRY_POINT                    = EfiEntry\n"
            "\n"
            "[Binaries.AARCH64]\n"
            "  %s\n"
            "\n"
            "[Depex]\n"
            "  TRUE\n" % (name, guid, entry))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dirs", nargs="*", default=[])
    parser.add_argument("--inventory", default="docs/uefi-vendor-modules.json")
    parser.add_argument("--fv", nargs="*", default=[],
                        help="the nested FV files, for recovering PE images the unpacker mislabels")
    parser.add_argument("--out", default="uefi/files/Binaries/cupid")
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args()

    inventory = json.load(open(args.inventory, encoding="utf-8"))
    roots = [r for r in args.dirs if os.path.isdir(r)]
    fvs = [open(p, "rb").read() for p in args.fv if os.path.isfile(p)]
    if not roots and not args.print_only:
        print("uefi-vendor-tree: no unpacked directories given", file=sys.stderr)
        return 1

    by_guid = {}
    for root in roots:
        for entry in os.listdir(root):
            for candidate in ("pe32.efi", "te.efi"):
                path = os.path.join(root, entry, candidate)
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    by_guid[entry.split("-", 1)[-1]] = (candidate, path)

    written = []
    for module in inventory["modules"]:
        name = module.get("name")
        guid = module.get("guid")
        if not guid:
            continue
        sections = module.get("sections", [])
        payload = "pe32.efi" if "pe32.efi" in sections else ("te.efi" if "te.efi" in sections else None)
        if not payload and "depex.bin" not in sections:
            continue
        source = by_guid.get(guid.upper())
        name_used = name
        if source is None and not name:
            # many modules the unpacker labels 'depex.bin' are really a PE32 image after a short
            # prefix. Recover them from the FV itself rather than dropping a driver the phone has.
            for fv in fvs:
                offset = find_pe(fv[module.get("body_offset", 0):
                                    module.get("body_offset", 0) + module.get("size", 0)])
                if offset is not None:
                    tmp = os.path.join(args.out, "_recovered")
                    os.makedirs(tmp, exist_ok=True)
                    path = os.path.join(tmp, guid.upper() + ".efi")
                    with open(path, "wb") as handle:
                        start = module.get("body_offset", 0) + offset
                        handle.write(fv[start:start + module.get("size", 0)])
                    source = ("pe32.efi", path)
                    name_used = "DXE_" + guid.replace("-", "").upper()
                    payload = "pe32.efi"
                    break
        if source is None:
            print("uefi-vendor-tree: %s: no image on disk" % (name or guid))
            continue
        base_name = safe_name(name_used)
        directory = os.path.join(args.out, "QcomPkg", "Drivers", base_name)
        inf = render_inf(base_name, guid.upper(), payload)
        if args.print_only:
            print("# %s (%s)" % (name, guid))
            print(inf)
            continue
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, base_name + ".inf"), "w", newline="\n") as handle:
            handle.write(inf)
        shutil.copyfile(source[1], os.path.join(directory, base_name + ".efi"))
        written.append(base_name)

    if not args.print_only:
        print("uefi-vendor-tree: wrote %d INF/EFI pair(s) under %s" % (len(written), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
