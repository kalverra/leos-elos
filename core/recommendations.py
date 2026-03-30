import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date


@dataclass
class BookInfo:
    page_id: str
    title: str
    elo: float
    matches_played: int
    last_played: date | None = None


@dataclass
class ScoredMatchup:
    book_a: BookInfo
    book_b: BookInfo
    score: float
    rationale: str = ""


# ── Scoring ──────────────────────────────────────────────────────────────────

WEIGHT_PROXIMITY = 0.25
WEIGHT_UNCERTAINTY = 0.30
WEIGHT_NOVELTY = 0.20
WEIGHT_RECENCY = 0.25

PROXIMITY_SIGMA = 200
UNCERTAINTY_HALFLIFE = 5
RECENCY_CAP_DAYS = 30


def _proximity_score(elo_a: float, elo_b: float) -> float:
    """Gaussian decay on Elo gap. Identical ratings -> 1.0."""
    diff = abs(elo_a - elo_b)
    return math.exp(-(diff ** 2) / (2 * PROXIMITY_SIGMA ** 2))


def _uncertainty_score(matches_a: int, matches_b: int) -> float:
    """High when either book has few matches. Uses the *minimum* count."""
    return 1.0 / (1.0 + min(matches_a, matches_b) / UNCERTAINTY_HALFLIFE)


def _novelty_score(head_to_head_count: int) -> float:
    """High when these two books have rarely (or never) played each other."""
    return 1.0 / (1.0 + head_to_head_count * 2)


def _recency_score(
    days_since_a: int | None,
    days_since_b: int | None,
) -> float:
    """High when both books haven't played in a while.

    ``None`` means the book has *never* played, which counts as maximum
    recency (the full cap).
    """
    cap = RECENCY_CAP_DAYS
    da = cap if days_since_a is None else min(days_since_a, cap)
    db = cap if days_since_b is None else min(days_since_b, cap)
    return (da + db) / (2 * cap)


def score_matchup(
    book_a: BookInfo,
    book_b: BookInfo,
    head_to_head_count: int,
    today: date | None = None,
) -> float:
    today = today or date.today()

    days_a = (today - book_a.last_played).days if book_a.last_played else None
    days_b = (today - book_b.last_played).days if book_b.last_played else None

    return (
        WEIGHT_PROXIMITY * _proximity_score(book_a.elo, book_b.elo)
        + WEIGHT_UNCERTAINTY * _uncertainty_score(book_a.matches_played, book_b.matches_played)
        + WEIGHT_NOVELTY * _novelty_score(head_to_head_count)
        + WEIGHT_RECENCY * _recency_score(days_a, days_b)
    )


# ── Rationale ────────────────────────────────────────────────────────────────

def generate_rationale(
    book_a: BookInfo,
    book_b: BookInfo,
    head_to_head_count: int,
    today: date | None = None,
) -> str:
    today = today or date.today()
    parts: list[str] = []

    diff = abs(book_a.elo - book_b.elo)
    if diff < 50:
        parts.append(f"Very close ratings ({round(book_a.elo)} vs {round(book_b.elo)})")
    elif diff < 150:
        parts.append(f"Comparable ratings ({round(book_a.elo)} vs {round(book_b.elo)})")

    low = min(book_a.matches_played, book_b.matches_played)
    if low == 0:
        under = book_a if book_a.matches_played <= book_b.matches_played else book_b
        parts.append(f'"{under.title}" has never been matched')
    elif low < 5:
        under = book_a if book_a.matches_played <= book_b.matches_played else book_b
        parts.append(f'"{under.title}" is undersampled ({under.matches_played} matches)')

    if head_to_head_count == 0:
        parts.append("First ever head-to-head")
    elif head_to_head_count == 1:
        parts.append("Only 1 prior meeting")

    for book in (book_a, book_b):
        if book.last_played is None:
            continue
        days = (today - book.last_played).days
        if days >= 14:
            parts.append(f'"{book.title}" hasn\'t played in {days} days')

    if not parts:
        parts.append("Good overall matchup diversity")

    return ". ".join(parts)


# ── Selection ────────────────────────────────────────────────────────────────

def _make_pair_key(id_a: str, id_b: str) -> tuple[str, str]:
    return tuple(sorted((id_a, id_b)))


def select_matchups(
    books: list[BookInfo],
    head_to_head: dict[tuple[str, str], int],
    count: int = 7,
    max_appearances: int = 2,
    today: date | None = None,
) -> list[ScoredMatchup]:
    """Score every pair, then greedily pick the top *count* with a diversity cap."""
    today = today or date.today()

    scored: list[ScoredMatchup] = []
    for i, a in enumerate(books):
        for b in books[i + 1 :]:
            key = _make_pair_key(a.page_id, b.page_id)
            h2h = head_to_head.get(key, 0)
            s = score_matchup(a, b, h2h, today=today)
            scored.append(ScoredMatchup(book_a=a, book_b=b, score=s))

    scored.sort(key=lambda m: m.score, reverse=True)

    selected: list[ScoredMatchup] = []
    appearances: Counter[str] = Counter()

    for matchup in scored:
        if len(selected) >= count:
            break
        aid = matchup.book_a.page_id
        bid = matchup.book_b.page_id
        if appearances[aid] >= max_appearances or appearances[bid] >= max_appearances:
            continue
        matchup.rationale = generate_rationale(
            matchup.book_a,
            matchup.book_b,
            head_to_head.get(_make_pair_key(aid, bid), 0),
            today=today,
        )
        selected.append(matchup)
        appearances[aid] += 1
        appearances[bid] += 1

    return selected
