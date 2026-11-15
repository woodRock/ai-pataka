#!/usr/bin/env python3
"""Render an AI Pātaka talk into a poster and an announcement email.

Usage:
    python3 scripts/render.py talks/<slug>            # render + compile PDF
    python3 scripts/render.py talks/<slug> --no-pdf   # skip LaTeX compile
    python3 scripts/render.py talks/<slug> --json     # also print email.json to stdout

Inputs:  config/series.yaml, config/signature.txt, talks/<slug>/talk.yaml
Outputs (talks/<slug>/build/):
    poster.tex, poster.pdf     A4 poster (XeLaTeX)
    email.txt, email.html      announcement email bodies
    poster.png                 poster image for embedding in the email (needs pdftoppm)
Also talks/<slug>/poster.png   hosted copy linked from the email, if poster_base_url is set
    email.json                 {subject, body_text, body_html, attachments, poster_image, meta}
                               -> hand this to the Pātaka mail service to create a draft
    event.ics                  calendar invite
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import jinja2
import yaml

ROOT = Path(__file__).resolve().parent.parent

# --- te reo Māori calendar names -------------------------------------------
MAORI_DAYS = ["Rāhina", "Rātū", "Rāapa", "Rāpare", "Rāmere", "Rāhoroi", "Rātapu"]
MAORI_MONTHS = ["Kohitātea", "Huitanguru", "Poutūterangi", "Paengawhāwhā",
                "Haratua", "Pipiri", "Hōngongoi", "Here-turi-kōkā", "Mahuru",
                "Whiringa-ā-nuku", "Whiringa-ā-rangi", "Hakihea"]

REQUIRED = [
    ("speaker", "name"), ("speaker", "bio"),
    ("talk", "title"), ("talk", "abstract"),
    ("when", "date"), ("when", "start"), ("when", "end"),
    ("zoom", "url"), ("zoom", "meeting_id"), ("zoom", "passcode"),
]


# --- helpers ---------------------------------------------------------------
def ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_time(t: dt.datetime, *, ampm_compact: bool = False) -> str:
    """9:00 AM, or 9am / 2:30pm when compact (poster style)."""
    h = t.hour % 12 or 12
    ap = "am" if t.hour < 12 else "pm"
    if ampm_compact:
        return f"{h}{ap}" if t.minute == 0 else f"{h}:{t.minute:02d}{ap}"
    return f"{h}:{t.minute:02d} {ap.upper()}"


def fmt_date(d: dt.datetime) -> str:
    return f"{d:%A}, {d:%B} {ordinal(d.day)}"


def fmt_date_mi(d: dt.datetime) -> str:
    return f"{MAORI_DAYS[d.weekday()]}, {d.day} {MAORI_MONTHS[d.month - 1]}"


LATEX_SPECIALS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex(s) -> str:
    """Escape a plain string for LaTeX. Keeps unicode (XeLaTeX handles macrons)."""
    s = "" if s is None else str(s)
    s = "".join(LATEX_SPECIALS.get(c, c) for c in s)
    return s.replace("–", "--").replace("—", "---")


def need(d: dict, path: tuple[str, ...], where: str):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or not cur.get(k):
            sys.exit(f"error: {where} is missing required field '{'.'.join(path)}'")
        cur = cur[k]


def resolve_photo(p: str | None, build: Path, name: str) -> str:
    """Square-cropped copy of a photo in build/, or '' (poster draws initials).

    Photos of any aspect ratio are centre-cropped to a square so they are not
    stretched inside the blob frame.
    """
    if not p:
        return ""
    path = (ROOT / p).resolve()
    if not path.exists():
        print(f"warning: photo not found: {p} (using placeholder)", file=sys.stderr)
        return ""
    try:
        from PIL import Image, ImageOps
    except ImportError:  # no Pillow: use as-is (square photos look best)
        return path.as_posix()
    build.mkdir(exist_ok=True)
    out = build / f"{name}.jpg"
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        side = min(im.size)
        left, top = (im.width - side) // 2, max(0, (im.height - side) // 3)  # bias toward faces
        im.crop((left, top, left + side, top + side)).resize((800, 800)).save(out, quality=90)
    return out.as_posix()


# --- context ---------------------------------------------------------------
def build_context(talk_dir: Path) -> dict:
    series_cfg = yaml.safe_load((ROOT / "config/series.yaml").read_text())
    talk = yaml.safe_load((talk_dir / "talk.yaml").read_text())
    for path in REQUIRED:
        need(talk, path, str(talk_dir / "talk.yaml"))

    host_tz = ZoneInfo(series_cfg["host_timezone"])
    date = dt.date.fromisoformat(str(talk["when"]["date"]))
    start = dt.datetime.combine(date, dt.time.fromisoformat(str(talk["when"]["start"])), host_tz)
    end = dt.datetime.combine(date, dt.time.fromisoformat(str(talk["when"]["end"])), host_tz)
    if end <= start:
        sys.exit("error: when.end must be after when.start")

    # Time zone table, grouped by local date (like the example email).
    groups: list[dict] = []
    for z in series_cfg["timezones"]:
        tz = ZoneInfo(z["tz"])
        s, e = start.astimezone(tz), end.astimezone(tz)
        row = {"label": z["label"], "abbr": s.tzname(),
               "range": f"{fmt_time(s)} - {fmt_time(e)}"}
        key = fmt_date(s)
        if not groups or groups[-1]["date"] != key:
            # merge with an earlier group of the same date if present
            match = next((g for g in groups if g["date"] == key), None)
            if match:
                match["rows"].append(row)
                continue
            groups.append({"date": key, "rows": []})
        groups[-1]["rows"].append(row)

    speaker = talk["speaker"]
    speaker.setdefault("honorific", "")
    speaker.setdefault("first_name", speaker["name"].split()[0])
    speaker["full"] = f"{speaker['honorific']} {speaker['name']}".strip()
    speaker["photo_abs"] = resolve_photo(speaker.get("photo"), talk_dir / "build", "speaker-photo")

    moderator = {**series_cfg["moderator"], **(talk.get("moderator") or {})}
    moderator["photo_abs"] = resolve_photo(moderator.get("photo"), talk_dir / "build", "moderator-photo")

    t = talk["talk"]
    # Starting font size for the bio; LaTeX (tcolorbox fitting) shrinks it further if needed.
    n = len(speaker["bio"])
    speaker["bio_pt"] = 13 if n <= 650 else 12 if n <= 900 else 11
    if n > 1400:
        print(f"warning: speaker bio is {n} characters; it will be set very small on the poster. "
              "Consider trimming it to ~900.", file=sys.stderr)
    full_title = t["title"] + (f": {t['subtitle']}" if t.get("subtitle") else "")

    # Google Calendar "add to calendar" link
    utc = ZoneInfo("UTC")
    gfmt = "%Y%m%dT%H%M%SZ"
    gcal = "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode({
        "action": "TEMPLATE",
        "text": f"{series_cfg['series']['name']} Lecture: {full_title}",
        "dates": f"{start.astimezone(utc):{gfmt}}/{end.astimezone(utc):{gfmt}}",
        "details": f"{speaker['full']} — {full_title}\n\nZoom: {talk['zoom']['url']}\n"
                   f"Meeting ID: {talk['zoom']['meeting_id']}\nPasscode: {talk['zoom']['passcode']}",
        "location": talk["zoom"]["url"],
    })

    sig_path = ROOT / series_cfg["email"]["signature_file"]
    signature = sig_path.read_text().strip() if sig_path.exists() else ""

    return {
        "cfg": series_cfg,
        "series": series_cfg["series"],
        "colours": series_cfg["colours"],
        "logo_abs": (ROOT / series_cfg["logo"]).resolve().as_posix(),
        "email_cfg": series_cfg["email"],
        "signature": signature,
        "speaker": speaker,
        "moderator": moderator,
        "talk": t,
        "full_title": full_title,
        "zoom": talk["zoom"],
        "start": start, "end": end,
        "host_abbr": start.tzname(),
        "date_en": fmt_date(start),
        "date_mi": fmt_date_mi(start),
        "time_range_compact": f"{fmt_time(start, ampm_compact=True)}–{fmt_time(end, ampm_compact=True)}",
        "time_start": fmt_time(start),
        "tz_groups": groups,
        "gcal_url": gcal,
        "slug": talk_dir.name,
        "poster_base_url": (series_cfg.get("poster_base_url") or "").strip(),
        "poster_url": "",
    }


# --- renderers -------------------------------------------------------------
def latex_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(ROOT / "templates"),
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string="<#", comment_end_string="#>",
        line_comment_prefix="%#",
        trim_blocks=True, autoescape=False, undefined=jinja2.StrictUndefined,
    )
    env.filters["tex"] = tex
    return env


def text_env(autoescape: bool) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(ROOT / "templates"),
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
        autoescape=autoescape, undefined=jinja2.StrictUndefined,
    )
    return env


def ics(ctx: dict) -> str:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")

    utc = ZoneInfo("UTC")
    f = "%Y%m%dT%H%M%SZ"
    now = dt.datetime.now(utc)
    # SEQUENCE must grow each time a sent invite changes, or calendar apps
    # treat the update as stale and keep the old time. Minutes since 2026
    # grows on every render, so a re-rendered invite always supersedes the
    # last one without anyone having to bump a number by hand.
    sequence = int((now - dt.datetime(2026, 1, 1, tzinfo=utc)).total_seconds() // 60)
    desc = (f"{ctx['speaker']['full']} — {ctx['full_title']}\n\n{ctx['talk']['abstract']}\n\n"
            f"Zoom: {ctx['zoom']['url']}\nMeeting ID: {ctx['zoom']['meeting_id']}\n"
            f"Passcode: {ctx['zoom']['passcode']}")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AI Pataka//Lecture Series//EN", "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{ctx['slug']}@ai-pataka",
        f"DTSTAMP:{now:{f}}",
        f"LAST-MODIFIED:{now:{f}}",
        f"SEQUENCE:{sequence}",
        f"DTSTART:{ctx['start'].astimezone(utc):{f}}",
        f"DTEND:{ctx['end'].astimezone(utc):{f}}",
        f"SUMMARY:{esc(ctx['series']['name'] + ' Lecture: ' + ctx['full_title'])}",
        f"DESCRIPTION:{esc(desc)}",
        f"LOCATION:{esc(ctx['zoom']['url'])}",
        f"URL:{ctx['zoom']['url']}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def html_to_text(s: str) -> str:
    s = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 (\1)", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|h\d|li|div|table|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def check_hosted(h: dict) -> None:
    """Warn if the hosted poster is missing or differs from this render."""
    try:
        with urllib.request.urlopen(h["url"], timeout=10) as r:
            same = hashlib.sha256(r.read()).hexdigest() == h["sha"]
        problem = None if same else "is out of date"
    except Exception as e:  # 404 before the first push, or offline
        problem = f"could not be fetched ({e})"
    if problem:
        print(f"warning: the hosted poster {problem}: {h['url']}\n"
              f"  Commit and push {h['path']} before sending, or the email shows a broken image.\n"
              f"  (raw.githubusercontent.com can take ~5 minutes to show a new push.)", file=sys.stderr)
    else:
        print(f"hosted poster is up to date: {h['url']}", file=sys.stderr)


def compile_pdf(build: Path) -> bool:
    engine = shutil.which("latexmk")
    if engine:
        cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "poster.tex"]
    elif shutil.which("xelatex"):
        cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "poster.tex"]
    else:
        print("note: xelatex not found; skipped PDF (poster.tex is ready to compile, e.g. on Overleaf "
              "with the XeLaTeX compiler)", file=sys.stderr)
        return False
    r = subprocess.run(cmd, cwd=build, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], file=sys.stderr)
        sys.exit("error: LaTeX compile failed (see log above / build/poster.log)")
    for ext in ("aux", "fls", "fdb_latexmk", "xdv", "out"):
        (build / f"poster.{ext}").unlink(missing_ok=True)
    # PNG version for embedding inline in the email body. Remove the old one
    # first so a stale poster is never used if pdftoppm is missing or fails.
    (build / "poster.png").unlink(missing_ok=True)
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", "110", "-singlefile", "poster.pdf", "poster"],
                       cwd=build, check=False)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("talk_dir", type=Path)
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--json", action="store_true", help="print email.json to stdout")
    args = ap.parse_args()

    talk_dir = args.talk_dir.resolve()
    if not (talk_dir / "talk.yaml").exists():
        sys.exit(f"error: {talk_dir}/talk.yaml not found")
    ctx = build_context(talk_dir)
    build = talk_dir / "build"
    build.mkdir(exist_ok=True)

    (build / "poster.tex").write_text(latex_env().get_template("poster.tex.j2").render(**ctx))
    (build / "event.ics").write_text(ics(ctx))

    has_pdf = False if args.no_pdf else compile_pdf(build)
    # Only use poster.png if it was just rebuilt from this run's PDF.
    png = build / "poster.png" if has_pdf and (build / "poster.png").exists() else None

    # Gmail's web composer drops inline (cid:) images when a draft is sent, so
    # when poster_base_url is set the email links to a hosted copy instead:
    # talks/<slug>/poster.png, which must be committed and pushed. ?v= changes
    # with the image so mail clients and GitHub never show an old cached poster.
    hosted = None
    if png and ctx["poster_base_url"]:
        tracked = talk_dir / "poster.png"
        shutil.copyfile(png, tracked)
        rel = tracked.relative_to(ROOT).as_posix()
        sha = hashlib.sha256(png.read_bytes()).hexdigest()
        url = ctx["poster_base_url"].rstrip("/") + "/" + urllib.parse.quote(rel)
        hosted = {"path": rel, "url": url, "sha": sha}
        ctx["poster_url"] = f"{url}?v={sha[:12]}"

    body_html = text_env(True).get_template("email.html.j2").render(**ctx)
    body_text = text_env(False).get_template("email.txt.j2").render(**ctx)
    subject = text_env(False).get_template("email_subject.txt.j2").render(**ctx).strip()
    (build / "email.html").write_text(body_html)
    (build / "email.txt").write_text(body_text)
    # With a hosted poster the body links to it, so no PNG is attached. When
    # inlined instead, Gmail's web composer drops the inline image on send,
    # so a PNG is attached as a fallback. It must be a separately named copy:
    # given the same file for both, the mail service stores one inline part
    # and no visible attachment.
    png_copy = build / f"{ctx['slug']}-poster.png"
    png_copy.unlink(missing_ok=True)
    if png and not hosted:
        shutil.copyfile(png, png_copy)
    else:
        png_copy = None
    attachments = [str(f.relative_to(ROOT)) for f in
                   ([build / "poster.pdf"] if has_pdf else []) + ([png_copy] if png_copy else [])
                   + [build / "event.ics"]]
    payload = {
        "subject": subject,
        "to": [],
        "cc": [],
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        # Image to put where <!-- POSTER --> appears in body_html. Null when the
        # body links to the hosted poster instead, or no poster was rendered.
        "poster_image": str(png.relative_to(ROOT)) if png and not hosted else None,
        "meta": {"series": ctx["series"]["name"], "slug": ctx["slug"],
                 "start_utc": ctx["start"].astimezone(ZoneInfo("UTC")).isoformat(),
                 "calendar_url": ctx["gcal_url"]},
    }
    (build / "email.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    if hosted:
        check_hosted(hosted)
    print(f"rendered {build.relative_to(ROOT)}/ : "
          + ", ".join(sorted(p.name for p in build.iterdir() if not p.name.endswith(".log"))),
          file=sys.stderr)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
