# Chrome DevTools MCP adapter contract

Use a user-authorized Chrome DevTools connection and visit an explicitly approved Bilibili video or Xiaohongshu note.

1. Read currently visible comment cards from the DOM. Emit one JSONL batch with source_method set to dom.
2. If a visible comment is not represented in accessible DOM text, capture the rendered frame and run an approved local OCR engine. OCR records include source_method set to ocr, evidence_ref, and ocr_confidence.
3. Scroll or use the visible “more comments” control at a conservative pace. After every successful page, execute append-batch.
4. Finish only when the UI explicitly reports no more comments or a platform total has been reached; include that UI evidence in finish.
5. Stop on CAPTCHA, login challenge, risk-control page, or rate limit and mark the run blocked.

OCR is a parser fallback, not an anti-bot technique. It does not authorize faster collection, hidden API access, account sharing, proxy rotation, or bypassing a platform control.
