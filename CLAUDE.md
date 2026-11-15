# AI Pātaka Lecture Series — templates

This repo turns one YAML file per talk into:
1. an A4 **poster** (XeLaTeX → `poster.pdf` + `poster.png`), and
2. an **announcement email** (`email.txt`, `email.html`, `email.json`) plus a calendar invite (`event.ics`).

The series is the **AI Pātaka Lecture Series**, hosted by the **Hiringa te Mahara** pod of
**Abundant Intelligences**. Emails open and close in te reo Māori; the body is in English.
The organiser/sender is **Jesse Wood** (signature in `config/signature.txt`).

## Layout

| Path | What it is | Who edits it |
|---|---|---|
| `config/series.yaml` | Series name, description, host time zone, email time-zone list, default moderator, colours, greeting/closing | Rarely |
| `config/signature.txt` | Plain-text email signature (first line = name, `http…` lines become links) | Rarely |
| `talks/_example/talk.yaml` | Fully commented example talk — copy this | Never (reference) |
| `talks/<slug>/talk.yaml` | **The only file you edit per talk** | Per talk |
| `talks/<slug>/build/` | Generated output (git-ignored) | Never by hand |
| `templates/poster.tex.j2` | Poster design (Jinja2 with LaTeX-safe delimiters) | Design changes |
| `templates/email.{txt,html}.j2`, `email_subject.txt.j2` | Email wording | Wording changes |
| `scripts/render.py` | Renderer: YAML → build/ | Code changes |
| `scripts/new_talk.py` | Scaffolds `talks/<slug>/talk.yaml` | — |
| `assets/` | Logo (white wordmark, needs dark background) and shared images | — |

## Workflow (for AI agents)

When asked to draft an announcement for a new talk:

1. `python3 scripts/new_talk.py <YYYY-MM-DD>-<speaker-surname>` (lowercase, hyphens).
2. Fill `talks/<slug>/talk.yaml` from what the user gave you (flyer text, speaker bio, Zoom invite…).
   - **Times are in the host time zone (`Pacific/Auckland`)**, 24-hour `HH:MM`. Convert if the user gave another zone.
   - Do not invent facts (bio, iwi, Zoom IDs). If something is missing, leave the example
     placeholder value and tell the user what is still needed.
   - Bio: third person, ≤ ~900 characters fits the poster comfortably (longer is auto-shrunk).
   - Abstract: 3–6 sentences, written as "In this session, we will…".
   - Photos: put them in `talks/<slug>/` and set `photo:` to the repo-relative path. Any aspect
     ratio is fine (auto square-cropped). Blank → initials placeholder.
3. `python3 scripts/render.py talks/<slug>` (add `--no-pdf` if XeLaTeX is unavailable).
4. Look at `build/poster.png` to check the layout, and read `build/email.txt` back to the user.
5. Hand `build/email.json` to the Pātaka mail service to create the draft (see below).
   Never send email directly — only create drafts for the user to review.

To change wording for **every** email, edit `templates/email.*.j2` (keep `.txt` and `.html` in sync).
To change a **single** email, render it, then edit the draft in the mail client — don't hand-edit `build/`.

## `talk.yaml` fields

```yaml
speaker:
  honorific: Dr            # optional (Dr, Prof, Matua, Whaea, …)
  name: Full Name          # required
  first_name: Full         # optional, defaults to first word of name
  affiliation: Iwi / hapū  # optional, italic on poster
  photo: talks/<slug>/speaker.jpg   # optional
  bio: >-                  # required
talk:
  title: ...               # required
  subtitle: ...            # optional; poster puts it on line 2, email joins with ": "
  abstract: >-             # required — "Session Description" in email
  series_context: ...      # optional sentence after the series description
when:
  date: YYYY-MM-DD         # required, host time zone
  start: "HH:MM"           # required, 24h
  end: "HH:MM"             # required, 24h
zoom:
  url: https://...         # required (also encoded in the poster QR code)
  meeting_id: "123 4567 8901"
  passcode: "123456"
moderator: {name, role, affiliation, photo}   # optional override of config default
```

## `email.json` (contract with the Pātaka mail service)

```json
{
  "subject": "AI Pātaka Lecture Series | Dr Name: \"Title\" | Wednesday, December 2nd, 2:00 PM NZDT",
  "to": [], "cc": [],
  "body_text": "plain-text body",
  "body_html": "HTML body; contains <!-- POSTER --> where the poster image should be inlined",
  "attachments": ["talks/<slug>/build/poster.pdf", "talks/<slug>/build/event.ics"],
  "poster_image": "talks/<slug>/build/poster.png",
  "meta": {"series": "...", "slug": "...", "start_utc": "ISO-8601", "calendar_url": "Google Calendar add link"}
}
```
Paths are relative to the repo root. `to`/`cc` are left empty for the user to fill.

## Te reo Māori used

Keep macrons. Poster/email phrases: *Kia ora koutou katoa* (greeting), *Ngā mihi nui* (closing),
*kaiwhakahaere* (moderator), *Te Wā* (time), *kōrero ā-ipurangi* (virtual talk),
*hono mai ki Zoom* (join Zoom), *Nau mai, haere mai* (welcome). Dates on the poster are
rendered bilingually by `render.py` (e.g. *Rāapa, 2 Hakihea* / Wednesday, December 2nd).
If you add new te reo text, flag it to the user for checking rather than guessing.

## Conventions

- Python 3.9+, deps in `requirements.txt` (`jinja2`, `pyyaml`, `tzdata`, optional `pillow`). LaTeX: XeLaTeX
  with `tikz`, `qrcode`, `tcolorbox` (TeX Live `texlive-xetex texlive-latex-extra`). Works on Overleaf (XeLaTeX compiler) if you upload `build/poster.tex` + the logo.
- Poster template syntax: `\VAR{expr}` prints, `\BLOCK{if …}…\BLOCK{endif}` for control flow,
  lines starting `%#` are template comments. Always pass strings through `|tex` to escape LaTeX.
- Time-zone list is labelled by city because some Canadian provinces now use permanent
  daylight time; abbreviations come from the tz database at render time.
- `event.ics` keeps the same `UID` per talk and sets `SEQUENCE` to minutes since 2026 at render
  time, so a re-rendered invite (e.g. after a time change) replaces the old event in calendars.
  To reschedule a talk that has been announced, edit `talk.yaml`, re-render and send the new invite.
- Verify changes by rendering `talks/_example` and viewing `build/poster.png`.
