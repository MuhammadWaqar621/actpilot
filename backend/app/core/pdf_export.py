import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

# Both assets live inside backend/assets - deliberately NOT under
# extension/ (a sibling directory one level up) - because on Vercel this
# backend is deployed as its own isolated project rooted at backend/, so
# nothing outside backend/ is present at runtime.
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "icon128.png"
QUERYNEST_MARK_PATH = Path(__file__).resolve().parents[2] / "assets" / "querynest-mark.png"

# Segoe UI is only present on Windows, so this only resolves locally on a
# Windows dev machine. On Vercel (Linux) these .exists() checks below are
# False and fpdf2 falls back to its built-in Helvetica core font instead of
# crashing - fine for ASCII, but Helvetica has no bold/unicode glyph
# coverage beyond latin-1, so non-ASCII chat text (e.g. curly quotes not in
# _ASCII_REPLACEMENTS, or non-Latin scripts) may render as blank/missing
# glyphs in production PDFs. If that matters, bundle a real TTF (e.g.
# DejaVuSans) under backend/assets/fonts/ and point these at it instead.
FONT_REGULAR = Path("C:/Windows/Fonts/segoeui.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/segoeuib.ttf")

BLUE = (37, 99, 235)
DARK = (30, 30, 30)
GRAY = (120, 120, 120)


_ASCII_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...",
}


def _strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "- ", text, flags=re.MULTILINE)
    for char, replacement in _ASCII_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text


class ChatPDF(FPDF):
    """Adds the ActPilot watermark and a "Developed by QueryNest" footer to
    every page automatically - fpdf2 calls footer() itself on each page
    break and at final output, so this stays correct even when a long chat
    spans multiple pages."""

    font_name = "Helvetica"

    def header(self) -> None:
        if not LOGO_PATH.exists():
            return
        size = 130
        cx, cy = self.w / 2, self.h / 2
        with self.local_context(fill_opacity=0.06, stroke_opacity=0.06):
            with self.rotation(30, cx, cy):
                self.image(str(LOGO_PATH), x=cx - size / 2, y=cy - size / 2, w=size, h=size)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(self.font_name, "", 8)
        self.set_text_color(*GRAY)
        x = self.l_margin
        if QUERYNEST_MARK_PATH.exists():
            mark_h = 4
            self.image(str(QUERYNEST_MARK_PATH), x=x, y=self.get_y() + 2, h=mark_h)
            x += mark_h + 2
        self.set_xy(x, self.get_y())
        self.cell(0, 8, "Developed by QueryNest", align="L")


def build_chat_pdf(messages: list[dict], page_title: str | None = None) -> bytes:
    """messages: [{"role": "user"|"assistant", "text": str}, ...]"""
    pdf = ChatPDF()
    pdf.set_auto_page_break(auto=True, margin=18)

    if FONT_REGULAR.exists() and FONT_BOLD.exists():
        pdf.add_font("body", "", str(FONT_REGULAR))
        pdf.add_font("body", "B", str(FONT_BOLD))
        pdf.font_name = "body"
    font = pdf.font_name

    pdf.add_page()

    if LOGO_PATH.exists():
        pdf.image(str(LOGO_PATH), x=10, y=10, w=12, h=12)
        pdf.set_xy(26, 12)
    else:
        pdf.set_xy(10, 12)

    pdf.set_font(font, "B", 16)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 8, "ActPilot", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(26 if LOGO_PATH.exists() else 10)
    pdf.set_font(font, "", 9)
    pdf.set_text_color(*GRAY)
    subtitle = f"Chat transcript - {datetime.now():%Y-%m-%d %H:%M}"
    if page_title:
        subtitle += f"  |  {page_title}"
    pdf.cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Chat-bubble layout matching the extension's sidebar UI: user messages
    # right-aligned in blue, ActPilot's left-aligned in light gray - color
    # and side alone identify the speaker, same as the real chat, so no
    # "You"/"ActPilot" text labels are drawn here either. Bubbles hug their
    # own text (like the real CSS max-width bubbles) instead of all being
    # the same fixed width.
    content_width = pdf.w - pdf.l_margin - pdf.r_margin
    max_text_width = content_width * 0.72 - 8
    padding = 4
    line_height = 6
    min_text_width = 15

    pdf.set_font(font, "", 10.5)

    for msg in messages:
        is_user = msg["role"] == "user"
        text = _strip_markdown(msg["text"])
        fill = BLUE if is_user else (241, 241, 241)
        text_color = (255, 255, 255) if is_user else DARK

        lines = pdf.multi_cell(max_text_width, line_height, text, dry_run=True, output="LINES")
        longest_line = max((pdf.get_string_width(line) for line in lines), default=0)
        text_width = max(min_text_width, min(max_text_width, longest_line + 2))
        # Re-measure at the exact width we'll actually draw with - fpdf2's
        # internal cell margins mean a width sized to the raw string width
        # can still wrap into an extra line, so trust this final line count.
        final_lines = pdf.multi_cell(text_width, line_height, text, dry_run=True, output="LINES")
        bubble_width = text_width + 2 * padding
        bubble_height = len(final_lines) * line_height + 2 * padding

        if pdf.get_y() + bubble_height > pdf.page_break_trigger:
            pdf.add_page()

        x = pdf.l_margin + content_width - bubble_width if is_user else pdf.l_margin
        y = pdf.get_y()

        pdf.set_fill_color(*fill)
        pdf.rect(x, y, bubble_width, bubble_height, style="F", round_corners=True, corner_radius=2)

        pdf.set_xy(x + padding, y + padding)
        pdf.set_text_color(*text_color)
        pdf.multi_cell(text_width, line_height, text, align="L")

        pdf.set_y(y + bubble_height + 4)

    return bytes(pdf.output())
