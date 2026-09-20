#!/usr/bin/env python3
"""Canonical offline validation for this Portable Core; Python standard library.

Supported frontmatter is deliberately limited to two unquoted, single-line
plain string fields: name and description. This is not a general YAML parser.
Unsupported YAML fails with an actionable error, rather than being guessed.
"""
import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


def frontmatter_errors(text):
    errors = []
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.S)
    if not match:
        return ["SKILL.md: expected opening and closing frontmatter fences"]
    fields = {}
    for line in match.group(1).splitlines():
        item = re.fullmatch(r"(name|description): ([^\n]+)", line)
        if not item:
            errors.append("Frontmatter supports only name/description as single-line plain strings")
            continue
        key, value = item.groups()
        if key in fields:
            errors.append("Duplicate frontmatter key: " + key)
        fields[key] = value
        # Reject YAML collections, quotes, tags, anchors, aliases, block scalars,
        # comments and implicit scalar types instead of partially parsing them.
        if (value != value.strip() or not value or not value[0].isalpha() or value.endswith(":")
                or ": " in value or " #" in value or "\t" in value
                or value.casefold() in {"null", "~", "true", "false", "yes", "no", "on", "off"}
                or re.fullmatch(r"[+\-]?[\d.]+", value)):
            errors.append(key + ": unsupported YAML; use a nonempty unquoted plain string")
    if set(fields) != {"name", "description"}:
        errors.append("Exactly name and description are required")
    name, description = fields.get("name", ""), fields.get("description", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append("name: use lowercase hyphenated words, 1–64 characters")
    if not 1 <= len(description) <= 1024 or "<" in description or ">" in description:
        errors.append("description: use 1–1024 characters, without angle brackets")
    if re.search(r"\[TODO:[^\n]*\]", text):
        errors.append("Unfinished TODO scaffold")
    return errors


def validate(root):
    root = Path(root).resolve()
    entry = root / "SKILL.md"
    if not entry.is_file():
        return ["SKILL.md missing"], 0
    errors = frontmatter_errors(entry.read_text(encoding="utf-8"))
    links_checked = 0
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Same inline-link coverage as the accepted regression check. Anchor
        # existence and remote URL health are intentionally outside this check.
        for target in re.findall(r"\]\(([^)]+)\)", text):
            target = target.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = Path(unquote(parsed.path))
            if destination.is_absolute():
                continue  # External evidence references are not portable assets.
            links_checked += 1
            if not (path.parent / destination).exists():
                errors.append(f"{path.relative_to(root)}: broken local link: {target}")
    return errors, links_checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        errors, count = validate(args.root)
    except (OSError, UnicodeError, ValueError) as exc:
        print("VALIDATION FAIL: " + str(exc), file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print("FAIL: " + error, file=sys.stderr)
        return 1
    print(f"VALIDATION PASS — frontmatter, scaffold and {count} local file links; standard library only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
