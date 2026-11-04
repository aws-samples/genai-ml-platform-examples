# Workshop walkthrough deck

`genai-ml-standardization-walkthrough.pptx` — a 27-slide, one-hour tour of the
architecture, the concepts, and the labs, intended to be presented **before**
participants open a notebook.

## Running the session

The deck is paced for 60 minutes including Q&A. Every slide carries speaker
notes with a running clock (`0:14 (3 min)` …), what to say, and what to skip if
you are behind. Present from the notes, not the slides.

Rough split: 18 minutes of framing and architecture, 5–6 minutes per lifecycle
stage, 6 minutes of logistics at the end. The notes flag three places to adapt
to the room — which Lab 1 baseline your event uses, whether the audience is
traditional-ML or GenAI leaning, and which prerequisites apply to your accounts.

If you have less than an hour, the stage dividers are natural cut points: drop
the two architecture slides (5–6) and the optional Lab 3D table (17), and the
narrative still holds.

## Rebuilding it

```bash
pip install python-pptx pillow
brew install librsvg            # rsvg-convert, to render the SVG diagrams

python3 scripts/generate-slides.py
```

The deck is generated, not hand-edited. Stage artwork is cut from a 2x render
of `images/architecture.svg` at build time, so the slides cannot drift from the
diagrams — change the SVG, re-run the script. Content lives in `build()` at the
bottom of `scripts/generate-slides.py`, one call per slide, speaker notes
included.

Hand edits to the `.pptx` will be lost on the next build. For one-off tweaks
before a delivery, save a copy under a different name.

## Fonts and branding

Type is **Amazon Ember**, the AWS brand typeface. If the presenting machine
does not have it, PowerPoint substitutes a default sans and some lines set
wider than designed — install Amazon Ember, or change `FONT` in the generator
to `"Arial"` for predictable fallback.

Colour is AWS Squid Ink and Smile Orange for chrome, plus the five per-stage
colours used verbatim in the architecture diagrams, so the deck and the
diagrams agree.

This is a content deck using AWS brand colour and type conventions — it is not
the official AWS corporate template. For a customer-facing delivery, move the
content into whatever template your team is required to present from.
