from datetime import date

from core.recommendations import (
    BookInfo,
    ScoredMatchup,
    _proximity_score,
    _uncertainty_score,
    _novelty_score,
    _recency_score,
    generate_rationale,
    score_matchup,
    select_matchups,
)

TODAY = date(2026, 3, 30)


def _book(pid="a", title="Book A", elo=1200.0, matches=0, last_played=None):
    return BookInfo(page_id=pid, title=title, elo=elo, matches_played=matches, last_played=last_played)


# ── Component scores ─────────────────────────────────────────────────────────

class TestProximityScore:
    def test_identical_ratings(self):
        assert _proximity_score(1200, 1200) == 1.0

    def test_large_gap_low_score(self):
        assert _proximity_score(1200, 1800) < 0.05

    def test_moderate_gap(self):
        score = _proximity_score(1200, 1400)
        assert 0.3 < score < 0.7

    def test_symmetric(self):
        assert _proximity_score(1200, 1400) == _proximity_score(1400, 1200)


class TestUncertaintyScore:
    def test_zero_matches(self):
        assert _uncertainty_score(0, 0) == 1.0

    def test_many_matches(self):
        score = _uncertainty_score(50, 50)
        assert score < 0.15

    def test_uses_minimum(self):
        assert _uncertainty_score(0, 100) == _uncertainty_score(0, 50)


class TestNoveltyScore:
    def test_never_played(self):
        assert _novelty_score(0) == 1.0

    def test_played_once(self):
        assert abs(_novelty_score(1) - 1.0 / 3) < 0.01

    def test_decreases_with_count(self):
        assert _novelty_score(5) < _novelty_score(2) < _novelty_score(0)


class TestRecencyScore:
    def test_never_played_is_max(self):
        assert _recency_score(None, None) == 1.0

    def test_played_today(self):
        assert _recency_score(0, 0) == 0.0

    def test_cap_applied(self):
        assert _recency_score(100, 100) == _recency_score(30, 30)

    def test_mixed(self):
        score = _recency_score(0, 30)
        assert abs(score - 0.5) < 0.01


# ── Composite scoring ────────────────────────────────────────────────────────

class TestScoreMatchup:
    def test_equal_new_books_score_high(self):
        a = _book("a", elo=1200, matches=0)
        b = _book("b", elo=1200, matches=0)
        score = score_matchup(a, b, head_to_head_count=0, today=TODAY)
        assert score > 0.9

    def test_far_apart_scores_lower(self):
        close_a = _book("a", elo=1200, matches=0)
        close_b = _book("b", elo=1200, matches=0)
        far_a = _book("c", elo=1200, matches=0)
        far_b = _book("d", elo=2000, matches=0)
        high = score_matchup(close_a, close_b, 0, today=TODAY)
        low = score_matchup(far_a, far_b, 0, today=TODAY)
        assert high > low

    def test_many_h2h_penalised(self):
        a = _book("a", elo=1200, matches=5)
        b = _book("b", elo=1200, matches=5)
        fresh = score_matchup(a, b, 0, today=TODAY)
        stale = score_matchup(a, b, 10, today=TODAY)
        assert fresh > stale

    def test_recently_played_penalised(self):
        a = _book("a", elo=1200, matches=5, last_played=TODAY)
        b = _book("b", elo=1200, matches=5, last_played=TODAY)
        recent = score_matchup(a, b, 0, today=TODAY)

        a2 = _book("c", elo=1200, matches=5, last_played=date(2026, 3, 1))
        b2 = _book("d", elo=1200, matches=5, last_played=date(2026, 3, 1))
        old = score_matchup(a2, b2, 0, today=TODAY)
        assert old > recent


# ── Selection ────────────────────────────────────────────────────────────────

class TestSelectMatchups:
    def _make_books(self, n):
        return [_book(pid=str(i), title=f"Book {i}", elo=1200 + i * 10, matches=i) for i in range(n)]

    def test_returns_requested_count(self):
        books = self._make_books(10)
        result = select_matchups(books, {}, count=5, today=TODAY)
        assert len(result) == 5

    def test_clamps_to_available_pairs(self):
        books = self._make_books(3)
        result = select_matchups(books, {}, count=7, today=TODAY)
        assert len(result) == 3  # C(3,2) = 3

    def test_diversity_constraint(self):
        books = self._make_books(8)
        result = select_matchups(books, {}, count=7, max_appearances=2, today=TODAY)
        from collections import Counter
        appearances = Counter()
        for m in result:
            appearances[m.book_a.page_id] += 1
            appearances[m.book_b.page_id] += 1
        assert all(c <= 2 for c in appearances.values())

    def test_each_result_has_rationale(self):
        books = self._make_books(6)
        result = select_matchups(books, {}, count=5, today=TODAY)
        for m in result:
            assert m.rationale, f"Missing rationale for {m.book_a.title} vs {m.book_b.title}"

    def test_empty_library(self):
        result = select_matchups([], {}, count=5, today=TODAY)
        assert result == []

    def test_single_book(self):
        result = select_matchups([_book()], {}, count=5, today=TODAY)
        assert result == []


# ── Rationale ────────────────────────────────────────────────────────────────

class TestGenerateRationale:
    def test_close_ratings_mentioned(self):
        a = _book("a", "Alpha", elo=1200, matches=10)
        b = _book("b", "Beta", elo=1210, matches=10)
        text = generate_rationale(a, b, 0, today=TODAY)
        assert "close" in text.lower() or "Close" in text

    def test_never_matched_book(self):
        a = _book("a", "Alpha", elo=1200, matches=0)
        b = _book("b", "Beta", elo=1200, matches=5)
        text = generate_rationale(a, b, 0, today=TODAY)
        assert "Alpha" in text
        assert "never" in text.lower()

    def test_first_h2h_mentioned(self):
        a = _book("a", "Alpha", elo=1200, matches=10)
        b = _book("b", "Beta", elo=1200, matches=10)
        text = generate_rationale(a, b, 0, today=TODAY)
        assert "first" in text.lower() or "First" in text

    def test_long_absence_mentioned(self):
        a = _book("a", "Alpha", elo=1200, matches=10, last_played=date(2026, 3, 1))
        b = _book("b", "Beta", elo=1200, matches=10, last_played=TODAY)
        text = generate_rationale(a, b, 3, today=TODAY)
        assert "Alpha" in text
        assert "days" in text

    def test_fallback_rationale(self):
        a = _book("a", "Alpha", elo=1200, matches=20, last_played=date(2026, 3, 25))
        b = _book("b", "Beta", elo=1500, matches=20, last_played=date(2026, 3, 25))
        text = generate_rationale(a, b, 5, today=TODAY)
        assert len(text) > 0
