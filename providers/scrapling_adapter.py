"""Optional public-page exporter powered by Scrapling's DynamicSession.

Install with pip install "scrapling[fetchers]" then run scrapling install.
This adapter deliberately does not expose Scrapling's stealth, CAPTCHA-solving,
proxy, user-agent spoofing, or fingerprint-manipulation options.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any


@dataclass(frozen=True)
class CommentSelectors:
    comment: str
    more_comments: str
    blocked_markers: tuple[str, ...] = ("验证码", "访问频繁", "安全验证", "risk control")


def export_visible_comments(
    url: str,
    selectors: CommentSelectors,
    *,
    max_pages: int = 100,
    pause_seconds: float = 1.5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read visible DOM comment text and return a batch plus completion evidence.

    This is for public pages only. For a logged-in user session, use the
    Chrome DevTools MCP adapter so the user retains control of their profile.
    """
    try:
        from scrapling.fetchers import DynamicSession
    except ImportError as exc:
        raise RuntimeError('Install optional dependency: pip install "scrapling[fetchers]"') from exc

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    outcome: dict[str, Any] = {"status": "collecting", "end_evidence": None, "blocked_reason": None}

    def read(page: Any) -> None:
        nonlocal outcome
        for _ in range(max_pages):
            body_text = page.locator("body").inner_text()
            if any(marker.lower() in body_text.lower() for marker in selectors.blocked_markers):
                outcome = {"status": "blocked", "end_evidence": None, "blocked_reason": "risk_control"}
                return
            texts = page.locator(selectors.comment).all_inner_texts()
            added = 0
            for text in texts:
                text = text.strip()
                if text and text not in seen:
                    seen.add(text)
                    records.append({"text": text, "source_method": "dom"})
                    added += 1
            more = page.locator(selectors.more_comments)
            if more.count() == 0:
                outcome = {
                    "status": "complete",
                    "end_evidence": "more-comments control absent after visible DOM pagination",
                    "blocked_reason": None,
                }
                return
            more.first.click()
            sleep(pause_seconds)
            if added == 0:
                outcome = {"status": "blocked", "end_evidence": None, "blocked_reason": "unknown"}
                return
        outcome = {"status": "blocked", "end_evidence": None, "blocked_reason": "unknown"}

    # DynamicSession is browser automation without the StealthySession feature set.
    with DynamicSession(headless=True, network_idle=True, disable_resources=False) as session:
        session.fetch(url, page_action=read)
    return records, outcome
