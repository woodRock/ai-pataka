---
name: draft-lecture-announcement
description: Draft the poster and announcement email for a new AI Pātaka lecture (Hiringa te Mahara / Abundant Intelligences). Use when the user gives details of an upcoming talk (speaker, title, date, Zoom link, bio, flyer) and wants the poster, email, or a mail draft.
---

Follow the "Workflow (for AI agents)" section of `CLAUDE.md` at the repo root:

1. Scaffold: `python3 scripts/new_talk.py <YYYY-MM-DD>-<surname>`.
2. Fill `talks/<slug>/talk.yaml` from the user's details only — no invented facts; list anything missing.
   Times are Pacific/Auckland, 24h.
3. Render: `python3 scripts/render.py talks/<slug>`.
4. Read `talks/<slug>/build/poster.png` to check layout (title wrapping, bio fit, photo crop).
5. Show the user the subject line and `email.txt`, and list remaining placeholders.
6. If the user wants a draft in their mailbox, pass `talks/<slug>/build/email.json` to the
   Pātaka mail service (drafts only — never send).
