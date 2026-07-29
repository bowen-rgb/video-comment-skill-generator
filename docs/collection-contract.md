# Collection contract

This project accepts public-page exports from a user-authorized, visible browser session. It does not store browser profiles, cookies, tokens, passwords, local storage, raw API responses, or private identifiers.

## Safe collection boundary

- Record target URLs, purpose, fields, and retention location before collection.
- Use normal visible UI pagination or “load more” controls, one page at a time.
- Stop when a CAPTCHA, login challenge, risk-control page, rate limit, or inaccessible reply thread appears. Mark the run as blocked; do not summarize it as complete.
- An organization-approved proxy may be normal egress infrastructure, but this tool does not rotate proxies or identities, spoof fingerprints, solve CAPTCHAs, or bypass platform controls.
- Preserve reply nesting and order when visible. Deduplicate by visible ID when available, otherwise by normalized text, timestamp, and parent ID.

## Portable JSONL format

Every line must have source, kind, url, captured_at, and data.

~~~json
{"source":"bilibili","kind":"video","url":"https://www.bilibili.com/video/BV...","captured_at":"2026-07-29T08:00:00Z","data":{"title":"..."}}
{"source":"bilibili","kind":"comment","url":"https://www.bilibili.com/video/BV...","captured_at":"2026-07-29T08:00:00Z","data":{"text":"...","parent_ref":null}}
~~~

Allowed combinations are bilibili/video, bilibili/comment, xiaohongshu/note, and xiaohongshu/comment. URLs must be absolute HTTP(S) URLs and timestamps must be ISO-8601.

Validate an export locally:

~~~powershell
python video_comment_skill_generator.py validate-export --input collection.jsonl
~~~

The command only checks local file structure and rejects secret/session-like keys. It never fetches a platform.
