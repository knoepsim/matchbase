import math
import secrets
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.games import check_draw, check_score, stations_of
from app.core.exceptions import (
    InvalidWinnerError,
    KnockoutError,
    MatchNotAtStationError,
    MatchNotReadyError,
    NotFoundError,
    ResultConflictError,
    TournamentNotStartedError,
)
from app.models.match import Match
from app.models.result import Result, ResultSource, ResultType
from app.schemas.match import BracketResponse, GroupResponse, MatchResponse, MatchStatus, StandingResponse
from app.schemas.result import ResultCreate
from app.models.tournament import TournamentMode, TournamentTeam
from app.services.bracket_layout import round_one_pairings
from app.services.groups import apply_order, group_letter, knockout_seeds, open_ties, place_label, split_into_groups
from app.services.round_robin import Played, match_days, standings
from app.models.station import Station
from app.services.revision import bump
from app.services.station_planner import PlanMatch, assign_free_stations, certain_next_stations, plan
from app.services.tournament_service import TournamentService
from app.core.database import DbSession


# a team, or the place of a group ("A1") that gets its team when the knock-out starts
Entrant = UUID | str


def _entered(match: Match, slot: str, entrant: Entrant | None) -> Match:
    """Put a team or a place of a group into slot "a" / "b" of a match."""
    if isinstance(entrant, str):
        setattr(match, f"source_{slot}", entrant)
    else:
        setattr(match, f"team_{slot}_id", entrant)
    return match


def _counts_points(tournament, match: Match) -> bool:
    """A match of everybody against everybody or of a group counts points (and so may end even)."""
    return tournament.mode == TournamentMode.ROUND_ROBIN or match.group_number is not None


def group_tables(matches: list[Match], results: dict[UUID, Result]) -> list[GroupResponse]:
    """The table of every group, from its matches."""
    groups: dict[int, set[UUID]] = {}
    for m in matches:
        if m.group_number is not None:
            groups.setdefault(m.group_number, set()).update(t for t in (m.team_a_id, m.team_b_id) if t)
    return [
        GroupResponse(
            group=group,
            standings=_rows(sorted(teams, key=str), [m for m in matches if m.group_number == group], results),
        )
        for group, teams in sorted(groups.items())
    ]


def _knockout_places(groups: list[GroupResponse], order: dict[int, list[UUID]], advance: int) -> dict[str, UUID]:
    """The team of every place of the tree ("A1"): the final order of each group, a tie decided by `order`."""
    places: dict[str, UUID] = {}
    for group in groups:
        ranks = [(row.team_id, row.rank) for row in group.standings]
        given = order.get(group.group)
        if not given and open_ties(ranks, advance):
            raise KnockoutError(f"In Gruppe {group_letter(group.group)} gibt es einen Gleichstand: Lege die Reihenfolge fest.")
        try:
            final = apply_order(ranks, given)
        except ValueError as error:
            raise KnockoutError(str(error)) from None
        places.update({place_label(group.group, rank): team for rank, team in enumerate(final[:advance], start=1)})
    return places


def _rows(team_ids: list[UUID], matches: list[Match], results: dict[UUID, Result]) -> list[StandingResponse]:
    """The table of these teams from these matches (see round_robin.standings)."""
    played = [
        Played(m.team_a_id, m.team_b_id, r.score_a or 0, r.score_b or 0, r.winner_team_id)
        for m in matches
        if (r := results.get(m.id)) is not None and m.team_a_id is not None and m.team_b_id is not None
    ]
    return [
        StandingResponse(
            team_id=row.team_id,
            rank=row.rank,
            played=row.played,
            won=row.won,
            drawn=row.drawn,
            lost=row.lost,
            score_for=row.score_for,
            score_against=row.score_against,
            points=row.points,
        )
        for row in standings(team_ids, played)
    ]


class BracketService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, tournament_id: UUID, team_ids: list[UUID], mode: TournamentMode) -> list[Match]:
        """The matches of a tournament at its start, as its mode wants them."""
        if mode == TournamentMode.ROUND_ROBIN:
            return await self.generate_round_robin(tournament_id, team_ids)
        if mode == TournamentMode.GROUPS_KNOCKOUT:
            return await self.generate_groups_knockout(tournament_id, team_ids)
        return await self.generate_bracket(tournament_id, team_ids)

    async def generate_groups_knockout(self, tournament_id: UUID, team_ids: list[UUID]) -> list[Match]:
        """The groups drawn at random, each with its match days (all groups play day by day at the same time), and the
        knock-out tree with the places of the groups ("A1" against "B2") until the organization starts it."""
        tournament = await TournamentService(self.db).get_tournament(tournament_id)
        shuffled = list(team_ids)
        # Für das Mischen der Teams reicht diese Zufallsverteilung aus und birgt kein Sicherheitsrisiko
        secrets.SystemRandom().shuffle(shuffled)  # NOSONAR
        matches: list[Match] = []
        positions: dict[int, int] = {}
        for group, teams in enumerate(split_into_groups(shuffled, tournament.group_count), start=1):
            for day, pairs in enumerate(match_days(teams), start=1):
                for a, b in pairs:
                    position = positions[day] = positions.get(day, -1) + 1
                    matches.append(
                        Match(tournament_id=tournament_id, round=day, position=position, group_number=group, team_a_id=a, team_b_id=b)
                    )
        seeds = knockout_seeds(tournament.group_count, tournament.advance_per_group)
        knockout = self._build_matches(tournament_id, round_one_pairings(seeds))
        self.db.add_all(matches)
        self.db.add_all(knockout)
        await self.db.flush()
        return matches + knockout

    async def start_knockout(self, tournament_id: UUID, order: dict[int, list[UUID]]) -> None:
        """The organization starts the knock-out stage: every group match has a result, a tie where it matters is
        decided (`order`: the teams of a group in the order the organization gave). The places of the tree get their
        teams, and from now on the group results are fixed."""
        tournament = await TournamentService(self.db).get_tournament(tournament_id, for_update=True)
        if tournament.mode != TournamentMode.GROUPS_KNOCKOUT or not tournament.is_started:
            raise KnockoutError("Dieses Turnier hat keine K.-o.-Runde nach Gruppen.")
        if tournament.knockout_started_at is not None:
            raise KnockoutError("Die K.-o.-Runde läuft schon.")
        matches = list((await self.db.execute(select(Match).where(Match.tournament_id == tournament_id))).scalars())
        results = await self._current_results([m.id for m in matches])
        if any(m.group_number is not None and m.id not in results for m in matches):
            raise KnockoutError("Erst wenn alle Gruppenspiele ein Ergebnis haben, kann die K.-o.-Runde starten.")

        places = _knockout_places(group_tables(matches, results), order, tournament.advance_per_group)
        for match in matches:
            for slot in ("a", "b"):
                source = getattr(match, f"source_{slot}")
                if source is not None:
                    setattr(match, f"team_{slot}_id", places[source])
        tournament.knockout_started_at = datetime.now(UTC)
        await self.db.flush()
        await self.assign_stations(tournament_id)
        await bump(self.db, tournament_id, "bracket", "tournament")

    async def generate_round_robin(self, tournament_id: UUID, team_ids: list[UUID]) -> list[Match]:
        """Everybody against everybody once, match day by match day (see round_robin.match_days); the order of the
        teams is drawn, so who meets whom when is left to chance."""
        shuffled = list(team_ids)
        # Für das Mischen der Teams reicht diese Zufallsverteilung aus und birgt kein Sicherheitsrisiko
        secrets.SystemRandom().shuffle(shuffled)  # NOSONAR
        matches = [
            Match(tournament_id=tournament_id, round=day, position=position, team_a_id=a, team_b_id=b)
            for day, pairs in enumerate(match_days(shuffled), start=1)
            for position, (a, b) in enumerate(pairs)
        ]
        self.db.add_all(matches)
        await self.db.flush()
        return matches

    async def generate_bracket(self, tournament_id: UUID, team_ids: list[UUID]) -> list[Match]:
        """Draw a single-elimination bracket for the given teams.

        - Shuffles the teams randomly
        - Byes (non-power-of-2 team counts) get no match: the team is entered directly into its
          match of the next round; byes are spread evenly over the bracket (see bracket_layout)
        - Creates the full match tree with next_match references
        Called when the tournament starts (see LifecycleService), never on its own.
        """
        shuffled = list(team_ids)
        # Für das Mischen der Teams reicht diese Zufallsverteilung aus und birgt kein Sicherheitsrisiko
        secrets.SystemRandom().shuffle(shuffled)  # NOSONAR

        matches = self._build_matches(tournament_id, round_one_pairings(shuffled))
        # Parents first: next_match_id is a foreign key to matches
        self.db.add_all(matches)
        await self.db.flush()
        return matches


    def _build_matches(self, tournament_id: UUID, pairings: list[tuple[Entrant | None, Entrant | None]]
    ) -> list[Match]:
        """Create the match tree for the given first-round pairings, ordered final first.

        An entrant is a team, or the place of a group ("A1") whose team comes in when the knock-out starts.
        """
        total_rounds = int(math.log2(len(pairings))) + 1

        def first(pos: int, a: Entrant | None, b: Entrant | None) -> Match | None:
            # a pairing with one entrant is a bye: no match
            if a is None or b is None:
                return None
            match = Match(id=uuid.uuid4(), tournament_id=tournament_id, round=1, position=pos)
            return _entered(_entered(match, "a", a), "b", b)

        rounds: dict[int, list[Match | None]] = {1: [first(pos, a, b) for pos, (a, b) in enumerate(pairings)]}
        for round_num in range(2, total_rounds + 1):
            rounds[round_num] = [
                Match(id=uuid.uuid4(), tournament_id=tournament_id, round=round_num, position=pos)
                for pos in range(len(pairings) // 2 ** (round_num - 1))
            ]

        for round_num in range(1, total_rounds):
            for pos, match in enumerate(rounds[round_num]):
                parent = rounds[round_num + 1][pos // 2]
                slot = "a" if pos % 2 == 0 else "b"
                if match is not None:
                    match.next_match_id = parent.id
                    match.next_match_slot = slot
                else:
                    # Bye in round one: the single team (or place) skips the match
                    _entered(parent, slot, pairings[pos][0] or pairings[pos][1])

        return [m for round_num in range(total_rounds, 0, -1) for m in rounds[round_num] if m is not None]


    async def _delete_bracket(self, tournament_id: UUID) -> None:
        """Remove all matches of a tournament (only valid before it has started)."""
        await self.db.execute(
            update(Match).where(Match.tournament_id == tournament_id).values(next_match_id=None)
        )
        await self.db.execute(delete(Match).where(Match.tournament_id == tournament_id))


    async def _advance_team(self, next_match_id: UUID, slot: str | None, team_id: UUID
    ) -> None:
        """Place a team into the specified slot of a match."""
        result = await self.db.execute(select(Match).where(Match.id == next_match_id))
        next_match = result.scalar_one_or_none()
        if next_match is None:
            return

        if slot == "a":
            next_match.team_a_id = team_id
        elif slot == "b":
            next_match.team_b_id = team_id


    async def _get_match(self, match_id: UUID, *, for_update: bool = False) -> Match:
        stmt = select(Match).where(Match.id == match_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        match = result.scalar_one_or_none()
        if match is None:
            raise NotFoundError("Spiel")
        return match


    async def _current_results(self, match_ids: list[UUID]) -> dict[UUID, Result]:
        """The current result per match: its latest event, unless that event is a deletion.

        One query for all matches (the result log is append-only, the last event wins).
        """
        if not match_ids:
            return {}
        rows = await self.db.execute(
            select(Result).where(Result.match_id.in_(match_ids)).order_by(Result.created_at)
        )
        latest = {r.match_id: r for r in rows.scalars()}
        return {match_id: r for match_id, r in latest.items() if r.type != ResultType.DELETED}

    async def _has_active_result(self, match_id: UUID) -> bool:
        """A match is decided if its latest event is not a deletion."""
        return match_id in await self._current_results([match_id])


    async def _record_result(
        self,
        match_id: UUID,
        result_type: ResultType,
        user_id: UUID,
        winner_team_id: UUID | None = None,
        score: tuple[int, int] | None = None,
        source: ResultSource = ResultSource.MANUAL,
    ) -> Result:
        """Append a result event and propagate the winner (or its removal) to the next match.

        Single place for all result rules:
        - the tournament must be running
        - CREATED needs a ready match without active result, MODIFIED/DELETED need an active one
        - the winner must be one of the match's two teams, and the score possible in the game with that winner;
          no winner is a draw, where the game and the mode have draws
        - the next match must not be decided yet
        """
        # Lock the tournament, then the match and its successor (always in this order): concurrent reports cannot
        # pass the checks below at the same time, and the stations are planned by one report after the other
        tournament_id = (await self._get_match(match_id)).tournament_id
        tournament = await TournamentService(self.db).get_tournament(tournament_id, for_update=True)
        match = await self._get_match(match_id, for_update=True)
        if match.next_match_id is not None:
            await self._get_match(match.next_match_id, for_update=True)
        if not tournament.is_started:
            raise TournamentNotStartedError()

        is_active = await self._has_active_result(match_id)
        if result_type == ResultType.CREATED and is_active:
            raise ResultConflictError("Für dieses Spiel gibt es schon ein Ergebnis. Ändere es stattdessen.")
        if result_type != ResultType.CREATED and not is_active:
            raise ResultConflictError("Für dieses Spiel gibt es noch kein Ergebnis.")

        if match.group_number is not None and tournament.knockout_started_at is not None:
            raise ResultConflictError("Die K.-o.-Runde läuft: Die Ergebnisse der Gruppen stehen fest.")

        if result_type != ResultType.DELETED:
            if match.team_a_id is None or match.team_b_id is None:
                raise MatchNotReadyError()
            score_a, score_b = score or (0, 0)
            if winner_team_id is None:
                if score_a != score_b:
                    raise InvalidWinnerError()
                check_draw(tournament.game, _counts_points(tournament, match), score_a)
            else:
                if winner_team_id not in (match.team_a_id, match.team_b_id):
                    raise InvalidWinnerError()
                winner_score, loser_score = (score_a, score_b) if winner_team_id == match.team_a_id else (score_b, score_a)
                check_score(tournament.game, winner_score, loser_score)

        if match.next_match_id is not None and await self._has_active_result(match.next_match_id):
            raise ResultConflictError(
                "Das nächste Spiel hat schon ein Ergebnis. Lösche zuerst dieses Ergebnis, dann kannst du hier etwas ändern."
            )

        entry = Result(
            match_id=match_id,
            type=result_type,
            winner_team_id=winner_team_id,
            score_a=score[0] if score else None,
            score_b=score[1] if score else None,
            source=source,
            reported_by_user_id=user_id,
        )
        self.db.add(entry)

        if match.next_match_id is not None:
            await self._advance_team(match.next_match_id, match.next_match_slot, winner_team_id)
        await self.db.flush()
        # over when every match has a result: in a knock-out that is the final, everybody against everybody the last
        # match day; a result taken back opens it again (a correction does not change the moment it ended)
        decided = await self._current_results(
            list((await self.db.execute(select(Match.id).where(Match.tournament_id == tournament.id))).scalars())
        )
        total = (await self.db.execute(select(func.count()).select_from(Match).where(Match.tournament_id == tournament.id))).scalar_one()
        if len(decided) < total:
            tournament.finished_at = None
        elif tournament.finished_at is None:
            tournament.finished_at = datetime.now(UTC)

        await self.db.flush()
        await self.assign_stations(tournament.id)
        await bump(self.db, tournament.id, "bracket", "tournament")
        return entry

    # -- stations ---------------------------------------------------------------------------------------------

    async def _plan_input(self, tournament_id: UUID) -> tuple[list[Match], list[PlanMatch], list[UUID], dict]:
        matches = list(
            (await self.db.execute(select(Match).where(Match.tournament_id == tournament_id))).scalars().all()
        )
        results = await self._current_results([m.id for m in matches])
        station_ids = list(
            (
                await self.db.execute(
                    select(Station.id)
                    .where(Station.tournament_id == tournament_id)
                    .order_by(Station.position)
                )
            ).scalars()
        )
        feeders: dict[UUID, list[UUID]] = {}
        for m in matches:
            if m.next_match_id is not None:
                feeders.setdefault(m.next_match_id, []).append(m.id)
        planned = [
            PlanMatch(
                id=m.id,
                round=m.round,
                position=m.position,
                feeders=tuple(feeders.get(m.id, ())),
                ready=m.team_a_id is not None and m.team_b_id is not None,
                ready_at=_timestamp(m.ready_at),
                finished=m.id in results,
                finished_at=_timestamp(results[m.id].created_at) if m.id in results else None,
                station=m.station_id,
                playing=m.on_station_at is not None,
                teams=tuple(t for t in (m.team_a_id, m.team_b_id) if t is not None),
            )
            for m in matches
        ]
        return matches, planned, station_ids, results

    async def assign_stations(self, tournament_id: UUID) -> None:
        """Bring the matches to the stations: keep what is being played, give free stations to the next ready matches.

        Runs after the draw, after every result (also corrections) and when stations are added or deleted; the caller
        holds the lock of the tournament, so one planning follows the other. See services/station_planner.py.
        """
        now = datetime.now(UTC)
        matches, _, station_ids, results = await self._plan_input(tournament_id)
        for m in matches:
            ready = m.team_a_id is not None and m.team_b_id is not None
            if not ready:
                # it lost a team (a result was taken back): it waits again, without a station
                m.ready_at = m.station_id = m.on_station_at = None
            elif m.ready_at is None:
                m.ready_at = now
            # a match that is over or lost its station is not at a station (and so not live either)
            if m.id in results or m.station_id not in station_ids:
                m.on_station_at = None
            if m.on_station_at is None:
                m.started_at = None
        await self.db.flush()

        _, planned, _, _ = await self._plan_input(tournament_id)
        by_id = {m.id: m for m in matches}
        for match_id, station_id in assign_free_stations(planned, station_ids).items():
            match = by_id[match_id]
            if match.on_station_at is None:
                match.station_id = station_id
                match.on_station_at = now
        await self.db.flush()


    async def set_started(self, match_id: UUID, started: bool) -> None:
        """Start a match at its station (live), or take the start back. A result can be reported without a start."""
        tournament_id = (await self._get_match(match_id)).tournament_id
        tournament = await TournamentService(self.db).get_tournament(tournament_id, for_update=True)
        match = await self._get_match(match_id, for_update=True)
        if not tournament.is_started:
            raise TournamentNotStartedError()
        if await self._has_active_result(match_id):
            raise ResultConflictError("Das Spiel hat schon ein Ergebnis.")
        if started and match.on_station_at is None:
            raise MatchNotAtStationError(stations_of(tournament.game).none)
        if started and match.started_at is None:
            match.started_at = datetime.now(UTC)
        elif not started:
            match.started_at = None
        await self.db.flush()
        await bump(self.db, tournament.id, "bracket")

    async def report_result(self, match_id: UUID, data: ResultCreate, user_id: UUID) -> Result:
        """Report the first result for a match and advance the winner."""
        return await self._record_result(
            match_id, ResultType.CREATED, user_id, data.winner_team_id, (data.score_a, data.score_b), data.source
        )


    async def modify_result(self, match_id: UUID, data: ResultCreate, user_id: UUID) -> Result:
        """Modify an existing result, updating the winner in the next match."""
        return await self._record_result(
            match_id, ResultType.MODIFIED, user_id, data.winner_team_id, (data.score_a, data.score_b), data.source
        )


    async def delete_result(self, match_id: UUID, user_id: UUID) -> Result:
        """Mark the current result as deleted, removing the winner from the next match."""
        return await self._record_result(match_id, ResultType.DELETED, user_id)


    async def get_bracket(self, tournament_id: UUID) -> BracketResponse:
        """Get the complete bracket tree for a tournament."""
        result = await self.db.execute(
            select(Match)
            .where(Match.tournament_id == tournament_id)
            .order_by(Match.round, Match.position)
        )
        matches = list(result.scalars().all())
        results = await self._current_results([m.id for m in matches])

        # the rounds of the tree (a knock-out), or the match days (everybody against everybody)
        tree = [m for m in matches if m.group_number is None]
        total_rounds = max((m.round for m in tree), default=0)
        names = dict(
            (
                await self.db.execute(
                    select(Station.id, Station.name).where(Station.tournament_id == tournament_id)
                )
            ).all()
        )
        _, planned, station_ids, _ = await self._plan_input(tournament_id)
        queue = {match_id: place for place, match_id in enumerate(plan(planned, station_ids).queue, start=1)}
        upcoming = certain_next_stations(planned, station_ids, datetime.now(UTC).timestamp())
        responses = [
            self._to_response(m, results.get(m.id)).model_copy(
                update={
                    "station_name": names.get(m.station_id),
                    "queue_position": queue.get(m.id),
                    "upcoming_station_id": upcoming.get(m.id),
                    "upcoming_station_name": names.get(upcoming.get(m.id)),
                }
            )
            for m in matches
        ]
        tournament = await TournamentService(self.db).get_tournament(tournament_id)
        groups = group_tables(matches, results) if tournament.mode == TournamentMode.GROUPS_KNOCKOUT else None
        if tournament.mode == TournamentMode.ROUND_ROBIN:
            table = await self.standings(tournament_id, matches, results)
            # the first of the table once everything is played (a shared first place has no single winner)
            leaders = [row for row in table if row.rank == 1]
            champion = leaders[0].team_id if tournament.finished_at and len(leaders) == 1 else None
        else:
            table = None
            final = next((r for r in responses if r.round == total_rounds and r.group is None), None)
            champion = final.winner_team_id if final else None

        return BracketResponse(
            tournament_id=tournament_id,
            mode=tournament.mode,
            total_rounds=total_rounds,
            champion_team_id=champion,
            matches=responses,
            standings=table,
            groups=groups,
            knockout_started=tournament.knockout_started_at is not None,
        )

    async def standings(
        self, tournament_id: UUID, matches: list[Match], results: dict[UUID, Result]
    ) -> list[StandingResponse]:
        """The table of everybody against everybody: every team that plays, also before its first result."""
        team_ids = list(
            (await self.db.execute(select(TournamentTeam.team_id).where(TournamentTeam.tournament_id == tournament_id))).scalars()
        )
        return _rows(team_ids, matches, results)

    @staticmethod
    def _to_response(match: Match, current: Result | None) -> MatchResponse:
        if current is not None:
            status = MatchStatus.FINISHED
        elif match.team_a_id is None or match.team_b_id is None:
            status = MatchStatus.WAITING
        elif match.started_at is not None:
            status = MatchStatus.LIVE
        elif match.on_station_at is not None:
            status = MatchStatus.READY
        else:
            status = MatchStatus.QUEUED
        return MatchResponse.model_validate(match).model_copy(
            update={
                "status": status,
                "winner_team_id": current.winner_team_id if current else None,
                "score_a": current.score_a if current else None,
                "score_b": current.score_b if current else None,
            }
        )



def get_bracket_service(db: DbSession) -> BracketService:
    return BracketService(db)


def _timestamp(value: datetime | None) -> float | None:
    """A comparable number for the planner (naive values from SQLite count as UTC)."""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).timestamp()
