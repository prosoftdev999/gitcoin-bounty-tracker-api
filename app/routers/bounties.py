import csv
import io
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Bounty, User
from app.schemas import (
    BountyCreate,
    BountyResponse,
    BountyUpdate,
    PaginatedBounties,
    PaginationMeta,
    StatsResponse,
)

router = APIRouter(prefix="/bounties", tags=["Bounties"])


def get_owned_bounty(
    bounty_id: int,
    current_user: User,
    db: Session,
) -> Bounty:
    bounty = db.scalar(
        select(Bounty).where(
            Bounty.id == bounty_id,
            Bounty.owner_id == current_user.id,
        )
    )
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    return bounty


@router.post(
    "",
    response_model=BountyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bounty(
    payload: BountyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bounty = Bounty(
        owner_id=current_user.id,
        **payload.model_dump(mode="json"),
    )
    db.add(bounty)
    db.commit()
    db.refresh(bounty)
    return bounty


@router.get("", response_model=PaginatedBounties)
def list_bounties(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    bounty_status: str | None = Query(default=None, alias="status"),
    platform: str | None = Query(default=None, max_length=80),
    min_reward: int | None = Query(default=None, ge=0),
    max_reward: int | None = Query(default=None, ge=0),
    deadline_before: datetime | None = None,
    deadline_after: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [Bounty.owner_id == current_user.id]

    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Bounty.title.ilike(pattern),
                Bounty.skills.ilike(pattern),
                Bounty.notes.ilike(pattern),
            )
        )

    if bounty_status:
        filters.append(Bounty.status == bounty_status.strip().lower())

    if platform:
        filters.append(Bounty.platform.ilike(platform.strip()))

    if min_reward is not None:
        filters.append(Bounty.reward_usd >= min_reward)

    if max_reward is not None:
        filters.append(Bounty.reward_usd <= max_reward)

    if deadline_before:
        filters.append(Bounty.deadline <= deadline_before)

    if deadline_after:
        filters.append(Bounty.deadline >= deadline_after)

    total = db.scalar(
        select(func.count(Bounty.id)).where(*filters)
    ) or 0

    statement = (
        select(Bounty)
        .where(*filters)
        .order_by(Bounty.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.scalars(statement).all())
    total_pages = math.ceil(total / page_size) if total else 0

    return PaginatedBounties(
        items=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/stats", response_model=StatsResponse)
def bounty_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(
            Bounty.status,
            func.count(Bounty.id),
            func.coalesce(func.sum(Bounty.reward_usd), 0),
        )
        .where(Bounty.owner_id == current_user.id)
        .group_by(Bounty.status)
    ).all()

    by_status = {status_name: count for status_name, count, _ in rows}
    total_bounties = sum(count for _, count, _ in rows)
    total_reward_usd = sum(int(reward) for _, _, reward in rows)
    won_reward_usd = sum(
        int(reward)
        for status_name, _, reward in rows
        if status_name == "won"
    )

    return StatsResponse(
        total_bounties=total_bounties,
        total_reward_usd=total_reward_usd,
        won_reward_usd=won_reward_usd,
        by_status=by_status,
    )


@router.get("/export.csv")
def export_bounties_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bounties = list(
        db.scalars(
            select(Bounty)
            .where(Bounty.owner_id == current_user.id)
            .order_by(Bounty.created_at.desc())
        ).all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "title",
            "platform",
            "reward_usd",
            "status",
            "url",
            "skills",
            "deadline",
            "created_at",
        ]
    )

    for bounty in bounties:
        writer.writerow(
            [
                bounty.id,
                bounty.title,
                bounty.platform,
                bounty.reward_usd,
                bounty.status,
                bounty.url or "",
                bounty.skills,
                bounty.deadline.isoformat() if bounty.deadline else "",
                bounty.created_at.isoformat(),
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="gitcoin-bounties.csv"'
            )
        },
    )


@router.get("/{bounty_id}", response_model=BountyResponse)
def get_bounty(
    bounty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_bounty(bounty_id, current_user, db)


@router.patch("/{bounty_id}", response_model=BountyResponse)
def update_bounty(
    bounty_id: int,
    payload: BountyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bounty = get_owned_bounty(bounty_id, current_user, db)

    for field, value in payload.model_dump(
        exclude_unset=True,
        mode="json",
    ).items():
        setattr(bounty, field, value)

    db.commit()
    db.refresh(bounty)
    return bounty


@router.delete("/{bounty_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bounty(
    bounty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bounty = get_owned_bounty(bounty_id, current_user, db)
    db.delete(bounty)
    db.commit()
