# Video Comment Skill Generator

Browser automation exports batches of **public, visible** Bilibili or Xiaohongshu comments to JSONL. This tool checkpoints, deduplicates, proves collection completion, creates an extractive evidence pack, then generates one Codex Skill per source item. With --merge-similar, it combines only analyses whose extracted topic terms overlap beyond the configured threshold.

The completeness gate is deliberate: a blocked or unfinished export cannot be summarized or turned into a Skill without an explicit manual override for the summary step, and it can never enter generate-skills.

## Commands

    python video_comment_skill_generator.py init-run --out runs/BV1 --platform bilibili --content-id BV1 --url https://www.bilibili.com/video/BV1 --title "Video title" --topic "Topic"
    python video_comment_skill_generator.py append-batch --run runs/BV1 --input batch-001.jsonl
    python video_comment_skill_generator.py finish --run runs/BV1 --reason no_more_comments --evidence "Page 12 shows no-more-comments text"
    python video_comment_skill_generator.py summarize --run runs/BV1
    python video_comment_skill_generator.py generate-skills --analysis-dir runs --out generated-skills --merge-similar

Each input JSONL line needs at least text; optional fields are id, published_at, parent_id, like_count, and reply_count.

## Xiaohongshu support

Use the normal visible page in a user-authorized Chrome profile. The adapter must prefer DOM text, then use OCR only for text already visible in a screenshot. OCR records require source_method: "ocr", an evidence_ref pointing to the frame, and an ocr_confidence score. Do not automate CAPTCHAs, risk controls, login challenges, proxy rotation, or anti-detection behavior.

The Chrome DevTools MCP adapter calls append-batch after each visible pagination batch and calls finish only after observing an explicit end-of-comments state. Any challenge, rate-limit page, or inaccessible reply thread must mark the run blocked; this prevents a misleading complete Skill.
