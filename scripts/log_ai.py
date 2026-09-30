#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

LOG_FILE_PATH = Path("AI_USAGE_LOG.md")
TABLE_HEADER = (
    "# AI Usage Log\n\n"
    "This document records all significant AI interactions throughout the project lifecycle "
    "in compliance with Section E3 of the deployment specification.\n\n"
    "| Date | Tool Used | Purpose | Prompt Summary | How Output Was Used | Validation Step |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | \n"
)

def ensure_log_file_exists() -> None:
    if not LOG_FILE_PATH.exists():
        LOG_FILE_PATH.write_text(TABLE_HEADER, encoding="utf-8")
    else:
        content = LOG_FILE_PATH.read_text(encoding="utf-8")
        if "| Date |" not in content:
            LOG_FILE_PATH.write_text(TABLE_HEADER + content, encoding="utf-8")

def escape_markdown(text: str) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ").strip()
    return cleaned.replace("|", "\\|")

def get_staged_summary() -> str:
    try:
        diff_stat = subprocess.check_output(
            ["git", "diff", "--cached", "--stat"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        if diff_stat:
            return diff_stat.split("\n")[-1].strip()
    except Exception:
        pass
    return "Repository modifications staged"

def append_entry(date_str: str, tool: str, purpose: str, prompt: str, usage: str, validation: str) -> None:
    ensure_log_file_exists()
    row = (
        f"| {escape_markdown(date_str)} "
        f"| {escape_markdown(tool)} "
        f"| {escape_markdown(purpose)} "
        f"| {escape_markdown(prompt)} "
        f"| {escape_markdown(usage)} "
        f"| {escape_markdown(validation)} |\n"
    )
    with LOG_FILE_PATH.open("a", encoding="utf-8") as f:
        f.write(row)
    print(f"[AI-LOG] Successfully appended entry to {LOG_FILE_PATH}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Append an AI interaction entry to AI_USAGE_LOG.md.")
    parser.add_argument("--tool", type=str, default="Gemini 2.5 Pro")
    parser.add_argument("--purpose", type=str, default="Codebase Implementation")
    parser.add_argument("--prompt", type=str, default="Enterprise configuration setup")
    parser.add_argument("--used", type=str, default="")
    parser.add_argument("--validation", type=str, default="Local syntax review & container verification")
    parser.add_argument("--json-input", action="store_true")
    args = parser.parse_args()

    date_now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.json_input:
        try:
            payload = json.load(sys.stdin)
            append_entry(
                date_str=payload.get("date", date_now),
                tool=payload.get("tool", "Gemini 2.5 Pro"),
                purpose=payload.get("purpose", "Implementation"),
                prompt=payload.get("prompt", "Prompt summary not supplied"),
                usage=payload.get("used", "Direct integration into module"),
                validation=payload.get("validation", "Static syntax check and domain review")
            )
            return
        except Exception as err:
            print(f"[AI-LOG ERROR] Failed to parse JSON stdin: {err}", file=sys.stderr)
            sys.exit(1)

    usage = args.used if args.used else f"Committed staged files ({get_staged_summary()})"
    append_entry(
        date_str=date_now,
        tool=args.tool,
        purpose=args.purpose,
        prompt=args.prompt,
        usage=usage,
        validation=args.validation
    )

if __name__ == "__main__":
    main()
