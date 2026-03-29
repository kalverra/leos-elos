import os
from dotenv import load_dotenv
from notion_client import Client

def main():
    load_dotenv()
    notion = Client(auth=os.environ.get("NOTION_INTEGRATION_TOKEN"))
    library_id = os.environ.get("LIBRARY_DB_ID")
    
    print("Updating Library DB properties...")
    notion.databases.update(
        database_id=library_id,
        properties={
            "Elo": {"number": {"format": "number"}},
            "Matches Played": {"number": {"format": "number"}},
            "Wins": {"number": {"format": "number"}},
            "Losses": {"number": {"format": "number"}},
            "Peak Elo": {"number": {"format": "number"}},
        }
    )
    print("Library DB properties created/updated successfully!")

if __name__ == "__main__":
    main()
