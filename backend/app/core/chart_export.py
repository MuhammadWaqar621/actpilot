import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BAR_COLOR = "#2563eb"
PIE_COLORS = ["#2563eb", "#ea580c", "#16a34a", "#9333ea", "#dc2626", "#0891b2", "#ca8a04", "#0d9488"]

CHART_TYPES = {"bar", "barh", "pie", "line", "area", "scatter", "histogram"}


def _strip_top_right(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def build_chart_image(chart: dict) -> str:
    """chart: {"type": <one of CHART_TYPES>, "title": str, "labels": [str], "values": [float]}
    Returns a base64 PNG data URL, rendered server-side with matplotlib - no
    browser dependency, unlike Plotly's kaleido exporter."""
    chart_type = chart.get("type", "bar")
    values = chart["values"]
    labels = chart.get("labels") or [str(i + 1) for i in range(len(values))]
    x = range(len(values))

    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=150)

    if chart_type == "pie":
        ax.pie(values, labels=labels, autopct="%1.0f%%", colors=PIE_COLORS[: len(values)])
        ax.axis("equal")

    elif chart_type == "barh":
        ax.barh(labels, values, color=BAR_COLOR)
        _strip_top_right(ax)
        ax.grid(axis="x", alpha=0.25)
        for i, v in enumerate(values):
            ax.text(v, i, f" {v:g}", ha="left", va="center", fontsize=9)

    elif chart_type == "line":
        ax.plot(labels, values, marker="o", color=BAR_COLOR)
        _strip_top_right(ax)

    elif chart_type == "area":
        ax.fill_between(x, values, color=BAR_COLOR, alpha=0.35)
        ax.plot(x, values, color=BAR_COLOR)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        _strip_top_right(ax)

    elif chart_type == "scatter":
        ax.scatter(x, values, color=BAR_COLOR)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        _strip_top_right(ax)

    elif chart_type == "histogram":
        bins = min(10, max(3, len(values)))
        ax.hist(values, bins=bins, color=BAR_COLOR)
        _strip_top_right(ax)

    else:  # bar (default)
        ax.bar(labels, values, color=BAR_COLOR)
        _strip_top_right(ax)
        for i, v in enumerate(values):
            ax.text(i, v, f"{v:g}", ha="center", va="bottom", fontsize=9)

    if chart.get("title"):
        ax.set_title(chart["title"], fontsize=12, fontweight="bold")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode()
    return f"data:image/png;base64,{encoded}"
