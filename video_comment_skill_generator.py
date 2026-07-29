#!/usr/bin/env python3
"""Local pipeline for complete-comment exports and evidence-backed Codex skills.

The browser/MCP layer writes comment batches to this tool. This program never
logs in, fetches a site, stores credentials, or attempts to evade platform
controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_END_REASONS = {"no_more_comments", "platform_total_reached"}
BLOCKED_REASONS = {"rate_limited", "captcha", "login_required", "risk_control", "unknown"}
PLATFORMS = {"bilibili", "xiaohongshu"}
METHODS = {"dom", "ocr"}
STOPWORDS = set("这个那个我们你们他们以及但是因为所以视频评论感觉真的就是一个可以没有什么比较还是".split())


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_paths(run: Path) -> tuple[Path, Path]:
    return run / "manifest.json", run / "comments.jsonl"


def normalize_comment(raw: dict[str, Any]) -> dict[str, Any]:
    text = str(raw.get("text", "")).strip()
    if not text:
        raise ValueError("comment.text is required")
    method = str(raw.get("source_method", "dom"))
    if method not in METHODS:
        raise ValueError(f"comment.source_method must be one of {sorted(METHODS)}")
    confidence = raw.get("ocr_confidence")
    if method == "ocr":
        if not raw.get("evidence_ref"):
            raise ValueError("OCR comments require evidence_ref (the captured frame reference)")
        if confidence is None or not 0 <= float(confidence) <= 1:
            raise ValueError("OCR comments require ocr_confidence from 0 to 1")
    return {
        "id": str(raw.get("id", "")).strip() or None,
        "text": text,
        "published_at": raw.get("published_at"),
        "parent_id": raw.get("parent_id"),
        "like_count": int(raw.get("like_count", 0) or 0),
        "reply_count": int(raw.get("reply_count", 0) or 0),
        "source_method": method,
        "evidence_ref": raw.get("evidence_ref"),
        "ocr_confidence": float(confidence) if confidence is not None else None,
    }


def comment_key(comment: dict[str, Any]) -> str:
    if comment["id"]:
        return "id:" + comment["id"]
    source = "\u241f".join(str(comment.get(k) or "") for k in ("text", "published_at", "parent_id"))
    return "hash:" + hashlib.sha256(source.encode("utf-8")).hexdigest()


def load_comments(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid stored JSONL at line {n}: {exc}") from exc
    return records


def init_run(args: argparse.Namespace) -> None:
    run = Path(args.out).resolve()
    run.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1,
        "content": {
            "platform": args.platform,
            "id": args.content_id,
            "url": args.url,
            "title": args.title,
            "topic": args.topic or "",
            "kind": args.content_kind,
        },
        "created_at": now(),
        "updated_at": now(),
        "collection": {
            "status": "collecting",
            "comment_count": 0,
            "batches": 0,
            "duplicates": 0,
            "end_reason": None,
            "end_evidence": None,
            "blocked_reason": None,
        },
    }
    write_json(run / "manifest.json", manifest)
    (run / "comments.jsonl").write_text("", encoding="utf-8")
    print(run)


def append_batch(args: argparse.Namespace) -> None:
    run = Path(args.run).resolve()
    manifest_path, comments_path = run_paths(run)
    manifest = read_json(manifest_path)
    if manifest["collection"]["status"] != "collecting":
        raise ValueError("cannot append after collection has stopped")
    existing = load_comments(comments_path)
    seen = {comment_key(c) for c in existing}
    incoming: list[dict[str, Any]] = []
    for n, line in enumerate(Path(args.input).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            comment = normalize_comment(json.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid input at line {n}: {exc}") from exc
        key = comment_key(comment)
        if key in seen:
            manifest["collection"]["duplicates"] += 1
        else:
            seen.add(key)
            incoming.append(comment)
    with comments_path.open("a", encoding="utf-8") as handle:
        for comment in incoming:
            handle.write(json.dumps(comment, ensure_ascii=False) + "\n")
    manifest["collection"]["comment_count"] += len(incoming)
    manifest["collection"]["batches"] += 1
    manifest["updated_at"] = now()
    write_json(manifest_path, manifest)
    print(json.dumps({"added": len(incoming), "duplicates": manifest["collection"]["duplicates"]}, ensure_ascii=False))


def import_mediacrawler_jsonl(args: argparse.Namespace) -> None:
    """Normalize MediaCrawler JSONL comments and append them to an active run."""
    source = Path(args.input)
    converted = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid MediaCrawler JSONL at line {number}: {exc}") from exc
        text = raw.get("content") or raw.get("comment_content") or raw.get("text") or raw.get("desc")
        if not text:
            continue
        converted.append(
            {
                "id": raw.get("comment_id") or raw.get("id"),
                "text": text,
                "published_at": raw.get("create_time") or raw.get("publish_time"),
                "parent_id": raw.get("parent_comment_id") or raw.get("parent_id"),
                "like_count": raw.get("like_count") or raw.get("like_num") or 0,
                "reply_count": raw.get("sub_comment_count") or raw.get("reply_count") or 0,
                "source_method": "dom",
                "evidence_ref": f"mediacrawler:{source.name}:{number}",
            }
        )
    temporary = Path(args.run).resolve() / ".mediacrawler-import.jsonl"
    try:
        temporary.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in converted) + "\n", encoding="utf-8")
        append_batch(argparse.Namespace(run=args.run, input=str(temporary)))
    finally:
        temporary.unlink(missing_ok=True)


def run_mediacrawler(args: argparse.Namespace) -> None:
    """Run the licensed MediaCrawler backend with its own user-managed config."""
    if not args.ack_noncommercial:
        raise ValueError("pass --ack-noncommercial to confirm the MediaCrawler non-commercial learning license")
    root = Path(args.backend_root).resolve()
    entry = root / "main.py"
    if not entry.is_file():
        raise FileNotFoundError(f"MediaCrawler backend is missing: {entry}")
    command = [
        args.uv_command,
        "run",
        "main.py",
        "--platform",
        args.platform,
        "--lt",
        args.login_type,
        "--type",
        args.crawl_type,
    ]
    completed = subprocess.run(command, cwd=root, text=True, timeout=args.timeout, check=False)
    if completed.returncode:
        raise ValueError(f"MediaCrawler exited with status {completed.returncode}")


def finish(args: argparse.Namespace) -> None:
    run = Path(args.run).resolve()
    manifest_path, _ = run_paths(run)
    manifest = read_json(manifest_path)
    collection = manifest["collection"]
    if args.blocked:
        if args.blocked not in BLOCKED_REASONS:
            raise ValueError(f"blocked reason must be one of {sorted(BLOCKED_REASONS)}")
        collection.update(status="blocked", blocked_reason=args.blocked, end_reason=None, end_evidence=args.evidence or None)
    else:
        if args.reason not in ALLOWED_END_REASONS:
            raise ValueError(f"completion reason must be one of {sorted(ALLOWED_END_REASONS)}")
        if not args.evidence:
            raise ValueError("completion requires visible UI evidence, e.g. 'no-more-comments text on page 12'")
        collection.update(status="complete", end_reason=args.reason, end_evidence=args.evidence, blocked_reason=None)
    manifest["updated_at"] = now()
    write_json(manifest_path, manifest)


def tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text.lower())
    return [word for word in words if word not in STOPWORDS]


def summarize_run(args: argparse.Namespace) -> None:
    run = Path(args.run).resolve()
    manifest_path, comments_path = run_paths(run)
    manifest = read_json(manifest_path)
    collection = manifest["collection"]
    if collection["status"] != "complete" and not args.allow_incomplete:
        raise ValueError("refusing to summarize: comment export is not complete")
    comments = load_comments(comments_path)
    ranked = sorted(comments, key=lambda c: (c.get("like_count", 0), c.get("reply_count", 0)), reverse=True)
    frequencies = Counter(token for c in comments for token in tokens(c["text"]))
    observations = []
    for comment in ranked[: args.max_observations]:
        observations.append({"text": comment["text"], "likes": comment["like_count"], "replies": comment["reply_count"]})
    analysis = {
        "schema_version": 1,
        "content": manifest["content"],
        "collection": collection,
        "analysis_status": "ready" if collection["status"] == "complete" else "incomplete_override",
        "comment_count": len(comments),
        "dominant_terms": [{"term": term, "count": count} for term, count in frequencies.most_common(args.max_terms)],
        "high_engagement_observations": observations,
        "method": "extractive evidence pack; interpret observations with a model or reviewer before publishing claims",
        "generated_at": now(),
    }
    output = Path(args.out or run / "analysis.json")
    write_json(output, analysis)
    print(output)


def slug(value: str, fallback: str) -> str:
    ascii_value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (ascii_value[:48] or fallback).strip("-")


def overlap(left: dict[str, Any], right: dict[str, Any]) -> float:
    a = {x["term"] for x in left.get("dominant_terms", [])}
    b = {x["term"] for x in right.get("dominant_terms", [])}
    return len(a & b) / len(a | b) if a | b else 0.0


def skill_body(group: list[dict[str, Any]], title: str) -> str:
    sources = "\n".join(f"- {item['content']['title']} — {item['content']['url']}" for item in group)
    terms = Counter(term["term"] for item in group for term in item.get("dominant_terms", []))
    observations = []
    for item in group:
        for observation in item.get("high_engagement_observations", [])[:3]:
            observations.append(f"- {observation['text']} (likes: {observation['likes']})")
    observation_text = "\n".join(observations) or "No observations available."
    return f"""---
name: {slug(title, 'video-comment-insights')}
description: Reusable, evidence-backed guidance derived from complete public-comment exports for the topic {title}. Use when the user asks to apply, compare, or extend the audience insights represented by these source items. Do not treat the observations as universal claims without checking the cited sources and collection status.
---

# {title}

## Source items

{sources}

## Recurrent audience signals

{', '.join(term for term, _ in terms.most_common(12)) or 'No recurring terms extracted.'}

## High-engagement evidence

{observation_text}

## Use with care

These are extractive signals from complete public-comment exports, not demographic facts or causal conclusions. Preserve each source video’s context, and keep materially different observations distinct when applying this skill.
"""


def generate_skills(args: argparse.Namespace) -> None:
    analyses = [read_json(path) for path in sorted(Path(args.analysis_dir).glob("**/analysis.json"))]
    if not analyses:
        raise ValueError("no analysis.json files found")
    invalid = [a["content"].get("title", "unknown") for a in analyses if a.get("analysis_status") != "ready"]
    if invalid:
        raise ValueError("refusing skill generation from incomplete exports: " + ", ".join(invalid))
    groups: list[list[dict[str, Any]]] = []
    for analysis in analyses:
        target = next((g for g in groups if args.merge_similar and overlap(g[0], analysis) >= args.merge_threshold), None)
        if target is None:
            groups.append([analysis])
        else:
            target.append(analysis)
    output_root = Path(args.out).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    for index, group in enumerate(groups, 1):
        title = group[0]["content"].get("topic") or group[0]["content"]["title"]
        if len(group) > 1:
            title += " (merged audience insights)"
        folder = output_root / slug(title, f"video-insights-{index}")
        folder.mkdir(exist_ok=True)
        (folder / "SKILL.md").write_text(skill_body(group, title), encoding="utf-8")
    print(json.dumps({"skills": len(groups), "output": str(output_root)}, ensure_ascii=False))


def status(args: argparse.Namespace) -> None:
    manifest = read_json(Path(args.run) / "manifest.json")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("init-run"); p.add_argument("--out", required=True); p.add_argument("--platform", choices=sorted(PLATFORMS), required=True); p.add_argument("--content-id", required=True); p.add_argument("--content-kind", default="video"); p.add_argument("--url", required=True); p.add_argument("--title", required=True); p.add_argument("--topic"); p.set_defaults(func=init_run)
    p = commands.add_parser("append-batch"); p.add_argument("--run", required=True); p.add_argument("--input", required=True); p.set_defaults(func=append_batch)
    p = commands.add_parser("import-mediacrawler-jsonl"); p.add_argument("--run", required=True); p.add_argument("--input", required=True); p.set_defaults(func=import_mediacrawler_jsonl)
    p = commands.add_parser("run-mediacrawler"); p.add_argument("--platform", choices=["xhs", "bili"], required=True); p.add_argument("--login-type", default="qrcode"); p.add_argument("--crawl-type", default="detail"); p.add_argument("--backend-root", default="vendor/MediaCrawler"); p.add_argument("--uv-command", default="uv"); p.add_argument("--timeout", type=int, default=3600); p.add_argument("--ack-noncommercial", action="store_true"); p.set_defaults(func=run_mediacrawler)
    p = commands.add_parser("finish"); p.add_argument("--run", required=True); p.add_argument("--reason"); p.add_argument("--blocked"); p.add_argument("--evidence"); p.set_defaults(func=finish)
    p = commands.add_parser("summarize"); p.add_argument("--run", required=True); p.add_argument("--out"); p.add_argument("--max-terms", type=int, default=15); p.add_argument("--max-observations", type=int, default=12); p.add_argument("--allow-incomplete", action="store_true"); p.set_defaults(func=summarize_run)
    p = commands.add_parser("generate-skills"); p.add_argument("--analysis-dir", required=True); p.add_argument("--out", required=True); p.add_argument("--merge-similar", action="store_true"); p.add_argument("--merge-threshold", type=float, default=0.55); p.set_defaults(func=generate_skills)
    p = commands.add_parser("status"); p.add_argument("--run", required=True); p.set_defaults(func=status)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
