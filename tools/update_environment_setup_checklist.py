"""Safely update section 1.1 checkboxes in the StockLam test plan.

This script is intentionally conservative:
- It only knows the rows from section "1.1 Environment Setup".
- It performs a dry run by default.
- It refuses to write unless the caller explicitly passes --apply, --test-passed,
  and --confirmed.

Example dry run:
    python tools/update_environment_setup_checklist.py --item verify-logs

Example apply after the related test passed and the user asked for it:
    python tools/update_environment_setup_checklist.py --item verify-logs --test-passed --confirmed --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_PLAN_PATH = Path("docs/comprehensive-application-test-plan.md")
SECTION_TITLE = "### 1.1 Environment Setup"
PASS_MARK = "[x]"
OPEN_MARK = "[ ]"

CHECKLIST_ITEMS = {
    "install-dependencies": "Install dependencies inside the project virtual environment.",
    "start-application": "Start the application from `venv` using `python main.py`.",
    "verify-env-settings": "Verify `.env` database settings.",
    "prevent-production-data": "Verify the application does not use production data during testing.",
    "verify-logs": "Verify logs are written and readable.",
    "screen-resolution": "Verify screen resolution support: small laptop, standard desktop, wide screen.",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely mark selected Environment Setup checklist rows as passed. "
            "Dry-run mode is used unless --apply is provided."
        )
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Markdown test plan path. Default: {DEFAULT_PLAN_PATH}",
    )
    parser.add_argument(
        "--item",
        action="append",
        choices=sorted(CHECKLIST_ITEMS),
        help="Checklist item key to mark. Repeat for multiple rows.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List supported item keys and exit.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to the plan. Without this flag the script only previews changes.",
    )
    parser.add_argument(
        "--test-passed",
        action="store_true",
        help="Required with --apply. Confirms the related automated/manual verification passed.",
    )
    parser.add_argument(
        "--confirmed",
        action="store_true",
        help="Required with --apply. Confirms the user explicitly asked to mark the selected rows.",
    )
    return parser.parse_args(argv)


def _section_bounds(lines: list[str]) -> tuple[int, int]:
    start = None
    for index, line in enumerate(lines):
        if line.strip() == SECTION_TITLE:
            start = index
            break
    if start is None:
        raise ValueError(f"Could not find section: {SECTION_TITLE}")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("### ") or stripped.startswith("## "):
            end = index
            break
    return start, end


def _replace_checkbox(line: str) -> str:
    if f"| {PASS_MARK} |" in line:
        return line
    if f"| {OPEN_MARK} |" not in line:
        raise ValueError(f"Target row is not open and cannot be safely updated: {line.strip()}")
    return line.replace(f"| {OPEN_MARK} |", f"| {PASS_MARK} |", 1)


def update_environment_setup_rows(markdown: str, item_keys: list[str]) -> tuple[str, list[str]]:
    if not item_keys:
        raise ValueError("At least one --item is required.")

    unknown = sorted(set(item_keys) - set(CHECKLIST_ITEMS))
    if unknown:
        raise ValueError(f"Unsupported item key(s): {', '.join(unknown)}")

    lines = markdown.splitlines(keepends=True)
    start, end = _section_bounds(lines)
    updated = []

    for item_key in item_keys:
        target_text = CHECKLIST_ITEMS[item_key]
        matches = [
            index
            for index in range(start, end)
            if lines[index].lstrip().startswith("|") and f"| {target_text} |" in lines[index]
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one row for item '{item_key}' in section 1.1, found {len(matches)}."
            )
        row_index = matches[0]
        new_line = _replace_checkbox(lines[row_index])
        if new_line != lines[row_index]:
            lines[row_index] = new_line
            updated.append(item_key)

    return "".join(lines), updated


def _print_supported_items() -> None:
    print("Supported Environment Setup checklist items:")
    for key, text in CHECKLIST_ITEMS.items():
        print(f"  {key}: {text}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    if args.list:
        _print_supported_items()
        return 0

    if not args.item:
        print("No items selected. Use --list to see valid item keys.", file=sys.stderr)
        return 2

    if args.apply and (not args.test_passed or not args.confirmed):
        print(
            "Refusing to write. --apply requires both --test-passed and --confirmed.",
            file=sys.stderr,
        )
        return 2

    if not args.plan.exists():
        print(f"Plan file not found: {args.plan}", file=sys.stderr)
        return 2

    original = args.plan.read_text(encoding="utf-8")
    updated_text, updated_keys = update_environment_setup_rows(original, args.item)

    if not updated_keys:
        print("Selected rows were already marked as passed. No changes needed.")
        return 0

    if not args.apply:
        print("Dry run only. The following rows would be marked [x]:")
        for key in updated_keys:
            print(f"  {key}: {CHECKLIST_ITEMS[key]}")
        print("Re-run with --apply --test-passed --confirmed to write changes.")
        return 0

    args.plan.write_text(updated_text, encoding="utf-8", newline="")
    print("Updated Environment Setup checklist rows:")
    for key in updated_keys:
        print(f"  {key}: {CHECKLIST_ITEMS[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
