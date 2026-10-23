"""Rebuild the Villager Linker jar so it uses a blaze rod instead of a stick.

Villager Linker (MIT, Hafid Talbi) hard-codes Items.STICK and has no config
option for the tool item. This rewrites the relevant constant-pool strings in
the class files and leaves everything else in the jar untouched.

Usage: python -I tools/patch_villager_linker.py <original.jar> <output.jar>
"""
import json
import struct
import sys
import zipfile

CLASS_PATCHES = {
    "com/example/villagerlinker/VillagerLinkerMod.class": {
        "STICK": "BLAZE_ROD",
        "Linking Mode: Sneak-Right-Click a block with Stick.":
            "Linking Mode: Sneak-Right-Click a block with Blaze Rod.",
    },
    "com/example/villagerlinker/client/VillagerLinkerScreen.class": {
        "Sneak-right-click a bed or workstation with a stick":
            "Sneak-right-click a bed or workstation with a blaze rod",
    },
}

# Constant-pool entry sizes (excluding the tag byte) for everything but Utf8.
CP_SIZES = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
            15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}


def patch_class(data, replacements):
    count = struct.unpack_from(">H", data, 8)[0]
    out = bytearray(data[:10])
    pos, index, found = 10, 1, set()
    while index < count:
        tag = data[pos]
        if tag == 1:
            length = struct.unpack_from(">H", data, pos + 1)[0]
            text = data[pos + 3:pos + 3 + length].decode("utf-8")
            if text in replacements:
                found.add(text)
                text = replacements[text]
            raw = text.encode("utf-8")
            out += struct.pack(">BH", 1, len(raw)) + raw
            pos += 3 + length
        else:
            size = CP_SIZES[tag]
            out += data[pos:pos + 1 + size]
            pos += 1 + size
        index += 2 if tag in (5, 6) else 1
    missing = set(replacements) - found
    if missing:
        sys.exit(f"Not found (mod changed?): {sorted(missing)}")
    return bytes(out + data[pos:])


def patch_mod_json(data):
    meta = json.loads(data)
    meta["version"] += "+blazerod"
    meta["description"] = ("Link and unlink villagers from beds and workstations"
                           " with a blaze rod. (Numenor build: stick swapped"
                           " for blaze rod.)")
    return json.dumps(meta, indent=2).encode("utf-8")


def main(src, dst):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        seen = set()
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename in CLASS_PATCHES:
                data = patch_class(data, CLASS_PATCHES[info.filename])
                seen.add(info.filename)
            elif info.filename == "fabric.mod.json":
                data = patch_mod_json(data)
            zout.writestr(info, data, compress_type=info.compress_type)
    if seen != set(CLASS_PATCHES):
        sys.exit(f"Missing classes: {sorted(set(CLASS_PATCHES) - seen)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
