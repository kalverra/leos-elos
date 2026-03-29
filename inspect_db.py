import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
notion = Client(auth=os.environ.get("NOTION_INTEGRATION_TOKEN"))
matches_id = os.environ.get("MATCHES_DB_ID")
library_id = os.environ.get("LIBRARY_DB_ID")

matches_db = notion.databases.retrieve(matches_id)
print("Matches DB Properties:")
for k, v in matches_db["properties"].items():
    print(f"  - {k} ({v['type']})")

library_db = notion.databases.retrieve(library_id)
print("\nLibrary DB Properties:")
for k, v in library_db["properties"].items():
    print(f"  - {k} ({v['type']})")
