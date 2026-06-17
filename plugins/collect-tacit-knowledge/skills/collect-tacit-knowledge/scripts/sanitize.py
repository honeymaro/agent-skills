#!/usr/bin/env python3
"""Rescan a report for leaks; optionally mask them. stdlib only."""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from ctk.sanitize import find_leaks, mask_report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("report", help="path to report markdown")
    ap.add_argument("--known-names", help="path to newline-separated names file")
    ap.add_argument("--mask", action="store_true", help="write masked report back")
    args = ap.parse_args(argv)

    names = []
    if args.known_names and os.path.exists(args.known_names):
        with open(args.known_names, encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]

    with open(args.report, encoding="utf-8") as f:
        text = f.read()
    findings = find_leaks(text, known_names=names)

    if args.mask:
        masked = mask_report(text, known_names=names)
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(masked)
        print(json.dumps({"masked": True, "found": len(findings)}))
        return 0

    print(json.dumps({"found": len(findings), "findings": findings}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
