import pytest
from core.elo import BookStats, update_ratings, calculate_expected_score

def test_expected_score():
    # Equal players expected score should exactly 0.5
    assert calculate_expected_score(1200, 1200) == 0.5
    
    # +400 rating diff ratio: ~ 10-to-1 expected odds
    assert abs(calculate_expected_score(1600, 1200) - 0.909) < 0.01

def test_update_ratings_new_players():
    winner = BookStats()
    loser = BookStats()
    
    # Both are under 30 matches, K=40
    # Expected is 0.5 for both
    # Winner gets 40 * (1 - 0.5) = +20
    # Loser gets 40 * (0 - 0.5) = -20
    
    update_ratings(winner, loser)
    assert winner.elo == 1220.0
    assert winner.wins == 1
    assert winner.matches_played == 1
    assert winner.peak_elo == 1220.0
    
    assert loser.elo == 1180.0
    assert loser.losses == 1
    assert loser.matches_played == 1
    assert loser.peak_elo == 1200.0

def test_update_ratings_established_players():
    winner = BookStats(elo=2000, matches_played=35)
    loser = BookStats(elo=2000, matches_played=35)
    
    # K=20 for > 30 matches and < 2400 peak
    # Both get standard 20 * (diff from expected 0.5) = +- 10
    update_ratings(winner, loser)
    
    assert winner.elo == 2010.0
    assert loser.elo == 1990.0

def test_update_ratings_peak_2400_players():
    winner = BookStats(elo=2390, matches_played=50, peak_elo=2410)
    loser = BookStats(elo=2390, matches_played=50, peak_elo=2410)
    
    # Peak elo >= 2400, so K=10, K factor remains permanent even when hovering at ≤ 2400
    update_ratings(winner, loser)
    
    assert winner.elo == 2395.0
    assert loser.elo == 2385.0
