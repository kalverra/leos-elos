import math

class BookStats:
    def __init__(self, elo: float = 1200.0, matches_played: int = 0, peak_elo: float = 1200.0, wins: int = 0, losses: int = 0):
        self.elo = elo
        self.matches_played = matches_played
        self.peak_elo = max(elo, peak_elo)
        self.wins = wins
        self.losses = losses

    def get_k_factor(self):
        """
        Standard FIDE chess K-factor logic:
        K = 40 for a player with less than 30 games.
        K = 20 as long as a player's rating remains under 2400.
        K = 10 once a player's published rating has reached 2400.
        """
        if self.peak_elo >= 2400:
            return 10
        if self.matches_played < 30:
            return 40
        return 20

def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def update_ratings(winner: BookStats, loser: BookStats):
    winner_expected = calculate_expected_score(winner.elo, loser.elo)
    loser_expected = calculate_expected_score(loser.elo, winner.elo)

    winner_k = winner.get_k_factor()
    loser_k = loser.get_k_factor()

    winner_new_elo = winner.elo + winner_k * (1 - winner_expected)
    loser_new_elo = loser.elo + loser_k * (0 - loser_expected)

    winner.elo = winner_new_elo
    winner.matches_played += 1
    winner.wins += 1
    winner.peak_elo = max(winner.peak_elo, winner_new_elo)

    loser.elo = loser_new_elo
    loser.matches_played += 1
    loser.losses += 1
    loser.peak_elo = max(loser.peak_elo, loser_new_elo)
