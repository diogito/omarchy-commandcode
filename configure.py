#!/usr/bin/env python3
"""Save a Command Code API key for the Omarchy bar widget.

The key is written to ~/.commandcode/auth.json and is never printed.
Prefer the paste field in the bar panel; this is the terminal equivalent.
"""

from __future__ import annotations

import getpass
import sys

import usage


def main() -> int:
    replace = "--replace" in sys.argv[1:]
    name = usage.env_key_name()
    if name:
        print(
            f"{name} is set in this terminal and overrides ~/.commandcode/auth.json.",
            file=sys.stderr,
        )
        print("Unset it, then paste the key into the bar panel or run this again.", file=sys.stderr)
        return 1
    existing = usage.load_key()
    if existing and not replace:
        try:
            report = usage.build(existing)
        except usage.ApiError as error:
            print(error, file=sys.stderr)
            print("Run again with --replace to save a new key.", file=sys.stderr)
            return 1
        print(f"Already configured. Plan: {report['planName']}.")
        return 0
    if not sys.stdin.isatty():
        print("Open the Command Code icon on the bar and paste the API key there.", file=sys.stderr)
        print("Create one at https://commandcode.ai/studio/", file=sys.stderr)
        return 2
    print("Create a key at https://commandcode.ai/studio/")
    print("It is saved to ~/.commandcode/auth.json and is not shown again.")
    try:
        typed = getpass.getpass("API key: ")
        usage.store_key(typed)
        report = usage.build(typed.strip())
    except usage.ApiError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Saved. Plan: {report['planName']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
