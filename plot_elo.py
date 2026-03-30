import logging
import os
import warnings

import matplotlib
matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from notion_client import Client
from core.elo import BookStats, update_ratings
from main import get_library_books, get_matches

PASTEL_COLORS = [
    "#FFB3BA", "#BAFFC9", "#BAE1FF", "#FFFFBA", "#E8BAFF",
    "#FFD4BA", "#B5EAD7", "#C7CEEA", "#FFDAC1", "#FF9AA2",
    "#D4A5A5", "#A5D4D4", "#D4D4A5", "#C9A5D4", "#A5D4B8",
]

BACKGROUND = "#FFFDF7"


def _color(i: int) -> str:
    return PASTEL_COLORS[i % len(PASTEL_COLORS)]


def _apply_common_style(ax):
    ax.set_facecolor(BACKGROUND)
    ax.figure.set_facecolor(BACKGROUND)
    for spine in ax.spines.values():
        spine.set_linewidth(1.5)


def _plot_leaderboard(book_stats, books_data, top_n=5):
    sorted_books = sorted(book_stats.items(), key=lambda x: x[1].elo, reverse=True)
    top = sorted_books[:top_n]

    titles = [books_data[bid]["title"] for bid, _ in top][::-1]
    elos = [round(stats.elo, 1) for _, stats in top][::-1]
    colors = [_color(i) for i in range(len(top))][::-1]

    fig, ax = plt.subplots(figsize=(10, 5))
    _apply_common_style(ax)
    y_pos = np.arange(len(titles))
    bars = ax.barh(y_pos, elos, color=colors, edgecolor="#555555", linewidth=1.2, height=0.6)

    for bar, elo in zip(bars, elos):
        ax.text(
            bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
            str(elo), va="center", fontsize=12, fontweight="bold",
        )

    ax.axvline(x=1200, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(titles, fontsize=11)
    ax.set_xlabel("Elo Rating", fontsize=12)
    ax.set_title("Leo's Top Picks", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlim(left=min(1100, min(elos) - 30))

    fig.tight_layout()
    fig.savefig("leaderboard.png", dpi=150)
    plt.close(fig)
    print("Saved leaderboard.png")


def _plot_current_vs_peak(book_stats, books_data):
    sorted_books = sorted(book_stats.items(), key=lambda x: x[1].elo, reverse=True)

    titles = [books_data[bid]["title"] for bid, _ in sorted_books][::-1]
    current = [round(s.elo, 1) for _, s in sorted_books][::-1]
    peak = [round(s.peak_elo, 1) for _, s in sorted_books][::-1]

    fig, ax = plt.subplots(figsize=(10, max(5, len(titles) * 0.55)))
    _apply_common_style(ax)
    y_pos = np.arange(len(titles))
    bar_h = 0.35

    ax.barh(
        y_pos + bar_h / 2, peak, height=bar_h,
        color="#E8BAFF", edgecolor="#555555", linewidth=1, label="Peak Elo", alpha=0.7,
    )
    ax.barh(
        y_pos - bar_h / 2, current, height=bar_h,
        color="#BAE1FF", edgecolor="#555555", linewidth=1, label="Current Elo",
    )

    ax.axvline(x=1200, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(titles, fontsize=10)
    ax.set_xlabel("Elo Rating", fontsize=12)
    ax.set_title("Current vs Peak Elo", fontsize=16, fontweight="bold", pad=15)
    ax.legend(loc="lower right", fontsize=10, framealpha=0.8)
    ax.set_xlim(left=min(1100, min(current + peak) - 30))

    fig.tight_layout()
    fig.savefig("current_vs_peak.png", dpi=150)
    plt.close(fig)
    print("Saved current_vs_peak.png")


def _plot_elo_history(history, books_data):
    fig, ax = plt.subplots(figsize=(12, 7))
    _apply_common_style(ax)

    for i, (b_id, elos) in enumerate(history.items()):
        title = books_data[b_id]["title"]
        ax.plot(elos, color=_color(i), linewidth=2, label=title, marker="o", markersize=3)

    ax.axhline(y=1200, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_xlabel("Match Number", fontsize=12)
    ax.set_ylabel("Elo Rating", fontsize=12)
    ax.set_title("Elo Ratings Over Time", fontsize=16, fontweight="bold", pad=15)
    ax.legend(fontsize=9, loc="best", framealpha=0.8, ncol=2)

    fig.tight_layout()
    fig.savefig("elo_history_chart.png", dpi=150)
    plt.close(fig)
    print("Saved elo_history_chart.png")


def main():
    notion = Client(auth=os.environ.get("NOTION_INTEGRATION_TOKEN"))
    library_id = os.environ.get("LIBRARY_DB_ID")
    matches_id = os.environ.get("MATCHES_DB_ID")

    print("Fetching Library Database...")
    books_data = get_library_books(notion, library_id)

    book_stats = {}
    history = {}

    for b_id in books_data:
        book_stats[b_id] = BookStats(elo=1200.0, matches_played=0, peak_elo=1200.0, wins=0, losses=0)
        history[b_id] = [1200.0]

    print("Fetching Matches Database...")
    matches = get_matches(notion, matches_id)
    print(f"Loaded {len(matches)} matches. Replaying...")

    for match in matches:
        w_id = match["winner_id"]
        l_id = match["loser_id"]
        if w_id in book_stats and l_id in book_stats:
            update_ratings(book_stats[w_id], book_stats[l_id])
            history[w_id].append(book_stats[w_id].elo)
            history[l_id].append(book_stats[l_id].elo)
            for b_id in book_stats:
                if b_id != w_id and b_id != l_id:
                    history[b_id].append(book_stats[b_id].elo)

    print("Generating charts (xkcd style)...")
    warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
    with plt.xkcd():
        _plot_leaderboard(book_stats, books_data)
        _plot_current_vs_peak(book_stats, books_data)
        _plot_elo_history(history, books_data)

    print("All charts generated!")


if __name__ == "__main__":
    main()
