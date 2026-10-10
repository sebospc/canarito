#!/usr/bin/env python3
"""Builds Canarito/Localizable.xcstrings (es source, en translation) and InfoPlist.xcstrings.

Keys come from the compiler: build once, then run `python3 tools/strings.py <derived-data>`.
English lives in tools/translations_en.py. A key without English fails the run: a screen in
Spanish on an English phone is a bug, and the alert text is the one place it must never happen.
"""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from translations_en import EN, INFO_PLIST  # noqa: E402


def extracted_keys(derived_data):
    keys = set()
    for path in pathlib.Path(derived_data).rglob("*.stringsdata"):
        if "arm64" not in path.parts:
            continue
        data = json.loads(path.read_text())
        if "/ios/Canarito/" not in data.get("source", ""):
            continue
        for entries in data.get("tables", {}).get("Localizable", []):
            if entries["key"]:
                keys.add(entries["key"])
    return keys


def catalog(source, translations):
    strings = {}
    for key in sorted(source):
        strings[key] = {"extractionState": "manual", "localizations": {
            "es": {"stringUnit": {"state": "translated", "value": key}},
            "en": {"stringUnit": {"state": "translated", "value": translations[key]}}}}
    return {"sourceLanguage": "es", "strings": strings, "version": "1.0"}


def info_catalog():
    """Permission prompts: the key is the Info.plist property, Spanish is the base value."""
    strings = {key: {"extractionState": "manual", "localizations": {
        "es": {"stringUnit": {"state": "translated", "value": es}},
        "en": {"stringUnit": {"state": "translated", "value": en}}}} for key, (es, en) in INFO_PLIST.items()}
    return {"sourceLanguage": "es", "strings": strings, "version": "1.0"}


def main():
    keys = extracted_keys(sys.argv[1])
    missing = sorted(keys - EN.keys())
    unused = sorted(EN.keys() - keys)
    if missing:
        print("MISSING English for:", *missing, sep="\n  ")
    if unused:
        print("UNUSED translations:", *unused, sep="\n  ")
    if missing:
        sys.exit(1)
    app = HERE.parent / "Canarito"
    (app / "Localizable.xcstrings").write_text(json.dumps(catalog(keys, EN), ensure_ascii=False, indent=2) + "\n")
    (app / "InfoPlist.xcstrings").write_text(json.dumps(info_catalog(), ensure_ascii=False, indent=2) + "\n")
    print(f"{len(keys)} strings")


main()
