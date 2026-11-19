"""Numbered pages for one learning sheet, one sequence per student.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import LearningSheetCapture, LearningSheetCopy, LearningSheetToken
from services.learning_space.access import get_class_for_staff
from services.learning_space.glasses_contract import parse_sheet_payload, sheet_payload
from services.learning_space.memberships import class_roster_items
from utils.auth.role_constants import ROLE_STUDENT


def _students(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    students: list[dict[str, Any]] = []
    for item in items:
        if item.get("role") != ROLE_STUDENT:
            continue
        user_id = int(item["id"])
        if user_id in seen:
            continue
        seen.add(user_id)
        students.append(item)
    return students


def copy_payload(row: LearningSheetCopy, *, scanned: bool) -> dict[str, Any]:
    """One numbered page, and whether a photo of that page has arrived."""
    return {
        "seq": int(row.seq),
        "student_user_id": row.student_user_id,
        "student_name": row.student_name,
        "class_name": row.class_name,
        "qr_payload": sheet_payload(row.sheet_id, int(row.seq)),
        "scanned": scanned,
    }


async def _owned_token(db: AsyncSession, user: User, qr_payload: str) -> LearningSheetToken:
    sheet_id, _seq = parse_sheet_payload(qr_payload)
    if not sheet_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown sheet")
    token = await db.get(LearningSheetToken, sheet_id)
    if token is None or int(token.owner_user_id) != int(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown sheet")
    return token


async def assign_class_copies(
    db: AsyncSession,
    user: User,
    *,
    qr_payload: str,
    class_id: int,
) -> list[dict[str, Any]]:
    """Replace this sheet's numbered pages with the class roster, in stable order."""
    token = await _owned_token(db, user, qr_payload)
    learning_class = await get_class_for_staff(
        db,
        int(class_id),
        int(user.id),
        allow_archived=True,
        actor=user,
    )
    items = await class_roster_items(
        db,
        int(learning_class.id),
        include_initial_password=False,
        admin_bypass_rls=True,
    )
    students = _students(items)
    if not students:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class has no students")
    await db.execute(delete(LearningSheetCopy).where(LearningSheetCopy.sheet_id == token.id))
    rows: list[LearningSheetCopy] = []
    for seq, student in enumerate(students, start=1):
        row = LearningSheetCopy(
            sheet_id=token.id,
            seq=seq,
            student_user_id=int(student["id"]),
            student_name=str(student.get("name") or "")[:80],
            class_name=str(learning_class.name or "")[:80],
            owner_user_id=int(token.owner_user_id),
            organization_id=int(token.organization_id),
        )
        db.add(row)
        rows.append(row)
    await db.commit()
    return [copy_payload(row, scanned=False) for row in rows]


async def list_sheet_copies(db: AsyncSession, user: User, qr_payload: str) -> list[dict[str, Any]]:
    """Numbered pages for this sheet, with which ones the glasses have photographed."""
    token = await _owned_token(db, user, qr_payload)
    copies = await db.execute(
        select(LearningSheetCopy).where(LearningSheetCopy.sheet_id == token.id).order_by(LearningSheetCopy.seq.asc())
    )
    rows = list(copies.scalars().all())
    scanned_rows = await db.execute(
        select(LearningSheetCapture.copy_seq).where(
            LearningSheetCapture.sheet_id == token.id,
            LearningSheetCapture.copy_seq.is_not(None),
        )
    )
    scanned = {int(seq) for seq in scanned_rows.scalars().all() if seq is not None}
    return [copy_payload(row, scanned=int(row.seq) in scanned) for row in rows]
