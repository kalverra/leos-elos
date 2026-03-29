import os
import plotly.graph_objects as go

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from notion_client import Client
from core.elo import BookStats, update_ratings
from main import get_library_books, get_matches

def main():
    notion = Client(auth=os.environ.get("NOTION_INTEGRATION_TOKEN"))
    library_id = os.environ.get("LIBRARY_DB_ID")
    matches_id = os.environ.get("MATCHES_DB_ID")

    print("Fetching Library Database...")
    books_data = get_library_books(notion, library_id)

    # Initialize book stats and history trackers
    book_stats = {}
    history = {}  # Map page_id -> list of Elos
    
    for b_id in books_data:
        book_stats[b_id] = BookStats(elo=1200.0, matches_played=0, peak_elo=1200.0, wins=0, losses=0)
        history[b_id] = [1200.0]  # Start at base Elo

    print("Fetching Matches Database...")
    matches = get_matches(notion, matches_id)
    print(f"Loaded {len(matches)} matches. Simulating history line...")

    for match in matches:
        w_id = match["winner_id"]
        l_id = match["loser_id"]
        if w_id in book_stats and l_id in book_stats:
            update_ratings(book_stats[w_id], book_stats[l_id])
            
            # Record post-match ratings for the books involved in THIS match
            history[w_id].append(book_stats[w_id].elo)
            history[l_id].append(book_stats[l_id].elo)
            
            # For all other books, their Elo stayed the same at this timestep
            for b_id in book_stats:
                if b_id != w_id and b_id != l_id:
                    history[b_id].append(book_stats[b_id].elo)

    print("Generating interactive chart...")
    fig = go.Figure()
    
    # Plot a line for each book
    for b_id, elos in history.items():
        title = books_data[b_id]['title']
        fig.add_trace(go.Scatter(y=elos, mode='lines+markers', name=title))

    fig.update_layout(
        title="Book Elo Ratings Over Time",
        xaxis_title="Match Timeline (Number of Total Matches)",
        yaxis_title="Elo Rating",
        hovermode="x unified",
        shapes=[
            dict(
                type="line",
                xref="paper", x0=0, x1=1,
                yref="y", y0=1200, y1=1200,
                line=dict(color="gray", width=1, dash="dash"),
            )
        ]
    )
    
    output_path_html = "elo_history_chart.html"
    output_path_png = "elo_history_chart.png"
    fig.write_html(output_path_html)
    fig.write_image(output_path_png, width=1200, height=800)
    print(f"Success! Interactive graph saved to {output_path_html} and static image to {output_path_png}")

if __name__ == "__main__":
    main()
