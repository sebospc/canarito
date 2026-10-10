#!/usr/bin/env python3
"""Fails when a store field is over its limit: App Store Connect rejects it, and in the form it is easy to miss."""
import pathlib, re, sys

LIMITS = {"Name": 30, "Subtitle": 30, "Promotional text": 170, "Keywords": 100, "Description": 4000, "What's New": 4000}
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
sys.exit(1 if failed else 0)
