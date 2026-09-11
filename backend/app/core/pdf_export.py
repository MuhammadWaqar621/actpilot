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

    for msg in messages:
        is_user = msg["role"] == "user"
        label = "You" if is_user else "ActPilot"
        color = DARK if is_user else BLUE

        pdf.set_font(font, "B", 11)
        pdf.set_text_color(*color)
        pdf.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font(font, "", 10.5)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 6, _strip_markdown(msg["text"]))
        pdf.ln(4)

    return bytes(pdf.output())
