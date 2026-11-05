"""Generate the one-hour workshop walkthrough deck.

    python3 scripts/generate-slides.py [out.pptx]

Default output: slides/genai-ml-standardization-walkthrough.pptx

What this builds
----------------
A 34-slide, 16:9 deck that walks an audience through the architecture, the
concepts, and the labs of all five AI lifecycle stages *before* they open a
notebook. Every slide carries speaker notes with a running clock, and the
narrative is kept in step with two sources of truth:

  * images/architecture.svg + images/architecture-icons.svg  (this repo)
  * the Workshop Studio content pages in the companion repo
    model-governance-at-scale-with-sagemaker-ai/content/

Stage artwork is cut from a 2x render of architecture.svg at build time, so the
deck cannot drift from the diagram: change the SVG, re-run this script. The
crops are written to a temp directory and embedded in the .pptx, which leaves
no build artifacts behind.

Requirements
------------
  pip install python-pptx pillow        # PPTX writer + image cropping
  brew install librsvg                  # rsvg-convert, for the SVG renders

Typography
----------
Body and headings are set in **Amazon Ember**, the AWS brand typeface. If the
presenting machine does not have it installed PowerPoint substitutes a default
sans and some lines will set wider than designed; install Amazon Ember, or
change FONT below to "Arial" for a predictable fallback.

Colour
------
AWS Squid Ink (#232F3E) and Smile Orange (#FF9900) for chrome, Cloudscape
greys for body text, and the five per-stage colours reused verbatim from the
architecture diagrams so the deck and the diagrams agree visually.

This is a content deck using AWS brand colour and type conventions. It is not
the official AWS corporate template -- for a customer-facing delivery, paste
these slides into whatever template your team is required to present from.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMAGES = os.path.join(ROOT, "images")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "slides", "genai-ml-standardization-walkthrough.pptx")

FONT = "Amazon Ember"

# --- palette ---------------------------------------------------------------
SQUID = RGBColor(0x23, 0x2F, 0x3E)      # AWS Squid Ink
ORANGE = RGBColor(0xFF, 0x99, 0x00)     # AWS Smile Orange
INK = RGBColor(0x16, 0x19, 0x1F)
GRAY = RGBColor(0x5F, 0x6B, 0x7A)
LINE = RGBColor(0xD5, 0xDB, 0xDB)
LIGHT = RGBColor(0xF7, 0xF8, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

STAGE = [
    RGBColor(0x4B, 0x55, 0x63),   # 1 infra setup
    RGBColor(0x09, 0x72, 0xD3),   # 2 data prep
    RGBColor(0x7D, 0x3A, 0xC1),   # 3 model build
    RGBColor(0x0F, 0x8B, 0x5F),   # 4 model deploy
    RGBColor(0xC2, 0x57, 0x1A),   # 5 monitoring
]
TINT = [
    RGBColor(0xF2, 0xF4, 0xF6), RGBColor(0xEA, 0xF2, 0xFB),
    RGBColor(0xF3, 0xEB, 0xFB), RGBColor(0xE8, 0xF6, 0xEF),
    RGBColor(0xFF, 0xF4, 0xEC),
]

# --- geometry (13.333 x 7.5 in) --------------------------------------------
SW, SH = Inches(13.333), Inches(7.5)
M = Inches(0.62)                  # side margin
BODY_W = SW - 2 * M
TITLE_Y = Inches(0.40)
RULE_Y = Inches(1.17)
BODY_Y = Inches(1.42)
FOOT_Y = Inches(6.96)

FOOTER = "GenAI / ML Standardization on Amazon SageMaker AI"


# ---------------------------------------------------------------- utilities
def _sh(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def render_assets(tmp):
    """Render the SVGs at 2x and cut the per-stage crops used by the deck."""
    arch = os.path.join(tmp, "arch.png")
    _sh(["rsvg-convert", "-z", "2", "--background-color", "white",
         os.path.join(IMAGES, "architecture.svg"), "-o", arch])

    icons = os.path.join(IMAGES, "architecture-icons.png")
    if not os.path.isfile(icons):
        icons = os.path.join(tmp, "icons.png")
        _sh(["rsvg-convert", "-z", "2", "--background-color", "white",
             os.path.join(IMAGES, "architecture-icons.svg"), "-o", icons])

    im = Image.open(arch)
    out = {"arch": arch, "icons": icons}

    # lab columns: SVG x = 24/352/680/1008/1336, width 316, y 170..682.
    # Lab 3 runs to 616 inner because of the optional 3D box.
    for i, x in enumerate((24, 352, 680, 1008, 1336), start=1):
        bottom = 1572 if i == 3 else 1364
        box = (x * 2 - 10, 330, (x + 316) * 2 + 10, bottom + 10)
        p = os.path.join(tmp, f"col{i}.png")
        im.crop(box).save(p)
        out[f"col{i}"] = p

    # The lab-column band on its own. The whole diagram scaled to one slide
    # is legible only as a shape; cropping to the columns roughly doubles the
    # type size, and the lower bands get their own slides.
    band = os.path.join(tmp, "arch-columns.png")
    im.crop((30, 120, 3330, 1590)).save(band)
    out["columns"] = band
    return out


def txt(slide, x, y, w, h, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.paragraphs[0].alignment = align
    return tf


def line(tf, text, size=14, bold=False, color=INK, first=False,
         space_before=0, space_after=4, italic=False, font=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font or FONT
    r.font.color.rgb = color
    return p


def rect(slide, x, y, w, h, fill, outline=None, radius=0.06,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if outline is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = outline
        s.line.width = Pt(1.1)
    s.shadow.inherit = False
    s.text_frame.word_wrap = True
    return s


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = SW, SH
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def _new(self):
        return self.prs.slides.add_slide(self.blank)

    def chrome(self, slide, kicker=None, kicker_color=ORANGE, number=True):
        """Footer rule, footer text, slide number."""
        self.n += 1
        if number:
            tf = txt(slide, SW - Inches(1.3), FOOT_Y, Inches(0.9),
                     Inches(0.3), align=PP_ALIGN.RIGHT)
            line(tf, str(self.n), size=10, color=GRAY, first=True)
        tf = txt(slide, M, FOOT_Y, Inches(8.0), Inches(0.3))
        line(tf, FOOTER, size=10, color=GRAY, first=True)
        rect(slide, M, FOOT_Y - Inches(0.08), BODY_W, Emu(9525), LINE,
             radius=None, shape=MSO_SHAPE.RECTANGLE)

    def head(self, slide, title, kicker=None, color=ORANGE, sub=None,
             compact=False):
        y = TITLE_Y if not kicker else TITLE_Y + Inches(0.16)
        if kicker:
            tf = txt(slide, M, TITLE_Y - Inches(0.08), BODY_W, Inches(0.3))
            line(tf, kicker.upper(), size=11.5, bold=True, color=color,
                 first=True)
        tf = txt(slide, M, y, BODY_W, Inches(0.6))
        line(tf, title, size=24 if compact else 27, bold=True, color=SQUID,
             first=True)
        rect(slide, M, RULE_Y, Inches(1.5), Inches(0.045), ORANGE,
             radius=None, shape=MSO_SHAPE.RECTANGLE)
        if sub:
            tf = txt(slide, M, RULE_Y + Inches(0.12), BODY_W, Inches(0.4))
            line(tf, sub, size=13, color=GRAY, first=True)

    # ---------------------------------------------------------- slide kinds
    def title_slide(self, title, sub, meta, note):
        s = self._new()
        rect(s, 0, 0, SW, SH, SQUID, radius=None, shape=MSO_SHAPE.RECTANGLE)
        rect(s, 0, SH - Inches(0.34), SW, Inches(0.34), ORANGE, radius=None,
             shape=MSO_SHAPE.RECTANGLE)
        for i, c in enumerate(STAGE):
            rect(s, Inches(1.0) + i * Inches(0.62), Inches(1.5),
                 Inches(0.46), Inches(0.1), c, radius=None,
                 shape=MSO_SHAPE.RECTANGLE)
        tf = txt(s, Inches(1.0), Inches(1.95), Inches(10.9), Inches(2.0))
        line(tf, title, size=42, bold=True, color=WHITE, first=True)
        line(tf, sub, size=19, color=RGBColor(0xD6, 0xDB, 0xE1),
             space_before=14)
        tf = txt(s, Inches(1.0), Inches(5.4), Inches(10.9), Inches(1.0))
        line(tf, meta, size=13, color=ORANGE, first=True)
        self.n += 1
        notes(s, note)
        return s

    def section(self, idx, name, promise, persona, bullets, note):
        """Full-bleed stage divider in the stage's own colour."""
        s = self._new()
        c = STAGE[idx - 1]
        rect(s, 0, 0, SW, SH, c, radius=None, shape=MSO_SHAPE.RECTANGLE)
        rect(s, Inches(7.4), 0, SW - Inches(7.4), SH,
             RGBColor(*[min(255, v + 16) for v in (c[0], c[1], c[2])]),
             radius=None, shape=MSO_SHAPE.RECTANGLE)
        tf = txt(s, Inches(0.9), Inches(1.45), Inches(3.0), Inches(1.5))
        tf.word_wrap = False
        line(tf, f"0{idx}", size=74, bold=True, color=WHITE, first=True)
        tf = txt(s, Inches(0.9), Inches(3.05), Inches(6.2), Inches(2.4))
        line(tf, name.upper(), size=33, bold=True, color=WHITE, first=True)
        line(tf, promise, size=16, color=WHITE, space_before=10)
        line(tf, f"Persona  ·  {persona}", size=13, bold=True, color=WHITE,
             space_before=16)
        tf = txt(s, Inches(8.0), Inches(2.2), Inches(4.5), Inches(3.4))
        for i, b in enumerate(bullets):
            line(tf, b, size=14.5, color=WHITE, first=(i == 0),
                 space_after=12)
        self.n += 1
        notes(s, note)
        return s

    def bullets_slide(self, title, kicker, bullets, note, color=ORANGE,
                      sub=None, lead=None):
        s = self._new()
        self.head(s, title, kicker, color, sub)
        y = BODY_Y + (Inches(0.42) if sub else Inches(0))
        if lead:
            tf = txt(s, M, y, BODY_W, Inches(0.6))
            line(tf, lead, size=16, color=INK, first=True)
            y += Inches(0.72)
        # Centre the block in the space that is left, so short lists do not
        # leave a dead third at the bottom of the slide.
        tf = txt(s, M, y, BODY_W, FOOT_Y - Inches(0.25) - y,
                 anchor=MSO_ANCHOR.MIDDLE)
        pitch = 20 if len(bullets) <= 4 else (15 if len(bullets) <= 5 else 11)
        for i, b in enumerate(bullets):
            if isinstance(b, tuple):
                head, body = b
                line(tf, head, size=16, bold=True, color=color,
                     first=(i == 0), space_before=0 if i == 0 else pitch,
                     space_after=3)
                if body:
                    line(tf, body, size=14.5, color=INK, space_after=0)
            else:
                line(tf, "•  " + b, size=15, color=INK, first=(i == 0),
                     space_before=0 if i == 0 else pitch)
        self.chrome(s)
        notes(s, note)
        return s

    def image_slide(self, title, img, caption, note, kicker=None,
                    color=ORANGE):
        # The diagrams carry their own titles, so this layout keeps the slide
        # chrome to one line and gives the artwork everything else.
        s = self._new()
        tf = txt(s, M, Inches(0.22), BODY_W, Inches(0.34))
        if kicker:
            line(tf, f"{kicker.upper()}   ·   {title}", size=11.5, bold=True,
                 color=color, first=True)
        else:
            line(tf, title, size=11.5, bold=True, color=color, first=True)
        top = Inches(0.62)
        avail_h = FOOT_Y - Inches(0.40) - top
        iw, ih = Image.open(img).size
        w = Emu(int(avail_h * iw / ih))
        if w > BODY_W:
            w, avail_h = BODY_W, Emu(int(BODY_W * ih / iw))
        s.shapes.add_picture(img, Emu(int((SW - w) / 2)), top, width=w,
                             height=Emu(int(avail_h)))
        tf = txt(s, M, FOOT_Y - Inches(0.40), BODY_W, Inches(0.34))
        line(tf, caption, size=10.5, color=GRAY, first=True, italic=True)
        self.chrome(s)
        notes(s, note)
        return s

    def flow_row(self, slide, x, y, w, items, color, h=Inches(0.72),
                 back_label=None):
        """A row of labelled boxes joined by arrows, drawn natively.

        The equivalent bands cut from architecture.svg are 27:1 strips -- at
        slide width they render about 0.4in tall and are unreadable, so these
        are redrawn as real shapes instead.
        """
        n = len(items)
        gap = Inches(0.46)
        bw = Emu(int((w - gap * (n - 1)) / n))
        for i, label in enumerate(items):
            bx = x + i * (bw + gap)
            box = rect(slide, bx, y, bw, h, WHITE, outline=color)
            tf = box.text_frame
            tf.margin_left = tf.margin_right = Inches(0.06)
            tf.margin_top = tf.margin_bottom = Inches(0.04)
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = label
            r.font.size, r.font.bold, r.font.name = Pt(12.5), True, FONT
            r.font.color.rgb = SQUID
            if i < n - 1:
                ax = bx + bw + Inches(0.08)
                rect(slide, ax, y + h / 2 - Inches(0.09), Inches(0.3),
                     Inches(0.18), color, radius=None,
                     shape=MSO_SHAPE.RIGHT_ARROW)
        if back_label:
            by = y + h + Inches(0.26)
            rect(slide, x + Inches(0.4), by, w - Inches(0.8), Inches(0.03),
                 ORANGE, radius=None, shape=MSO_SHAPE.RECTANGLE)
            rect(slide, x + Inches(0.1), by - Inches(0.09), Inches(0.3),
                 Inches(0.21), ORANGE, radius=None, shape=MSO_SHAPE.LEFT_ARROW)
            lbl = rect(slide, x + w / 2 - Inches(2.0), by - Inches(0.16),
                       Inches(4.0), Inches(0.36), WHITE, outline=ORANGE)
            tf = lbl.text_frame
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = back_label
            r.font.size, r.font.name = Pt(12), FONT
            r.font.color.rgb = RGBColor(0xC2, 0x57, 0x1A)
        return y + h + (Inches(0.78) if back_label else Inches(0.36))

    def flow_slide(self, title, kicker, items, bullets, note, color=ORANGE,
                   lead=None, back_label=None):
        s = self._new()
        self.head(s, title, kicker, color)
        y = BODY_Y
        if lead:
            tf = txt(s, M, y, BODY_W, Inches(0.5))
            line(tf, lead, size=15.5, color=INK, first=True)
            y += Inches(0.56)
        y = self.flow_row(s, M, y, BODY_W, items, color,
                          back_label=back_label)
        tf = txt(s, M, y, BODY_W, FOOT_Y - Inches(0.25) - y,
                 anchor=MSO_ANCHOR.MIDDLE)
        pitch = 16 if len(bullets) <= 3 else 11
        for i, b in enumerate(bullets):
            if isinstance(b, tuple):
                line(tf, b[0], size=15, bold=True, color=color,
                     first=(i == 0), space_before=0 if i == 0 else pitch,
                     space_after=3)
                line(tf, b[1], size=14, color=INK)
            else:
                line(tf, "•  " + b, size=14.5, color=INK, first=(i == 0),
                     space_before=0 if i == 0 else pitch)
        self.chrome(s)
        notes(s, note)
        return s

    def stage_slide(self, idx, title, kicker, col_img, concepts, labs, note):
        """Two columns of text plus the lab's own column from the diagram."""
        s = self._new()
        c = STAGE[idx - 1]
        self.head(s, title, kicker, c)
        col_w = Inches(3.05)
        img_x = SW - M - col_w
        iw, ih = Image.open(col_img).size
        h = Emu(int(col_w * ih / iw))
        max_h = FOOT_Y - Inches(0.2) - BODY_Y
        if h > max_h:
            h = Emu(int(max_h))
            col_w = Emu(int(max_h * iw / ih))
            img_x = SW - M - col_w
        s.shapes.add_picture(col_img, img_x, BODY_Y, width=col_w, height=h)

        text_w = img_x - M - Inches(0.35)

        # The "what you will run" card is anchored to the bottom and sized
        # from its row count; the concepts get whatever is above it. Sizing
        # the card from the concepts instead let long concept lines wrap into
        # the card and disappear behind it.
        card_h = Inches(0.42) + Inches(0.265) * (len(labs) + 1)
        card_y = FOOT_Y - Inches(0.18) - card_h
        tf = txt(s, M, BODY_Y, text_w, card_y - BODY_Y - Inches(0.18))
        line(tf, "CONCEPTS", size=11, bold=True, color=c, first=True,
             space_after=7)
        for b in concepts:
            line(tf, "•  " + b, size=13, color=INK, space_after=7)

        card = rect(s, M, card_y, text_w, card_h, TINT[idx - 1])
        ctf = card.text_frame
        ctf.margin_left = Inches(0.18)
        ctf.margin_right = Inches(0.14)
        ctf.margin_top = Inches(0.12)
        ctf.margin_bottom = Inches(0.12)
        p0 = line(ctf, "WHAT YOU WILL RUN", size=11, bold=True, color=c,
                  first=True, space_after=5)
        p0.alignment = PP_ALIGN.LEFT
        for lab, desc in labs:
            p = ctf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            p.space_after = Pt(5)
            r = p.add_run()
            r.text = lab + "  "
            r.font.size, r.font.bold, r.font.name = Pt(13), True, FONT
            r.font.color.rgb = c
            r2 = p.add_run()
            r2.text = desc
            r2.font.size, r2.font.name = Pt(13), FONT
            r2.font.color.rgb = INK
        self.chrome(s)
        notes(s, note)
        return s

    def table_slide(self, title, kicker, headers, rows, note, lead=None,
                    color=ORANGE, widths=None, fsize=12.5):
        s = self._new()
        self.head(s, title, kicker, color)
        y = BODY_Y
        if lead:
            tf = txt(s, M, y, BODY_W, Inches(0.5))
            line(tf, lead, size=15, color=INK, first=True)
            y += Inches(0.56)
        # Grow the rows to fill the slide instead of leaving a dead band
        # under short tables.
        avail = FOOT_Y - Inches(0.22) - y
        rowh = Emu(min(int(Inches(0.56)), int(avail / (len(rows) + 1))))
        shape = s.shapes.add_table(len(rows) + 1, len(headers), M, y, BODY_W,
                                   rowh * (len(rows) + 1))
        tbl = shape.table
        if widths:
            total = sum(widths)
            for i, w in enumerate(widths):
                tbl.columns[i].width = Emu(int(BODY_W * w / total))
        tbl.first_row = True
        for j, htext in enumerate(headers):
            cell = tbl.cell(0, j)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = SQUID
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.1)
            line(cell.text_frame, htext, size=fsize, bold=True, color=WHITE,
                 first=True)
        for i, row in enumerate(rows, start=1):
            tbl.rows[i].height = rowh
            for j, val in enumerate(row):
                cell = tbl.cell(i, j)
                cell.text = ""
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.margin_left = cell.margin_right = Inches(0.1)
                line(cell.text_frame, val, size=fsize,
                     bold=(j == 0), color=INK if j else SQUID, first=True)
        self.chrome(s)
        notes(s, note)
        return s

    def cards_slide(self, title, kicker, cards, note, color=ORANGE,
                    lead=None, cols=3):
        s = self._new()
        self.head(s, title, kicker, color)
        y = BODY_Y
        if lead:
            tf = txt(s, M, y, BODY_W, Inches(0.5))
            line(tf, lead, size=15.5, color=INK, first=True)
            y += Inches(0.58)
        gap = Inches(0.26)
        cw = Emu(int((BODY_W - gap * (cols - 1)) / cols))
        rows = (len(cards) + cols - 1) // cols
        ch = Emu(int((FOOT_Y - Inches(0.3) - y - gap * (rows - 1)) / rows))
        for i, (head, body) in enumerate(cards):
            cx = M + (i % cols) * (cw + gap)
            cy = y + (i // cols) * (ch + gap)
            card = rect(s, cx, cy, cw, ch, LIGHT, outline=LINE)
            rect(s, cx, cy, Inches(0.055), ch, color, radius=None,
                 shape=MSO_SHAPE.RECTANGLE)
            tf = card.text_frame
            tf.margin_left = Inches(0.22)
            tf.margin_right = Inches(0.16)
            tf.margin_top = Inches(0.16)
            p0 = line(tf, head, size=15, bold=True, color=SQUID, first=True,
                      space_after=6)
            p0.alignment = PP_ALIGN.LEFT
            for b in body:
                p = line(tf, b, size=12.5, color=INK, space_after=4)
                p.alignment = PP_ALIGN.LEFT
        self.chrome(s)
        notes(s, note)
        return s

    def closing(self, title, lines, note):
        s = self._new()
        rect(s, 0, 0, SW, SH, SQUID, radius=None, shape=MSO_SHAPE.RECTANGLE)
        rect(s, 0, 0, SW, Inches(0.3), ORANGE, radius=None,
             shape=MSO_SHAPE.RECTANGLE)
        tf = txt(s, Inches(1.1), Inches(1.5), Inches(10.5), Inches(1.0))
        line(tf, title, size=36, bold=True, color=WHITE, first=True)
        tf = txt(s, Inches(1.1), Inches(2.9), Inches(10.5), Inches(3.4))
        for i, t in enumerate(lines):
            line(tf, t, size=16, color=WHITE if i == 0 else
                 RGBColor(0xD6, 0xDB, 0xE1), first=(i == 0), space_after=12)
        self.n += 1
        notes(s, note)
        return s

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.prs.save(path)


# ============================================================== deck content
def build(a):
    d = Deck()

    # ---------------------------------------------------------------- 1 open
    d.title_slide(
        "GenAI / ML Standardization on AWS",
        "A guided tour of the five lifecycle stages before you open a notebook",
        "Amazon SageMaker AI  ·  Workshop walkthrough  ·  60 minutes",
        "0:00 (2 min). Welcome. One sentence on why we spend an hour on slides "
        "before labs: the labs are deep, and people who understand the shape of "
        "the whole lifecycle finish more of them. Ask the room: who builds "
        "models, who runs platforms, who owns governance. Use that to decide "
        "which stages to linger on.")

    d.bullets_slide(
        "How this hour runs", "Agenda",
        [("Stage by stage, 5 to 12 minutes each",
          "For every stage: the problem it solves, the concepts you need, then "
          "the labs that make it real."),
         ("Architecture twice, at two zoom levels",
          "Services per stage first, then the detailed build. Both diagrams are "
          "in the workshop guide, so you do not need to copy anything down."),
         ("Then you run the labs",
          "The last slides are the order of execution, the prerequisites that "
          "actually block people, and the cleanup rules.")],
        "0:02 (1 min). Set expectations: slides are a map, not a manual. The "
        "guide has every command. Tell them to save deep questions for the "
        "stage they belong to. Flag now that there is a hard rule coming about "
        "Lab 1E, and that you will repeat it.",
        lead="Five stages, one dataset journey, and a governance thread that "
             "runs through all of it.")

    d.cards_slide(
        "The problem we are standardizing away", "Why this workshop exists",
        [("Every team invents the platform",
          ["One team's notebook role can read every bucket.",
           "Another's cannot reach the data at all.",
           "Nobody can say which is correct."]),
         ("Models exist, provenance does not",
          ["Metrics live in a chat thread.",
           "The prompt that produced them was edited last week.",
           "\"Which data trained this?\" has no answer."]),
         ("Deployment is a person",
          ["A human copies artifacts to an endpoint.",
           "Approval is implicit and unrecorded.",
           "Rollback is a rebuild."]),
         ("Drift is discovered by a customer",
          ["No baseline to compare against.",
           "No signal that quality moved.",
           "Retraining is a reaction, not a decision."]),
         ("Audit is an archaeology project",
          ["Who approved this model, and when?",
           "Which endpoint serves which version?",
           "Evidence is assembled after the fact."]),
         ("Cost arrives as a surprise",
          ["Idle GPU endpoints nobody owns.",
           "Clusters left running over a weekend.",
           "No teardown path."])],
        "0:03 (3 min). This is the slide to make personal. Ask for a show of "
        "hands on the one they recognise. Do not read all six - pick the two "
        "the room reacts to. The point to land: none of these are model "
        "problems, they are platform problems, and that is what gets "
        "standardized.",
        cols=3)

    d.bullets_slide(
        "What \"standardized\" means here", "The thesis",
        [("The lifecycle is a loop, not a pipeline",
          "Five stages, and the fifth feeds the second. A drift verdict is a "
          "retraining decision, not a dashboard."),
         ("Each stage has an owner and a contract",
          "A persona owns the stage; the stage emits one defined artifact that "
          "the next one consumes. Change the tool inside a stage and nothing "
          "downstream notices."),
         ("Governance is a thread, not a gate at the end",
          "Prompt version, dataset snapshot, experiment run, model package, "
          "approval, captured prediction, drift verdict - each one points at "
          "the one before it."),
         ("Infrastructure is code you did not write today",
          "Six CloudFormation stacks stand up the platform. Notebooks consume "
          "it. No notebook creates a VPC.")],
        "0:06 (2 min). The four ideas that make the rest of the hour hang "
        "together. Spend most of the time on the contract idea - it is why the "
        "workshop can offer four different data-prep tools without four "
        "different downstream paths. Preview the loop; you will show it closing "
        "in stage 5.")

    d.image_slide(
        "Services by lifecycle stage", a["icons"],
        "One band per stage. SageMaker AI recurs because the workshop uses "
        "several of its capabilities. Dashed outline = optional step. "
        "Dark tile = the one non-AWS tool, GitHub Actions.",
        "0:08 (3 min). Orient, do not enumerate. Trace left to right across "
        "two bands so they learn to read it, then let them scan. Call out that "
        "SageMaker AI appears five times - Studio, Processing, Training, "
        "JumpStart, serverless customization, MLflow, Model Registry - because "
        "people hear \"SageMaker\" as one thing. Point at the dashed tiles and "
        "say: that is Lab 3D, optional, we will come back to it.",
        kicker="Architecture, zoom level 1")

    d.image_slide(
        "The build, in detail", a["columns"],
        "One column per lab, with the concepts each one teaches. The dashed "
        "box under Lab 3 is the optional serverless path. The shared bands "
        "below this crop — capture plane, platform foundation, IaC — get their "
        "own slides; the full diagram is in the workshop guide.",
        "0:11 (3 min). Do not read this slide - it is a reference they will "
        "come back to. Make three points only: columns are labs, the bands "
        "below are shared infrastructure provisioned once, and the dashed "
        "orange line is the loop closing from stage 5 back to stage 2. Mention "
        "the dashed box under Lab 3 is the optional serverless path. Then move "
        "on; the stage sections zoom into each column.",
        kicker="Architecture, zoom level 2")

    d.bullets_slide(
        "The governance thread", "Follow one claim end to end",
        [("A reviewer asks: what produced this number?", ""),
         ("Prompt  →  MLflow Prompt Registry version, pinned by alias",
          "Lab 2A registers it. Not a file in a folder."),
         ("Data  →  Iceberg snapshot ID, queried with FOR VERSION AS OF",
          "Lab 2F captures it. The baseline cannot move under you."),
         ("Experiment  →  MLflow run, with dataset and prompt version attached",
          "Labs 3A / 3B write it."),
         ("Model  →  Model Registry package + model card + metrics",
          "Lab 3C registers it, with the prompt version the metrics came from."),
         ("Promotion  →  approval status flips, CI/CD reacts",
          "Lab 4. The approval is the trigger, not a ticket."),
         ("Production  →  captured predictions, drift verdicts, audit trail",
          "Labs 5C / 5D. Evidence, queryable in Athena.")],
        "0:14 (3 min). The spine of the whole workshop. Walk down it once, "
        "slowly. The sentence to say out loud: every link points at the one "
        "above it, so a question about a production prediction can be answered "
        "all the way back to the prompt text. Contrast with the earlier "
        "\"metrics in a chat thread\" slide.")

    d.table_slide(
        "Two tracks, one lifecycle", "What you will actually build",
        ["", "Traditional ML track", "GenAI track"],
        [["Dataset", "UCI Bank Marketing, ~41K rows, tabular",
          "Dolly 15K summarization subset (or an offline synthetic corpus)"],
         ["Question", "Will this customer subscribe to a term deposit?",
          "Summarize this passage in our house style"],
         ["Model", "XGBoost binary classifier",
          "Llama 3.2 3B, fine-tuned"],
         ["Prepared in", "Lab 2B–2E (pick one), then 2F", "Lab 2A"],
         ["Built in", "Lab 3A", "Lab 3B + 3C, optionally 3D"],
         ["Deployed in", "Lab 4A, tested in 4B", "Lab 4C"],
         ["Monitored in", "Labs 5A–5F", "Labs 5A–5C"]],
        "0:17 (2 min). People get lost later if they do not know there are two "
        "parallel tracks. Say which track your audience should prioritise if "
        "time is short. Note the tracks share stages 1, 4 and 5 - the platform "
        "and the governance are the same whether the model is XGBoost or an "
        "LLM. That is the whole argument of the workshop in one table.",
        widths=[14, 43, 43], fsize=12)

    # ----------------------------------------------------------- 2 stage one
    d.section(
        1, "Infra setup", "A governed environment, provisioned once, consumed "
        "by every later lab.", "Platform Admin",
        ["VPC-only Studio domain, no public egress",
         "IAM execution roles, least privilege",
         "S3 Access Grants instead of bucket-policy sprawl",
         "Managed MLflow tracking server",
         "Optional: SAML federation, Service Catalog"],
        "0:19 (1 min). Transition. Frame stage 1 as the stage most data "
        "scientists want to skip and most enterprises cannot. Everything later "
        "assumes this exists.")

    d.stage_slide(
        1, "What makes an environment governed", "Stage 1 · concepts",
        a["col1"],
        ["VpcOnly domain: Studio traffic never touches the public internet; "
         "VPC endpoints reach AWS services privately.",
         "Execution roles, not user credentials: the notebook's identity is "
         "the audit subject.",
         "S3 Access Grants: grant identities scoped paths, instead of growing "
         "one bucket policy forever.",
         "Self-service provisioning: Service Catalog publishes the approved "
         "environment so teams stop hand-rolling one.",
         "Federation with per-user isolation: SAML principal tags matched "
         "against resource tags, so a user opens only their own space."],
        [("1A", "self-provision with CloudFormation"),
         ("1B", "validate the pre-provisioned Workshop Studio environment"),
         ("1C", "provision via Service Catalog products"),
         ("1D", "Okta SAML federation (optional)"),
         ("1E", "shared workspace setup (required)")],
        "0:20 (4 min). Pick the baseline your event uses - 1A for own "
        "accounts, 1B for Workshop Studio - and say which one they will do, so "
        "nobody runs all three. Explain Access Grants briefly: it is the "
        "control that makes 'governed data access' concrete rather than a "
        "slogan. Then set up the next slide: there is one step in Lab 1 nobody "
        "may skip.")

    d.bullets_slide(
        "The one rule for the whole workshop", "Lab 1E · required",
        [("Run Lab 1E once per JupyterLab space, before any other lab",
          "lab0-setup/setup.ipynb. It installs the shared kernel dependencies "
          "and discovers your environment."),
         ("It writes one .env at the repository root",
          "Region, account, project name, data bucket, execution role, user "
          "profile, MLflow tracking URI, Iceberg identifiers."),
         ("Every later notebook reads that file",
          "workshop_env.load_workshop_env(). No notebook hardcodes a bucket, a "
          "role or a database name."),
         ("Skipping it is the number one cause of a lab failing on cell one",
          "If a value looks wrong later, fix .env or re-run 1E. Do not edit the "
          "notebook."),
         ("Notebooks contain no pip install cells, by design",
          "requirements.txt is the single source of truth for packages.")],
        "0:24 (2 min). Slow down and be blunt. This is the slide that saves "
        "you forty minutes of support during the lab block. Ask them to "
        "actually do it first. Mention that 1E is also how the deck's claims "
        "stay true - every lab reads the same .env, so there is one place to "
        "look when something is off.",
        color=STAGE[0])

    # ----------------------------------------------------------- 3 stage two
    d.section(
        2, "Data prep", "Two datasets, four interchangeable engines, one "
        "output contract.", "Data Engineer",
        ["2A: instruction data for fine-tuning",
         "2B–2E: tabular prep, pick exactly one",
         "2F: register into Iceberg, always",
         "Quality gates before any GPU spend",
         "Prompts and snapshots become versioned artifacts"],
        "0:26 (1 min). Transition. The stage that did not exist in v1 of this "
        "workshop, because preprocessing used to hide inside training "
        "notebooks. Say why that was a problem: unversioned inputs make every "
        "downstream metric unfalsifiable.")

    d.stage_slide(
        2, "Data prep as a governed step", "Stage 2 · concepts",
        a["col2"],
        ["Validate before you spend: schema, length, groundedness, "
         "compression ratio, exact and near-duplicate detection.",
         "A split you can defend: 70/30 stratified, with an explicit leakage "
         "check asserting no record lands on both sides.",
         "The prompt is an artifact: registered and aliased in the MLflow "
         "Prompt Registry, not a string in a cell.",
         "One contract, four engines: 2B–2E write identical keys and formats, "
         "so Lab 3 never knows which ran.",
         "Iceberg snapshots pin the baseline: 2F captures the snapshot IDs "
         "that Labs 3 and 5 read with FOR VERSION AS OF."],
        [("2A", "Dolly or synthetic → train/test.jsonl + template.json"),
         ("2B", "SageMaker Processing job"),
         ("2C", "EMR Serverless"),
         ("2D", "EMR on EC2"),
         ("2E", "Canvas, low-code"),
         ("2F", "Iceberg registration — required after 2B–2E")],
        "0:27 (5 min). Two things to be explicit about. First: 2B–2E are "
        "alternatives, not a sequence - pick one, by team skill or curiosity, "
        "and 2F is mandatory afterwards. Second: the quality gates are the "
        "interesting part of 2A. Walk one gate, groundedness, and explain why "
        "a summary that cites a fact its context omits is poison for a "
        "fine-tune. Mention the synthetic path exists for locked-down VPCs.")

    d.bullets_slide(
        "Why time travel matters later", "Stage 2 · the payoff",
        [("A drift test compares today against a fixed yesterday",
          "If 'yesterday' is a mutable table, every drift number is "
          "unreproducible - and a monitoring lab that cannot be reproduced is "
          "theatre."),
         ("Lab 2F captures snapshot IDs at registration time",
          "They are written into .env and read by Labs 3 and 5."),
         ("Lab 5D queries the baseline with FOR VERSION AS OF <snapshot>",
          "The comparison set is frozen, by construction, no matter what else "
          "was appended to the table."),
         ("Same mechanism answers the audit question",
          "'Which exact rows trained this model?' is a snapshot ID, not a "
          "best guess.")],
        "0:32 (2 min). This is a small slide with a big idea, and it is worth "
        "the two minutes because it is the most transferable thing in the "
        "workshop. Most teams version code and models and leave data mutable. "
        "Ask: how would you reproduce last quarter's drift report today?",
        color=STAGE[1])

    # --------------------------------------------------------- 4 stage three
    d.section(
        3, "Model build", "Train, evaluate and register - with lineage that "
        "survives the people who made it.", "Data Scientist",
        ["3A: XGBoost on the governed Iceberg tables",
         "3B: fine-tune Llama 3.2 3B via JumpStart",
         "3C: evaluate, then register with a model card",
         "3D: the same job, serverless (optional)",
         "MLflow tracks every run, both tracks"],
        "0:34 (1 min). Transition. The stage people came for. Keep the energy "
        "but hold the line: the lesson is not 'we trained a model', it is "
        "'the model arrives in the registry with its provenance attached'.")

    d.stage_slide(
        3, "Build, with provenance attached", "Stage 3 · concepts",
        a["col3"],
        ["Experiment tracking is not optional plumbing: MLflow holds params, "
         "metrics, artifacts and the dataset and prompt versions used.",
         "Train/inference prompt parity: the container reads template.json "
         "from the training channel, and evaluation re-renders the same text.",
         "Metrics are only valid relative to a prompt: score with a different "
         "template and the numbers describe a model that does not exist.",
         "The registry is the boundary: a model package plus a model card is "
         "the hand-off to stage 4, and approval status is its gate.",
         "Capacity is a real constraint: 3B walks a GPU instance fallback "
         "list, which is honest engineering, not a workaround."],
        [("3A", "XGBoost → MLflow → registry → endpoint"),
         ("3B", "JumpStart fine-tune, SDK v3 ModelTrainer"),
         ("3C", "ROUGE + BLEU via mlflow.evaluate, then register"),
         ("3D", "serverless customization (optional, region-limited)")],
        "0:35 (6 min). The richest stage - budget accordingly. Two points to "
        "make carefully. One: 3B before 3C, because 3C reads the prompt "
        "version 3B pinned to its run; this is the ordering people break. Two: "
        "the metrics-relative-to-a-prompt idea, which is the single most "
        "common silent error in LLM evaluation. If the room is traditional-ML "
        "heavy, spend the time on 3A and the registry instead.")

    d.table_slide(
        "Lab 3D: the same fine-tune, without the compute decisions",
        "Stage 3 · optional path",
        ["", "Labs 3B + 3C", "Lab 3D"],
        [["Compute", "you pick the instance type", "SageMaker owns it"],
         ["GPU capacity", "you write the fallback logic", "not your problem"],
         ["Techniques", "whatever the container supports",
          "SFT, DPO, RLVR, RLAIF recipes only"],
         ["Base models", "the whole JumpStart catalogue",
          "models with a serverless recipe"],
         ["Prompt delivery", "template.json in the channel",
          "rendered into the dataset by 2A"],
         ["Dataset", "an S3 path", "a versioned DataSet artifact"],
         ["Registration", "explicit, in Lab 3C", "automatic, on job completion"],
         ["MLflow", "you wire it up", "automatic"],
         ["Custom container", "supported", "not supported"]],
        "0:41 (3 min). Frame it as a trade, not an upgrade: control for "
        "operational surface. For a standard LoRA SFT on a supported model it "
        "is a good deal; for a custom loss or a bespoke container, 3B is the "
        "only path. Then the logistics: 3D is optional, self-contained, "
        "registers to its own package group, creates no endpoint, and is "
        "region-limited - us-east-1, us-west-2, ap-northeast-1, eu-west-1. If "
        "your event runs in us-east-2 it will stop at the region check; say so "
        "now.",
        lead="Optional, self-contained, and region-limited. Labs 4 and 5 are "
             "identical whether you run it or skip it.",
        color=STAGE[2], widths=[16, 42, 42], fsize=11.5)

    # ---------------------------------------------------------- 5 stage four
    d.section(
        4, "Model deploy", "Automated promotion, with a human decision as the "
        "trigger.", "ML Engineer  ·  Governance Officer",
        ["Model Registry approval is the control point",
         "GitHub Actions drives build and deploy",
         "CDK provisions and updates the endpoint",
         "One shared build repo, one shared deploy repo",
         "Deploying with capture on feeds stage 5"],
        "0:44 (1 min). Transition. The stage where two personas meet: the "
        "engineer owns the pipeline, the governance officer owns what passes "
        "through it.")

    d.stage_slide(
        4, "Promotion as an event, not a handover",
        "Stage 4 · concepts", a["col4"],
        ["Approval status is the API between personas: the engineer never "
         "decides what ships, and the approver never touches a pipeline.",
         "Flipping status to Approved emits an event, and the event starts the "
         "deployment workflow - nobody copies an artifact.",
         "Deployment is code: a CDK stack retrieves the approved package and "
         "provisions or updates the endpoint, with validation and rollback.",
         "A monorepo layout keeps ten models from meaning twenty "
         "repositories: each model owns models/<name>/.",
         "Capture is a deployment-time switch: set SQS_QUEUE_URL and the "
         "endpoint's predictions start landing in Iceberg for stage 5."],
        [("4A", "ML CI/CD: build from Iceberg, register, approve, deploy"),
         ("4B", "ML endpoint testing: validate the 4A endpoint"),
         ("4C", "GenAI CI/CD: the same flow for the fine-tuned model")],
        "0:45 (5 min). Walk the event chain once: push, pipeline, register as "
        "pending, human approves, event fires, CDK deploys, endpoint serves. "
        "Then ask the governance question out loud - who in your organisation "
        "holds the approval? That is usually the most useful conversation in "
        "the hour. Note the OIDC prerequisite for GitHub if they will run this "
        "in their own accounts.")

    d.flow_slide(
        "What is real infrastructure, and what is notebook code",
        "Stage 4 → 5 · the handoff",
        ["SageMaker endpoint", "SQS queue", "logger Lambda",
         "Iceberg tables in Athena", "Lab 5D reads · 5E charts"],
        [("The capture path is deployed, not scripted",
          "endpoint → SQS → logger Lambda → Iceberg tables, created by "
          "templates/4-inference-capture.yaml. A notebook never builds this."),
         ("Lab 5D writes verdicts, not predictions",
          "The predictions arrive through the pipeline above. The notebook "
          "reads them and writes drift results back."),
         ("Drift is computed in the kernel",
          "Evidently runs in the notebook. There is no scheduled drift Lambda, "
          "EventBridge rule or alarm anywhere in this workshop - a deliberate "
          "choice, so you can see the computation."),
         ("Three Iceberg tables hold the evidence",
          "inference_responses, monitoring_responses, ground_truth_updates - "
          "all in the bank_marketing database, queryable in Athena.")],
        "0:50 (2 min). This slide exists because people consistently assume "
        "the opposite in both directions - that capture is notebook code and "
        "that drift detection is a managed service. Correcting it now prevents "
        "confusion in stage 5 and makes the architecture diagram readable.",
        color=STAGE[3])

    # ---------------------------------------------------------- 6 stage five
    d.section(
        5, "Monitoring", "Four different questions, four different signals - "
        "deliberately kept apart.", "Ops  ·  Governance Officer",
        ["Metrics: is it fast, available, right-sized?",
         "Logs: why did that break?",
         "Audit trail: who changed what, and when?",
         "Model quality: is it still right?",
         "Explainability: why this prediction?"],
        "0:52 (1 min). Transition. A model in production is a living system. "
        "The four-layer framing is the thing to remember from this stage.")

    d.stage_slide(
        5, "Four layers, and the loop closing", "Stage 5 · concepts",
        a["col5"],
        ["A model can be fast, clean and compliant while its predictions "
         "quietly degrade - which is why quality is its own layer.",
         "Baselines must be frozen to be comparable: Lab 5D reads the Lab 2F "
         "snapshots with FOR VERSION AS OF.",
         "Verdicts are data: drift results are written to Iceberg and logged "
         "to MLflow, so they can be charted and audited later.",
         "Governance needs a self-service view: Lab 5E publishes a QuickSight "
         "dashboard declared in code, for people who approve rather than build.",
         "Explainability is the other half of trust: SHAP attributes a single "
         "prediction to features, and the artifacts land in MLflow."],
        [("5A", "CloudWatch metrics, dashboards, alarms"),
         ("5B", "CloudWatch Logs and Logs Insights"),
         ("5C", "CloudTrail: who approved this model?"),
         ("5D", "Evidently drift vs pinned baselines"),
         ("5E", "QuickSight governance dashboard"),
         ("5F", "SHAP per-prediction attribution")],
        "0:53 (5 min). Run the four layers as four questions and let them map "
        "the labs onto them. Two logistics notes: 5A creates the SNS topic "
        "that 5B and 5C reuse, so run them in order; and 5E needs QuickSight "
        "Enterprise, which is a one-time account-level step - check before the "
        "lab block whether your accounts have it.")

    d.flow_slide(
        "The loop closes here", "Stage 5 → Stage 2",
        ["1 · Infra setup", "2 · Data prep", "3 · Model build",
         "4 · Model deploy", "5 · Monitoring"],
        [("A drift verdict is a retraining decision",
          "That is the dashed orange path on the architecture diagram, running "
          "from Lab 5 back to Lab 2 - the only arrow that points backwards."),
         ("Which is why stage 2 was built the way it was",
          "Re-preparing data is a governed, repeatable step with a versioned "
          "output, so acting on drift is routine rather than a project."),
         ("And why the thread matters",
          "You can answer 'what changed since the model was approved?' because "
          "every link in the chain is pinned.")],
        "0:58 (1 min). Close the narrative arc you opened at the start. The "
        "line to land: the lifecycle is a loop, and the loop is only cheap to "
        "run if every stage has a contract. Then move to logistics.",
        color=STAGE[4],
        lead="Five stages, and one arrow that points backwards.",
        back_label="drift detected → re-prep data & retrain")

    # ------------------------------------------------------------ 7 logistics
    d.table_slide(
        "Order of execution", "Before you start",
        ["Stage", "Do this", "Rule"],
        [["Lab 1", "One baseline: 1A or 1B or 1C. 1D optional.",
          "Then Lab 1E, always, once per space"],
         ["Lab 2", "2A for the GenAI track; one of 2B–2E for tabular",
          "2F is required after 2B–2E"],
         ["Lab 3", "3A for ML; 3B then 3C for GenAI",
          "3B before 3C — 3C reads what 3B pinned"],
         ["Lab 3D", "Optional, after 3C",
          "Needs 2A only; region-limited"],
         ["Lab 4", "4A then 4B for ML; 4C for GenAI",
          "Deploy with SQS_QUEUE_URL set to feed Lab 5"],
         ["Lab 5", "5A → 5B → 5C, then 5D, 5E, 5F",
          "5B/5C reuse 5A's SNS topic; 5E reads 5D's rows"]],
        "0:59 (2 min). The practical slide. Read the rules column out loud - "
        "these are the four mistakes that cost people the most time. Tell them "
        "this slide is in the guide too, so they do not need to photograph it. "
        "Then hand out whatever your event uses for credentials.",
        lead="Four rules account for most of the time people lose.")

    d.cards_slide(
        "Prerequisites that actually block people", "Before you start",
        [("Lab 1E first",
          ["Without .env, later labs fail on cell one.",
           "Once per JupyterLab space."]),
         ("Lab 3B / 3D: model licence",
          ["Llama 3.2 is gated. You must read and accept the licence.",
           "ACCEPT_EULA ships as False on purpose."]),
         ("Lab 3D: region",
          ["us-east-1, us-west-2, ap-northeast-1, eu-west-1 only.",
           "us-east-2 runs every other lab but not this one."]),
         ("Lab 5E: QuickSight Enterprise",
          ["Account-level, billable, one-time.",
           "The service role also needs data access, or panels fail to load."]),
         ("Lab 4: GitHub OIDC",
          ["A GitHub org with OIDC access to AWS.",
           "Only needed for the CI/CD flow."]),
         ("GPU capacity",
          ["Fine-tuning and GPU endpoints can hit capacity limits.",
           "3B walks a fallback list; retry in another AZ or region."])],
        "1:01 (2 min). Go fast - this is a reference slide. Say which of the "
        "six apply to your event specifically, and skip the rest. If you are "
        "on Workshop Studio, the account, region and QuickSight status are "
        "already decided for them, so tell them what they got.",
        cols=3, color=ORANGE)

    d.bullets_slide(
        "Cleaning up", "Cost discipline",
        [("Endpoints are the expensive thing",
          "They bill by the hour whether or not anyone calls them. Delete them "
          "when a lab is done, unless a later lab needs them - Labs 5A, 5B and "
          "5D use the Lab 3A endpoint."),
         ("Use the teardown script, not the console",
          "scripts/teardown-workshop.sh deletes the six stacks in reverse "
          "order and first clears what blocks deletion: running Studio apps "
          "and objects in the data, grants and MLflow buckets."),
         ("One endpoint can block the networking stack",
          "An endpoint deployed with a VpcConfig holds ENIs in the private "
          "subnets. Teardown detects those and names them; "
          "DELETE_LAB_ENDPOINTS=true removes them first."),
         ("What is left on purpose",
          "Model packages, model cards, MLflow experiments and registered "
          "prompts - the governance record. None of it bills hourly.")],
        "1:03 (2 min). Say the number if you know it - an idle GPU endpoint "
        "over a weekend is a memorable figure. Make the ask explicit: run "
        "teardown before you leave, or at the end of the day if you are "
        "continuing tomorrow.",
        color=STAGE[4])

    d.closing(
        "Over to you",
        ["Start with Lab 1E. Everything else reads the .env it writes.",
         "The guide has every command, every screenshot and both diagrams.",
         "Deep questions are better asked at the stage they belong to — "
         "flag us down as you go.",
         "Repository: github.com/aws-samples/genai-ml-platform-examples "
         "→ workshops/smai-std"],
        "1:05 (Q&A to the hour). Take questions, then start the lab block. If "
        "someone asks what to do with limited time: Lab 1E, then one data-prep "
        "path, then 3A or 3B+3C, then 5A and 5D. That subset tells the whole "
        "story end to end.")

    return d


def main():
    tmp = tempfile.mkdtemp(prefix="smai-slides-")
    assets = render_assets(tmp)
    deck = build(assets)
    deck.save(OUT)
    print(f"wrote {OUT}")
    print(f"  {len(deck.prs.slides.__iter__.__self__._sldIdLst)} slides"
          if False else f"  {len(deck.prs.slides._sldIdLst)} slides")


if __name__ == "__main__":
    main()
