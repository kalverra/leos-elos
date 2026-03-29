# Book Elo Calculation

There are 2 Notion DBs, `Matches` and `Library`

## Matches

* Datetime
* Winner (Relation to Library)
* Loser (Relation to Library)

## Library

* Title
* Cover

## Code

The script is a quick Python calculation of the elo ratings of the books in the library based on the matches in the matches database. It should do a full calculation of the elos of all books, and update stats in the `Library` DB as appropriate.

* Use the [notion python SDK](https://github.com/ramnes/notion-sdk-py)
* Write simple tests for the elo calculation logic
* If you need to modify the Notion DB (e.g., add new properties) use the Notion MCP server if available. If not, prompt the user to make changes.