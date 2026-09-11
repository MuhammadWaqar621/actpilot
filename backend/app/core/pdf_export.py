import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

LOGO_PATH = Path(__file__).resolve().parents[3] / "extension" / "src" / "icons" / "icon128.png"
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


def build_chat_pdf(messages: list[dict], page_title: str | None = None) -> bytes:
    """messages: [{"role": "user"|"assistant", "text": str}, ...]"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    unicode_font = FONT_REGULAR.exists() and FONT_BOLD.exists()
    if unicode_font:
        pdf.add_font("body", "", str(FONT_REGULAR))
        pdf.add_font("body", "B", str(FONT_BOLD))
        font = "body"
    else:
        font = "Helvetica"

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
