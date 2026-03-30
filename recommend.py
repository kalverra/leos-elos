import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from notion_client import Client

from core.recommendations import BookInfo, select_matchups
from main import get_library_books, get_matches_with_dates


def _build_recommendation_inputs(books_data, matches):
    """Turn raw Notion data into BookInfo list, head-to-head counts, and per-book last-played dates."""
    last_played: dict[str, date] = {}
    head_to_head: dict[tuple[str, str], int] = defaultdict(int)

    for match in matches:
        w_id = match["winner_id"]
        l_id = match["loser_id"]
        pair = tuple(sorted((w_id, l_id)))
        head_to_head[pair] += 1

        if match["date"]:
            try:
                d = datetime.fromisoformat(match["date"]).date()
            except (ValueError, TypeError):
                d = None
            if d:
                for book_id in (w_id, l_id):
                    if book_id not in last_played or d > last_played[book_id]:
                        last_played[book_id] = d

    books: list[BookInfo] = []
    for page_id, data in books_data.items():
        books.append(BookInfo(
            page_id=page_id,
            title=data["title"],
            elo=data["elo"],
            matches_played=data["matches_played"],
            last_played=last_played.get(page_id),
        ))

    return books, dict(head_to_head)


def _archive_existing_recommendations(notion: Client, db_id: str):
    """Archive all current rows in the Recommended Matchups database."""
    has_more = True
    start_cursor = None
    archived = 0
    while has_more:
        for attempt in range(3):
            try:
                response = notion.databases.query(
                    database_id=db_id,
                    start_cursor=start_cursor,
                )
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise e
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
        for page in response["results"]:
            try:
                notion.pages.update(page_id=page["id"], archived=True)
                archived += 1
            except Exception as e:
                print(f"Warning: Failed to archive {page['id']}: {e}")
    return archived


def _write_recommendations(notion: Client, db_id: str, matchups, today: date):
    """Create new pages in the Recommended Matchups database."""
    created = 0
    for rank, matchup in enumerate(matchups, 1):
        title = f"{matchup.book_a.title} vs {matchup.book_b.title}"
        try:
            notion.pages.create(
                parent={"database_id": db_id},
                properties={
                    "Matchup": {"title": [{"text": {"content": title}}]},
                    "Contender 1": {"relation": [{"id": matchup.book_a.page_id}]},
                    "Contender 2": {"relation": [{"id": matchup.book_b.page_id}]},
                    "Rank": {"number": rank},
                    "Score": {"number": round(matchup.score, 4)},
                    "Rationale": {"rich_text": [{"text": {"content": matchup.rationale}}]},
                    "Generated": {"date": {"start": today.isoformat()}},
                },
            )
            created += 1
            print(f"  #{rank}: {title} (score: {matchup.score:.3f})")
        except Exception as e:
            print(f"Error creating recommendation #{rank} ({title}): {e}")
    return created


def main():
    notion_token = os.environ.get("NOTION_INTEGRATION_TOKEN")
    library_db_id = os.environ.get("LIBRARY_DB_ID")
    matches_db_id = os.environ.get("MATCHES_DB_ID")
    recommendations_db_id = os.environ.get("RECOMMENDATIONS_DB_ID")

    required = {
        "NOTION_INTEGRATION_TOKEN": notion_token,
        "LIBRARY_DB_ID": library_db_id,
        "MATCHES_DB_ID": matches_db_id,
        "RECOMMENDATIONS_DB_ID": recommendations_db_id,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print("Error: Missing required environment variables:")
        for k in missing:
            print(f"  - {k}")
        sys.exit(1)

    notion = Client(auth=notion_token)

    print("Fetching Library...")
    books_data = get_library_books(notion, library_db_id)
    print(f"  {len(books_data)} books loaded.")

    print("Fetching Matches (with dates)...")
    matches = get_matches_with_dates(notion, matches_db_id)
    print(f"  {len(matches)} matches loaded.")

    books, head_to_head = _build_recommendation_inputs(books_data, matches)
    print(f"  {len(head_to_head)} unique head-to-head pairings found.")

    today = date.today()
    print("Selecting matchups...")
    matchups = select_matchups(books, head_to_head, count=7, today=today)

    if not matchups:
        print("No matchups to recommend (need at least 2 books).")
        return

    print(f"\nArchiving old recommendations...")
    archived = _archive_existing_recommendations(notion, recommendations_db_id)
    print(f"  Archived {archived} old recommendation(s).")

    print(f"\nWriting {len(matchups)} new recommendations:")
    created = _write_recommendations(notion, recommendations_db_id, matchups, today)
    print(f"\nDone! {created} recommendation(s) written.")


if __name__ == "__main__":
    main()
