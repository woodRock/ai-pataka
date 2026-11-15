# AI Pātaka Lecture Series

Poster and email templates for the **AI Pātaka Lecture Series**, hosted by the
**Hiringa te Mahara** pod of **Abundant Intelligences**.

![Example poster](docs/example-poster.png)

## Quick start

```bash
pip install -r requirements.txt          # jinja2, pyyaml, pillow, tzdata
# LaTeX (for the PDF): apt install texlive-xetex texlive-latex-extra   |  macOS: MacTeX

python3 scripts/new_talk.py 2026-12-02-surname     # creates talks/2026-12-02-surname/talk.yaml
$EDITOR talks/2026-12-02-surname/talk.yaml          # speaker, title, abstract, date, Zoom
python3 scripts/render.py talks/2026-12-02-surname  # -> talks/2026-12-02-surname/build/
```

Outputs in `build/`:

- `poster.pdf` / `poster.png`: A4 poster with logo, bilingual date, QR code to the Zoom link
- `email.txt` / `email.html`: announcement email (te reo Māori greeting and closing, time-zone table, add-to-calendar link)
- `email.json`: subject, bodies and attachments, ready for the Pātaka mail service to turn into a draft
- `event.ics`: calendar invite

No LaTeX locally? Run with `--no-pdf` and compile `build/poster.tex` on Overleaf with the **XeLaTeX** compiler (upload the logo from `assets/` too).

## Customising

- Series text, time zones, default moderator, colours, greeting and closing: `config/series.yaml`
- Email signature: `config/signature.txt`
- Poster design: `templates/poster.tex.j2`
- Email wording: `templates/email.txt.j2` and `templates/email.html.j2`

See [`CLAUDE.md`](CLAUDE.md) (also `AGENTS.md`) for the field reference, the `email.json`
contract and the workflow AI agents follow. Claude Code users can also run the
`draft-lecture-announcement` skill.
