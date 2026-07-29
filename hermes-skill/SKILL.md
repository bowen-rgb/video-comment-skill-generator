---
name: video-comment-skill-generator
description: "Export complete public Bilibili or Xiaohongshu comment batches, create evidence-backed summaries, and generate topic-linked Codex skills."
version: 1.0.0
author: Local
license: MIT
platforms: [windows]
prerequisites:
  commands: [python]
metadata:
  hermes:
    tags: [bilibili, xiaohongshu, comments, ocr, scrapling, skill-generation]
    homepage: https://github.com/bowen-rgb/video-comment-skill-generator
---

# Video Comment Skill Generator

Use this Skill for the pipeline:

1. Collect only public, visibly rendered comments from an approved Bilibili video or Xiaohongshu note.
2. Persist every visible pagination batch to the generator.
3. Mark the run complete only after visible end-of-comments evidence.
4. Create an extractive evidence pack and then a topic-linked Skill.

## Safety and completeness

- Use Chrome DevTools MCP for pages requiring the user's existing logged-in Chrome session.
- Use the optional Scrapling adapter only for public pages that do not require that session.
- Prefer DOM text. OCR is allowed only for text already displayed in a captured frame and must include an evidence reference and confidence.
- Do not solve CAPTCHAs, bypass risk controls, rotate proxies, spoof fingerprints, or automate login challenges.
- If comments cannot be fully reached, mark the export blocked. Do not generate a Skill from an incomplete export.

## Local commands

Run from C:\Users\ROG\Documents\projects\video-comment-skill-generator.

    python video_comment_skill_generator.py init-run --out runs/BV1 --platform bilibili --content-id BV1 --url VIDEO_URL --title "Video title" --topic "Topic"
    python video_comment_skill_generator.py append-batch --run runs/BV1 --input batch-001.jsonl
    python video_comment_skill_generator.py finish --run runs/BV1 --reason no_more_comments --evidence "Visible end-of-comments text"
    python video_comment_skill_generator.py summarize --run runs/BV1
    python video_comment_skill_generator.py generate-skills --analysis-dir runs --out generated-skills --merge-similar

Use platform xiaohongshu and content-kind note for Xiaohongshu notes.
