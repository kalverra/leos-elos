import os
import sys
import time
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from notion_client import Client
from core.elo import BookStats, update_ratings

def get_library_books(notion: Client, database_id: str):
    """
    Fetch all books from Library database.
    Returns a dict mapping Notion Page ID to a dict with properties:
      'title', 'elo', 'matches_played', 'wins', 'losses', 'peak_elo'
    """
    results = []
    has_more = True
    start_cursor = None
    while has_more:
        for attempt in range(3):
            try:
                response = notion.databases.query(
                    database_id=database_id,
                    start_cursor=start_cursor
                )
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise e
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor", None)
        results.extend(response["results"])

    books = {}
    for page in results:
        page_id = page["id"]
        props = page["properties"]

        title = "Unknown Title"
        # The Title property name defaults to "Name" or "Title", we fetch the title type
        for prop_name, prop_data in props.items():
            if prop_data["type"] == "title":
                if prop_data["title"]:
                    title = prop_data["title"][0]["plain_text"]
                break

        books[page_id] = {
            "page_id": page_id,
            "title": title,
            "elo": props.get("Elo", {}).get("number") or 1200.0,
            "matches_played": props.get("Matches Played", {}).get("number") or 0,
            "wins": props.get("Wins", {}).get("number") or 0,
            "losses": props.get("Losses", {}).get("number") or 0,
            "peak_elo": props.get("Peak Elo", {}).get("number") or 1200.0
        }
    return books

def get_matches(notion: Client, database_id: str):
    """
    Fetch all matches from Matches database.
    Order them by Datetime ascending.
    """
    results = []
    has_more = True
    start_cursor = None
    while has_more:
        # Check if 'Datetime' exists and we can sort by it
        for attempt in range(3):
            try:
                response = notion.databases.query(
                    database_id=database_id,
                    sorts=[{"property": "Date", "direction": "ascending"}],
                    start_cursor=start_cursor
                )
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise e
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor", None)
        results.extend(response["results"])

    matches = []
    for page in results:
        props = page["properties"]
        
        # Searching for relations
        winners = []
        losers = []

        # Find the relations accurately by inspecting properties
        for prop_name, prop_data in props.items():
            if prop_name.lower() == "winner" and prop_data["type"] == "relation":
                winners = prop_data.get("relation", [])
            elif prop_name.lower() == "loser" and prop_data["type"] == "relation":
                losers = prop_data.get("relation", [])

        if winners and losers:
            winner_id = winners[0]["id"]
            loser_id = losers[0]["id"]
            matches.append({
                "match_id": page["id"],
                "winner_id": winner_id,
                "loser_id": loser_id
            })
    return matches

def main():
    notion_token = os.environ.get("NOTION_INTEGRATION_TOKEN")
    library_db_id = os.environ.get("LIBRARY_DB_ID")
    matches_db_id = os.environ.get("MATCHES_DB_ID")

    if not all([notion_token, library_db_id, matches_db_id]):
        print("Error: Missing required environment variables:")
        print(" - NOTION_INTEGRATION_TOKEN")
        print(" - LIBRARY_DB_ID")
        print(" - MATCHES_DB_ID")
        print("\nPlease add them to a .env file or export them directly.")
        sys.exit(1)

    print("Authenticating with Notion...")
    notion = Client(auth=notion_token)
    
    print("Fetching Library Database...")
    books_data = get_library_books(notion, library_db_id)
    print(f"Loaded {len(books_data)} books.")

    book_stats = {}
    for b_id, b_data in books_data.items():
        # Using a full reset for the full calculation run
        book_stats[b_id] = BookStats(elo=1200.0, matches_played=0, peak_elo=1200.0, wins=0, losses=0)

    print("Fetching Matches Database...")
    matches = get_matches(notion, matches_db_id)
    print(f"Loaded {len(matches)} valid matches.")

    print("Replaying matches and computing Elos...")
    for match in matches:
        w_id = match["winner_id"]
        l_id = match["loser_id"]
        if w_id in book_stats and l_id in book_stats:
            # Capture pre-match Elo for historical tracking
            pre_match_winner_elo = book_stats[w_id].elo
            pre_match_loser_elo = book_stats[l_id].elo
            
            update_ratings(book_stats[w_id], book_stats[l_id])
            
            # Save the historical pre-match Elos to the Matches DB
            try:
                notion.pages.update(
                    page_id=match["match_id"],
                    properties={
                        "Winner Elo": {"number": round(pre_match_winner_elo, 1)},
                        "Loser Elo": {"number": round(pre_match_loser_elo, 1)}
                    }
                )
            except Exception as e:
                print(f"Warning: Failed to update history for match {match['match_id']}: {e}")
        else:
            print(f"Warning: Match {match['match_id']} refers to unknown books. Skipping.")

    print("\nRanking Preview:")
    sorted_books = sorted(book_stats.items(), key=lambda x: x[1].elo, reverse=True)
    for i, (b_id, stats) in enumerate(sorted_books[:10], 1):
        title = books_data[b_id]["title"]
        print(f" {i}. {title} (Elo: {round(stats.elo, 1)}) [W: {stats.wins}, L: {stats.losses}]")

    print("\nUpdating Library Database with new stats...")
    for page_id, stats in book_stats.items():
        try:
            notion.pages.update(
                page_id=page_id,
                properties={
                    "Elo": {"number": round(stats.elo, 1)},
                    "Matches Played": {"number": stats.matches_played},
                    "Wins": {"number": stats.wins},
                    "Losses": {"number": stats.losses},
                    "Peak Elo": {"number": round(stats.peak_elo, 1)},
                }
            )
            book = books_data[page_id]
            print(f"Updated '{book['title']}'")
        except Exception as e:
            book = books_data.get(page_id, {})
            print(f"Failed to update page {page_id} ('{book.get('title', 'Unknown')}'): {e}")
            print("\nPlease ensure your Library Database has these NUMBER properties exactly named:")
            print(" - Elo\n - Matches Played\n - Wins\n - Losses\n - Peak Elo")
            break

    print("Done!")

if __name__ == "__main__":
    main()
