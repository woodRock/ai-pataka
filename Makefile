# make new SLUG=2026-12-02-surname   -> scaffold talks/<slug>/talk.yaml
# make talk T=talks/2026-12-02-surname -> render poster + email into talks/<slug>/build/
# make example                        -> render the example talk

PY ?= python3

new:
	$(PY) scripts/new_talk.py $(SLUG)

talk:
	$(PY) scripts/render.py $(T)

example:
	$(PY) scripts/render.py talks/_example

.PHONY: new talk example
