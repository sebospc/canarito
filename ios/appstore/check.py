#!/usr/bin/env python3
"""Fails when a store field is over its limit: App Store Connect rejects it, and in the form it is easy to miss."""
import pathlib, re, sys

LIMITS = {"Name": 30, "Subtitle": 30, "Promotional text": 170, "Keywords": 100, "Description": 4000, "What's New": 4000}
# Guideline 2.3.10: no other mobile platform in the app or its store page.
PLATFORMS = re.compile(r"android|google|play store|samsung|huawei", re.I)
BANNED = ["delve", "leverage", "robust", "seamless", "streamline", "empower", "comprehensive", "cutting-edge", "—"]
failed = False
for path in sorted(pathlib.Path(__file__).parent.glob("*-*.md")):
    text = path.read_text()
    for title, body in re.findall(r"^## (.+?) \[\d+\]\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        body = body.strip()
        limit = LIMITS[title]
        if len(body) > limit:
            print(f"{path.name}: {title} is {len(body)}, limit {limit}"); failed = True
    for word in BANNED:
        if word in text.lower():
            print(f"{path.name}: slop word {word!r}"); failed = True
app_texts = [*pathlib.Path(__file__).parent.glob("*-*.md"), *(pathlib.Path(__file__).parent.parent / "Canarito").rglob("*.swift"),
             *(pathlib.Path(__file__).parent.parent / "Canarito").rglob("*.xcstrings")]
for path in app_texts:
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if PLATFORMS.search(line) and not line.lstrip().startswith("//"):
            print(f"{path.name}:{number}: names another platform (guideline 2.3.10)"); failed = True
sys.exit(1 if failed else 0)
