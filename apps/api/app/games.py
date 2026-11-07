"""Everything that differs from game to game: possible scores, what its stations are called and which modes it has.

A result is always the score of both teams (score_a, score_b) and its winner. What a score means is up to the game:
for beer pong the cups a team had left (the loser always has none), for football the goals. The same game rules
live in the web app (components/games).
"""
from collections.abc import Callable
from dataclasses import dataclass

from app.core.exceptions import InvalidScoreError
from app.models.tournament import Game, TournamentMode

# (score of the winner, score of the loser) -> the message why it is not possible, None if it is
ScoreRule = Callable[[int, int], str | None]


@dataclass(frozen=True)
class StationTerms:
    """The word for a station of the game ("Tisch", "Platz") in the forms the texts need."""

    singular: str
    plural: str
    # with its indefinite article in the accusative and negated: "einen Tisch", "keinen Tisch"
    accusative: str
    none: str

    def numbered(self, n: int) -> str:
        """The default name of the n-th station: "Tisch 3", "Platz 3"."""
        return f"{self.singular} {n}"


@dataclass(frozen=True)
class GameRules:
    label: str
    score: ScoreRule
    station: StationTerms
    # the modes a tournament of this game can have
    modes: tuple[TournamentMode, ...]
    # whether a match can end even (only where the mode does not need a winner of every match)
    draws: bool = False
    max_score: int = 99
    # whether the counts a sensor at the station sees (team a, team b) end the match; None where no sensor can tell
    sensed_end: Callable[[int, int], bool] | None = None


def _beerpong(winner: int, loser: int) -> str | None:
    if loser != 0:
        return "Beim Bierpong hat das unterlegene Team keine Becher mehr übrig."
    if not 1 <= winner <= 10:
        return "Der Sieger hat zwischen 1 und 10 Becher übrig."
    return None


def _football(winner: int, loser: int) -> str | None:
    if winner > 99:
        return "So viele Tore sind nicht möglich."
    if winner <= loser:
        # a knockout match needs a winner: extra time and penalties count into the score
        return "Der Sieger braucht mehr Tore. Trag bei Gleichstand das Ergebnis nach Verlängerung oder Elfmeterschießen ein."
    return None


GAMES: dict[Game, GameRules] = {
    Game.BEERPONG: GameRules(
        label="Bierpong",
        score=_beerpong,
        station=StationTerms(singular="Tisch", plural="Tische", accusative="einen Tisch", none="keinen Tisch"),
        modes=(TournamentMode.SINGLE_ELIMINATION, TournamentMode.ROUND_ROBIN, TournamentMode.GROUPS_KNOCKOUT),
        # the team whose cups are all gone has lost
        sensed_end=lambda a, b: (a == 0) != (b == 0),
    ),
    Game.FOOTBALL: GameRules(
        label="Fußball",
        score=_football,
        station=StationTerms(singular="Platz", plural="Plätze", accusative="einen Platz", none="keinen Platz"),
        modes=(TournamentMode.SINGLE_ELIMINATION, TournamentMode.ROUND_ROBIN, TournamentMode.GROUPS_KNOCKOUT),
        draws=True,
    ),
}


def check_score(game: Game, winner_score: int, loser_score: int) -> None:
    """Raise if the score is not possible in this game (or does not fit the winner)."""
    problem = GAMES[game].score(winner_score, loser_score)
    if problem:
        raise InvalidScoreError(problem)


def check_draw(game: Game, counts_points: bool, score: int) -> None:
    """Raise if this game has no draws or the match needs a winner (or the score is not possible).

    A match that counts points (everybody against everybody, a group) may end even; a knock-out match needs a winner.
    """
    rules = GAMES[game]
    if not rules.draws or not counts_points:
        raise InvalidScoreError("Ein Unentschieden gibt es hier nicht: Wähle den Sieger.")
    if not 0 <= score <= rules.max_score:
        raise InvalidScoreError("So viele Tore sind nicht möglich.")


def sensed_result(game: Game, score_a: int, score_b: int) -> tuple[str, int, int] | None:
    """What the counts of a station's sensor say about the match: ("a" or "b" as winner, score a, score b) once they
    end it with a possible score, else None (still running, a game without sensors, a count that cannot be)."""
    rules = GAMES[game]
    if rules.sensed_end is None or not rules.sensed_end(score_a, score_b) or score_a == score_b:
        return None
    winner, (high, low) = ("a", (score_a, score_b)) if score_a > score_b else ("b", (score_b, score_a))
    if rules.score(high, low):
        return None
    return winner, score_a, score_b


def stations_of(game: Game) -> StationTerms:
    return GAMES[game].station
