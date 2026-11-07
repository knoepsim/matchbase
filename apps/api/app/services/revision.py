"""Every change a viewer of a tournament can see raises its revision and says which part changed.

`bump` is called by the services that write. The signal goes out after the transaction was committed
(never before, or the browser would load the old state) and not at all if it was rolled back.
"""
from typing import Literal
from uuid import UUID

from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.util import identity_key

from app.core.events import bus
from app.models.tournament import Tournament, TournamentTeam

# "sensors": what the table controllers count (only on a Tournament Core, docs/edge)
Scope = Literal["tournament", "teams", "bracket", "roles", "sensors"]

_PENDING = "revision_events"


async def bump(db: AsyncSession, tournament_id: UUID, *scopes: Scope) -> int:
    """Raise the revision of a tournament (atomically) and remember which parts changed for the signal."""
    # No flush on the way: pending changes of the caller stay pending (a flush would expire what the response reads).
    # A plain table update: the ORM would expire the loaded tournament as well.
    with db.sync_session.no_autoflush:
        await db.execute(
            update(Tournament.__table__).where(Tournament.id == tournament_id).values(revision=Tournament.revision + 1)
        )
        revision = (await db.execute(select(Tournament.revision).where(Tournament.id == tournament_id))).scalar_one()
    loaded = db.sync_session.identity_map.get(identity_key(Tournament, tournament_id))
    if loaded is not None:
        set_committed_value(loaded, "revision", revision)
    pending = db.sync_session.info.setdefault(_PENDING, {})
    entry = pending.setdefault(tournament_id, {"revision": revision, "changed": set()})
    entry["revision"] = revision
    entry["changed"].update(scopes)
    return revision


async def bump_for_team(db: AsyncSession, team_id: UUID, *scopes: Scope) -> None:
    """A team changed (name, players): every tournament it plays in shows something different."""
    rows = await db.execute(select(TournamentTeam.tournament_id).where(TournamentTeam.team_id == team_id))
    for tournament_id in rows.scalars().all():
        await bump(db, tournament_id, *scopes)


@event.listens_for(Session, "after_commit")
def _publish_after_commit(session: Session) -> None:
    for tournament_id, entry in session.info.pop(_PENDING, {}).items():
        bus.publish(
            tournament_id, "revision", {"revision": entry["revision"], "changed": sorted(entry["changed"])}
        )


@event.listens_for(Session, "after_rollback")
def _drop_after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)
