"""Hermes command bridge for the Video Comment Skill Generator."""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
PROJECT = Path(r"C:\Users\ROG\Documents\projects\video-comment-skill-generator")
PROGRAM = PROJECT / "video_comment_skill_generator.py"
ALLOWED_ACTIONS = {"init-run", "validate-export", "append-batch", "import-mediacrawler-jsonl", "run-mediacrawler", "finish", "summarize", "generate-skills", "status"}


def register(ctx: Any) -> None:
    """Expose a real local command and add workflow context for relevant chats."""
    try:
        ctx.register_command(
            "video-comment",
            video_comment_command,
            description="Run comment export, completeness checks, summaries, and Skill generation.",
            args_hint="<run-mediacrawler|validate-export|import-mediacrawler-jsonl|init-run|append-batch|finish|summarize|generate-skills|status> [arguments]",
        )
    except TypeError:
        ctx.register_command("video-comment", video_comment_command)
    ctx.register_hook("pre_llm_call", pre_llm_call)


def pre_llm_call(user_message: Any = "", **_: Any) -> dict[str, str] | None:
    text = str(user_message or "").casefold()
    cues = ("bilibili", "小红书", "评论", "评论区", "skill", "总结")
    if not any(cue in text for cue in cues):
        return None
    return {
        "context": (
            "[Video Comment Tool] Use the licensed MediaCrawler backend for Bilibili/Xiaohongshu "
            "comment collection when its own configuration is prepared. For its JSONL comment output, "
            "invoke /video-comment import-mediacrawler-jsonl. For direct browser collection, use the "
            "logged-in Chrome DevTools session only for visible page navigation. After each visible pagination batch, write JSONL "
            "and invoke /video-comment append-batch. Invoke finish only with visible end-of-comments "
            "evidence. On CAPTCHA, rate limit, risk control, or inaccessible replies, invoke finish "
            "with --blocked and do not summarize or generate a Skill. Use /video-comment summarize "
            "then /video-comment generate-skills only after completion."
        )
    }


def video_comment_command(raw_args: str) -> str:
    """Run the generator without a shell, preserving stdout/stderr for Hermes."""
    if not PROGRAM.is_file():
        return f"Generator is missing: {PROGRAM}"
    try:
        parts = shlex.split(raw_args, posix=False)
    except ValueError as exc:
        return f"Invalid arguments: {exc}"
    if not parts or parts[0] in {"help", "--help", "-h"}:
        return _help()
    if parts[0] not in ALLOWED_ACTIONS:
        return _help()
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), *parts],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    output = (completed.stdout + completed.stderr).strip()
    return output or f"Command exited with status {completed.returncode}"


def _help() -> str:
    return (
        "Usage: /video-comment <action> [arguments]\n"
        "Actions: run-mediacrawler, validate-export, import-mediacrawler-jsonl, init-run, append-batch, finish, summarize, generate-skills, status\n"
        "Example: /video-comment status --run runs/BV1"
    )
