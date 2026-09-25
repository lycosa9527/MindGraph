"""Learning Space HTTP routes (admin / teacher / student).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_DRAFT,
    CLASS_STATUS_ACTIVE,
    CLASS_STATUS_ARCHIVED,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningClass,
    LearningPilotTeacher,
    LearningSubmission,
)
from routers.auth.dependencies import (
    get_async_db_with_request_rls,
    get_current_user,
    require_panel_capability,
)
from routers.features.learning_space.schemas import (
    AccountImportRequest,
    AssignmentCreate,
    ClassCreate,
    ClassUpdate,
    DraftDiagramBindRequest,
    ExtendDueRequest,
    PilotTeacherCreate,
    StudentChangePasswordRequest,
    StudentImportRequest,
    SubmissionReviewRequest,
)
from routers.features.learning_space.deps import get_learning_space_db
from services.learning_space.access import (
    get_class_for_publisher,
    get_class_for_staff,
    get_enabled_pilot,
    require_class_learner,
    require_student,
    require_student_password_ok,
    resolve_assignment_viewer,
)
from services.learning_space.admin_teachers import (
    assert_teacher_eligible_for_pilot,
    organization_display_map,
    search_teachers_for_pilot,
    user_display_map,
)
from services.learning_space.memberships import (
    MEMBERSHIP_ROLE_ASSISTANT,
    MEMBERSHIP_ROLE_LEARNER,
    assistants_by_class,
    class_activity_stats,
    class_ids_for_membership_role,
    class_roster_items,
    import_existing_accounts,
    learner_class_ids,
    preview_existing_accounts,
    replace_class_assistants,
)
from services.learning_space.assignments import (
    assignment_public_dict,
    bind_draft_diagram,
    delete_assignment,
    enrich_assignment_dict,
    enrich_submission_dict,
    get_assignment,
    get_or_create_submission,
    load_template_preview,
    return_submission,
    save_submission_review,
    submission_public_dict,
    submit_assignment,
)
from services.learning_space.class_codes import (
    class_code_in_use_error,
    create_class_with_unique_code,
    rotate_class_code,
)
from services.learning_space.image_storage import (
    delete_stored_images_sync,
    persist_instruction_images_sync,
    ref_for_key,
    stored_image_keys,
)
from services.learning_space.passwords import (
    merge_ai_permissions,
)
from services.learning_space.students import (
    classroom_student_ids,
    count_class_students,
    import_students,
    kick_classroom_student_sessions,
    preview_student_names,
    reset_student_password,
)
from services.auth.password_security import invalidate_user_cache_after_password_write
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth.admin_panel_permissions import (
    CAP_TAB_LEARNING_SPACE_EDIT,
    CAP_TAB_LEARNING_SPACE_VIEW,
    can_manage_learning_space_classes,
)
from utils.auth.admin_scope import AdminScope
from utils.auth.password import hash_password
from utils.auth.role_constants import ROLE_STUDENT
from utils.auth.roles import get_user_role, is_student
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

router = APIRouter()

_require_ls_view = require_panel_capability(CAP_TAB_LEARNING_SPACE_VIEW)
_require_ls_edit = require_panel_capability(CAP_TAB_LEARNING_SPACE_EDIT)


# ---------------------------------------------------------------------------
# Admin: pilot teachers
# ---------------------------------------------------------------------------


@router.get("/admin/teachers/search")
async def admin_search_teachers(
    q: str = Query("", max_length=100),
    org_id: int | None = Query(
        None,
        description="Filter by organization (not AdminScope organization_id)",
    ),
    limit: int = Query(50, ge=1, le=200),
    _scope: AdminScope = Depends(_require_ls_view),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Search teachers by name/phone/email for Learning Space pilot onboarding."""
    items = await search_teachers_for_pilot(
        db,
        query=q,
        organization_id=org_id,
        limit=limit,
    )
    return {"items": items}


@router.get("/admin/pilots")
async def list_pilots(
    _scope: AdminScope = Depends(_require_ls_view),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """List all pilot teacher grants with class counts."""
    result = await db.execute(select(LearningPilotTeacher).order_by(LearningPilotTeacher.id.desc()))
    rows = list(result.scalars().all())
    teacher_ids = {int(p.teacher_user_id) for p in rows}
    org_ids = {int(p.organization_id) for p in rows}
    names = await user_display_map(teacher_ids)
    org_names = await organization_display_map(org_ids)
    class_counts: dict[int, int] = {}
    if teacher_ids:
        count_result = await db.execute(
            select(LearningClass.teacher_user_id, func.count(LearningClass.id))
            .where(LearningClass.teacher_user_id.in_(tuple(teacher_ids)))
            .group_by(LearningClass.teacher_user_id)
        )
        class_counts = {int(uid): int(cnt) for uid, cnt in count_result.all()}
    return {
        "items": [
            {
                "id": p.id,
                "teacher_user_id": p.teacher_user_id,
                "teacher_name": names.get(int(p.teacher_user_id), ""),
                "organization_id": p.organization_id,
                "organization_name": org_names.get(int(p.organization_id), ""),
                "enabled": p.enabled,
                "class_count": class_counts.get(int(p.teacher_user_id), 0),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ]
    }


@router.post("/admin/pilots", status_code=201)
async def create_pilot(
    body: PilotTeacherCreate,
    scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Grant Learning Space to a teacher."""
    teacher = await db.get(User, body.teacher_user_id)
    if teacher is None:
        raise HTTPException(status_code=404, detail="Teacher not found")
    try:
        assert_teacher_eligible_for_pilot(teacher, body.organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = await db.execute(
        select(LearningPilotTeacher).where(LearningPilotTeacher.teacher_user_id == body.teacher_user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already a pilot teacher")
    pilot = LearningPilotTeacher(
        teacher_user_id=body.teacher_user_id,
        organization_id=body.organization_id,
        enabled=True,
        created_by=int(scope.actor.id),
    )
    db.add(pilot)
    try:
        await db.commit()
        await db.refresh(pilot)
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(
            "[LearningSpace] Pilot grant conflict teacher=%s actor=%s",
            body.teacher_user_id,
            scope.actor.id,
        )
        raise HTTPException(status_code=400, detail="Already a pilot teacher") from exc
    logger.info(
        "[LearningSpace] Pilot granted id=%s teacher=%s org=%s actor=%s",
        pilot.id,
        pilot.teacher_user_id,
        pilot.organization_id,
        scope.actor.id,
    )
    return {"id": pilot.id, "teacher_user_id": pilot.teacher_user_id, "enabled": pilot.enabled}


@router.patch("/admin/pilots/{pilot_id}")
async def patch_pilot(
    pilot_id: int,
    enabled: bool,
    scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Enable or disable a pilot grant."""
    pilot = await db.get(LearningPilotTeacher, pilot_id)
    if pilot is None:
        raise HTTPException(status_code=404, detail="Pilot not found")
    pilot.enabled = enabled
    await db.commit()
    logger.info(
        "[LearningSpace] Pilot updated id=%s teacher=%s enabled=%s actor=%s",
        pilot.id,
        pilot.teacher_user_id,
        enabled,
        scope.actor.id,
    )
    return {"id": pilot.id, "enabled": pilot.enabled}


@router.delete("/admin/pilots/{pilot_id}")
@router.post("/admin/pilots/{pilot_id}/delete")
async def delete_pilot(
    pilot_id: int,
    scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Remove a pilot grant so the teacher can be re-added later."""
    pilot = await db.get(LearningPilotTeacher, pilot_id)
    if pilot is None:
        raise HTTPException(status_code=404, detail="Pilot not found")
    teacher_user_id = int(pilot.teacher_user_id)
    await db.delete(pilot)
    await db.commit()
    logger.info(
        "[LearningSpace] Pilot removed id=%s teacher=%s actor=%s",
        pilot_id,
        teacher_user_id,
        scope.actor.id,
    )
    return {"ok": True, "id": pilot_id}


# ---------------------------------------------------------------------------
# Admin: classes + import
# ---------------------------------------------------------------------------


@router.get("/admin/classes")
async def admin_list_classes(
    _scope: AdminScope = Depends(_require_ls_view),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """List all learning classes."""
    result = await db.execute(select(LearningClass).order_by(LearningClass.id.desc()))
    classes = list(result.scalars().all())
    teacher_ids = {int(cls.teacher_user_id) for cls in classes}
    org_ids = {int(cls.organization_id) for cls in classes}
    names = await user_display_map(teacher_ids)
    org_names = await organization_display_map(org_ids)
    class_ids = [int(cls.id) for cls in classes]
    stats = await class_activity_stats(db, class_ids)
    assistants = await assistants_by_class(db, class_ids)
    items = []
    for cls in classes:
        activity = stats.get(int(cls.id), {"assignment_count": 0, "submission_count": 0})
        items.append(
            {
                "id": cls.id,
                "name": cls.name,
                "class_code": cls.class_code,
                "teacher_user_id": cls.teacher_user_id,
                "teacher_name": names.get(int(cls.teacher_user_id), ""),
                "organization_id": cls.organization_id,
                "organization_name": org_names.get(int(cls.organization_id), ""),
                "status": cls.status,
                "max_students": cls.max_students,
                "student_count": await count_class_students(db, cls.id),
                "assignment_count": activity["assignment_count"],
                "submission_count": activity["submission_count"],
                "assistants": assistants.get(int(cls.id), []),
            }
        )
    return {"items": items}


@router.post("/admin/classes", status_code=201)
async def admin_create_class(
    body: ClassCreate,
    _scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Create a class for a pilot teacher."""
    pilot = await get_enabled_pilot(db, body.teacher_user_id)
    if pilot is None:
        raise HTTPException(status_code=400, detail="Teacher is not an enabled pilot")
    cls = await create_class_with_unique_code(
        db,
        name=body.name.strip(),
        teacher_user_id=body.teacher_user_id,
        organization_id=int(pilot.organization_id),
        class_status=CLASS_STATUS_ACTIVE,
        max_students=body.max_students,
    )
    return {
        "id": cls.id,
        "name": cls.name,
        "class_code": cls.class_code,
        "teacher_user_id": cls.teacher_user_id,
    }


@router.patch("/admin/classes/{class_id}")
async def admin_patch_class(
    class_id: int,
    body: ClassUpdate,
    scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Update class metadata or archive."""
    cls = await db.get(LearningClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if body.name is not None:
        cls.name = body.name.strip()
    if body.max_students is not None:
        cls.max_students = body.max_students
    if body.class_code is not None:
        cls.class_code = body.class_code
    if body.status is not None:
        if body.status not in (CLASS_STATUS_ACTIVE, CLASS_STATUS_ARCHIVED):
            raise HTTPException(status_code=400, detail="Invalid status")
        cls.status = body.status
    kick_ids: list[int] = []
    if body.status == CLASS_STATUS_ARCHIVED:
        kick_ids = await classroom_student_ids(db, class_id)
    try:
        if body.assistant_user_ids is not None:
            await replace_class_assistants(db, cls, body.assistant_user_ids)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(
            "[LearningSpace] Class update conflict id=%s actor=%s",
            class_id,
            scope.actor.id,
        )
        if body.class_code is not None:
            raise class_code_in_use_error() from exc
        raise HTTPException(status_code=400, detail="Could not update class") from exc
    await kick_classroom_student_sessions(kick_ids)
    logger.info(
        "[LearningSpace] Class updated id=%s status=%s kicked=%s actor=%s",
        cls.id,
        cls.status,
        len(kick_ids),
        scope.actor.id,
    )
    return {"id": cls.id, "name": cls.name, "status": cls.status, "class_code": cls.class_code}


@router.post("/admin/classes/{class_id}/rotate-code")
async def admin_rotate_code(
    class_id: int,
    _scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Rotate class join code."""
    cls = await rotate_class_code(db, class_id)
    return {"id": cls.id, "class_code": cls.class_code}


@router.post("/admin/classes/{class_id}/import/preview")
async def admin_import_preview(
    class_id: int,
    body: StudentImportRequest,
    _scope: AdminScope = Depends(_require_ls_view),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Preview student import passwords."""
    cls = await db.get(LearningClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    rows = preview_student_names(body.names)
    return {
        "items": [{"name": r.name, "initial_password": r.initial_password, "ok": r.ok, "error": r.error} for r in rows]
    }


@router.post("/admin/classes/{class_id}/import")
async def admin_import_students(
    class_id: int,
    body: StudentImportRequest,
    _scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Import students; returns created passwords once."""
    cls = await db.get(LearningClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if cls.status != CLASS_STATUS_ACTIVE:
        raise HTTPException(status_code=400, detail="Class is archived")
    result = await import_students(db, cls, body.names)
    return {"created": result.created, "failed": result.failed}


@router.post("/admin/classes/{class_id}/import-accounts/preview")
@router.post("/admin/classes/{class_id}/import/accounts/preview")
async def admin_import_accounts_preview(
    class_id: int,
    body: AccountImportRequest,
    _scope: AdminScope = Depends(_require_ls_view),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Preview existing-account import by phone (role is not changed)."""
    cls = await db.get(LearningClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    rows = await preview_existing_accounts(db, cls, body.phones)
    return {
        "items": [
            {
                "phone": r.phone,
                "ok": r.ok,
                "error": r.error,
                "user_id": r.user_id,
                "name": r.name,
                "organization_name": r.organization_name,
                "role": r.role,
            }
            for r in rows
        ]
    }


@router.post("/admin/classes/{class_id}/import-accounts")
@router.post("/admin/classes/{class_id}/import-accounts/run")
@router.post("/admin/classes/{class_id}/import/accounts")
async def admin_import_accounts(
    class_id: int,
    body: AccountImportRequest,
    _scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Enroll existing accounts as learners; keeps users.role unchanged."""
    cls = await db.get(LearningClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if cls.status != CLASS_STATUS_ACTIVE:
        raise HTTPException(status_code=400, detail="Class is archived")
    return await import_existing_accounts(db, cls, body.phones)


@router.get("/admin/classes/{class_id}/students")
async def admin_list_students(
    class_id: int,
    _scope: AdminScope = Depends(_require_ls_view),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """List students in a class."""
    cls = await db.get(LearningClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return {"items": await class_roster_items(db, class_id)}


@router.post("/admin/students/{student_id}/reset-password")
async def admin_reset_password(
    student_id: int,
    _scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Reset student password (shows plaintext once)."""
    student = await db.get(User, student_id)
    if student is None or student.role != ROLE_STUDENT or not student.learning_class_id:
        raise HTTPException(status_code=404, detail="Student not found")
    plain = await reset_student_password(db, student)
    return {"student_id": student.id, "name": student.name, "initial_password": plain}


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------


@router.get("/teacher/classes")
async def teacher_list_classes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Classes owned by an enabled pilot, plus classes they assist."""
    owned: list[LearningClass] = []
    is_pilot = await get_enabled_pilot(db, int(current_user.id)) is not None
    if is_pilot:
        owned_result = await db.execute(
            select(LearningClass)
            .where(LearningClass.teacher_user_id == current_user.id)
            .order_by(LearningClass.id.desc())
        )
        owned = list(owned_result.scalars().all())
    assisted_ids = await class_ids_for_membership_role(db, int(current_user.id), MEMBERSHIP_ROLE_ASSISTANT)
    assisted: list[LearningClass] = []
    if assisted_ids:
        assisted_result = await db.execute(
            select(LearningClass).where(LearningClass.id.in_(tuple(assisted_ids))).order_by(LearningClass.id.desc())
        )
        assisted = list(assisted_result.scalars().all())
    seen: set[int] = set()
    classes: list[LearningClass] = []
    for cls in owned + assisted:
        if int(cls.id) in seen:
            continue
        seen.add(int(cls.id))
        classes.append(cls)
    return {
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "class_code": c.class_code,
                "status": c.status,
                "student_count": await count_class_students(db, c.id),
                "can_publish": is_pilot and int(c.teacher_user_id) == int(current_user.id),
            }
            for c in classes
        ]
    }


@router.get("/teacher/classes/{class_id}/students")
async def teacher_list_students(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """List students and enrolled members in the class."""
    learning_class = await get_class_for_staff(db, class_id, int(current_user.id), allow_archived=True)
    include_passwords = (
        int(learning_class.teacher_user_id) == int(current_user.id)
        and await get_enabled_pilot(db, int(current_user.id)) is not None
    )
    return {"items": await class_roster_items(db, class_id, include_initial_password=include_passwords)}


@router.post("/teacher/students/{student_id}/reset-password")
async def teacher_reset_password(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Teacher resets a student in their class."""
    student = await db.get(User, student_id)
    if student is None or student.role != ROLE_STUDENT or not student.learning_class_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await get_class_for_publisher(db, int(student.learning_class_id), current_user, allow_archived=True)
    plain = await reset_student_password(db, student)
    return {"student_id": student.id, "name": student.name, "initial_password": plain}


@router.post("/teacher/assignments", status_code=201)
async def teacher_create_assignment(
    body: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Create homework from a teacher-owned template diagram."""
    learning_class = await get_class_for_publisher(db, body.class_id, current_user)
    cache = get_diagram_cache()
    try:
        template = await cache.get_diagram(int(current_user.id), body.template_diagram_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Template load failed class=%s teacher=%s: %s",
            body.class_id,
            current_user.id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Diagram service unavailable",
        ) from exc
    if not template:
        logger.warning(
            "[LearningSpace] Template diagram missing class=%s teacher=%s diagram=%s",
            body.class_id,
            current_user.id,
            body.template_diagram_id,
        )
        raise HTTPException(status_code=400, detail="Template diagram not found")
    try:
        stored_images = await asyncio.to_thread(
            persist_instruction_images_sync,
            [u.strip() for u in body.instruction_images if u and u.strip()][:6],
            owner_id=int(current_user.id),
        )
    except ValueError as exc:
        logger.warning(
            "[LearningSpace] Instruction images persist failed class=%s teacher=%s: %s",
            body.class_id,
            current_user.id,
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    assignment = LearningAssignment(
        class_id=body.class_id,
        title=body.title.strip(),
        instructions=body.instructions or "",
        template_diagram_id=body.template_diagram_id,
        due_at=body.due_at,
        ai_permissions=merge_ai_permissions(body.ai_permissions),
        instruction_images=stored_images,
        organization_id=int(learning_class.organization_id),
        created_by=int(current_user.id),
        status=body.status,
    )
    db.add(assignment)
    try:
        await db.commit()
        await db.refresh(assignment)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        incoming = {item.strip() for item in body.instruction_images if item and item.strip()}
        orphans = [
            key for key in stored_image_keys(stored_images) if ref_for_key(key) not in incoming and key not in incoming
        ]
        await asyncio.to_thread(delete_stored_images_sync, orphans)
        logger.error(
            "[LearningSpace] Create assignment failed class=%s teacher=%s: %s",
            body.class_id,
            current_user.id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to create assignment") from exc
    logger.info(
        "[LearningSpace] Assignment created id=%s class=%s teacher=%s status=%s",
        assignment.id,
        assignment.class_id,
        current_user.id,
        assignment.status,
    )
    return await enrich_assignment_dict(db, assignment)


@router.delete("/teacher/assignments/{assignment_id}")
@router.post("/teacher/assignments/{assignment_id}/delete")
async def teacher_delete_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Delete a published or draft assignment (and cascaded submissions)."""
    assignment = await get_assignment(db, assignment_id)
    await get_class_for_publisher(db, assignment.class_id, current_user, allow_archived=True)
    await delete_assignment(db, assignment)
    return {"ok": True, "id": assignment_id}


@router.get("/teacher/classes/{class_id}/assignments")
async def teacher_list_assignments(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """List assignments for a class."""
    await get_class_for_staff(db, class_id, int(current_user.id), allow_archived=True)
    result = await db.execute(
        select(LearningAssignment).where(LearningAssignment.class_id == class_id).order_by(LearningAssignment.id.desc())
    )
    items = []
    for assignment in result.scalars().all():
        items.append(await enrich_assignment_dict(db, assignment))
    return {"items": items}


@router.get("/teacher/assignments/{assignment_id}/submissions")
async def teacher_list_submissions(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Submission board for an assignment."""
    assignment = await get_assignment(db, assignment_id)
    await get_class_for_staff(db, assignment.class_id, int(current_user.id), allow_archived=True)
    result = await db.execute(select(LearningSubmission).where(LearningSubmission.assignment_id == assignment_id))
    subs = list(result.scalars().all())
    items = []
    for submission in subs:
        items.append(await enrich_submission_dict(db, submission))
    return {"items": items}


@router.post("/teacher/submissions/{submission_id}/return")
async def teacher_return_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Return submission for revision."""
    submission = await db.get(LearningSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = await get_assignment(db, submission.assignment_id)
    await get_class_for_staff(db, assignment.class_id, int(current_user.id), allow_archived=True)
    updated = await return_submission(db, submission)
    return submission_public_dict(updated)


@router.post("/teacher/submissions/{submission_id}/extend")
async def teacher_extend_due(
    submission_id: int,
    body: ExtendDueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Per-student deadline extension."""
    submission = await db.get(LearningSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = await get_assignment(db, submission.assignment_id)
    await get_class_for_staff(db, assignment.class_id, int(current_user.id), allow_archived=True)
    submission.due_at_override = body.due_at
    try:
        await db.commit()
        await db.refresh(submission)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Extend due failed submission=%s actor=%s: %s",
            submission_id,
            current_user.id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to extend due date") from exc
    logger.info(
        "[LearningSpace] Extended due submission=%s assignment=%s actor=%s",
        submission.id,
        assignment.id,
        current_user.id,
    )
    return submission_public_dict(submission)


@router.post("/teacher/submissions/{submission_id}/review")
async def teacher_save_review(
    submission_id: int,
    body: SubmissionReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Save rubric / comment for a student submission."""
    submission = await db.get(LearningSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = await get_assignment(db, submission.assignment_id)
    await get_class_for_staff(db, assignment.class_id, int(current_user.id), allow_archived=True)
    updated = await save_submission_review(
        db,
        submission,
        scores=body.scores,
        comment=body.comment,
        liked=body.liked,
        pinned=body.pinned,
    )
    return await enrich_submission_dict(db, updated, include_preview=True, assignment_title=assignment.title)


@router.get("/submissions/{submission_id}/preview")
async def submission_preview(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Preview a submitted work (teacher of class, or classmate student)."""
    submission = await db.get(LearningSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = await get_assignment(db, submission.assignment_id)
    viewer = await resolve_assignment_viewer(db, current_user, assignment)
    if viewer == "learner" and submission.status != SUBMISSION_STATUS_SUBMITTED:
        if int(submission.student_user_id) != int(current_user.id):
            raise HTTPException(status_code=403, detail="Not visible")
    payload = await enrich_submission_dict(
        db,
        submission,
        include_preview=True,
        assignment_title=assignment.title,
    )
    logger.info(
        "[LearningSpace] Opened shared work submission=%s assignment=%s author=%s viewer=%s role=%s",
        submission.id,
        assignment.id,
        submission.student_user_id,
        current_user.id,
        viewer,
    )
    return payload


@router.get("/assignments/{assignment_id}/template-preview")
async def assignment_template_preview(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Preview the teacher template diagram for requirements / attachments."""
    assignment = await get_assignment(db, assignment_id)
    await resolve_assignment_viewer(db, current_user, assignment)
    return await load_template_preview(assignment)


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------


@router.get("/student/assignments")
async def student_list_assignments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Assignments for classroom students and enrolled learners."""
    class_ids = await learner_class_ids(db, current_user)
    if is_student(current_user):
        require_student_password_ok(current_user)
    elif not class_ids:
        raise HTTPException(status_code=403, detail="Students only")
    if not class_ids:
        return {"items": []}
    result = await db.execute(
        select(LearningAssignment)
        .where(
            LearningAssignment.class_id.in_(tuple(class_ids)),
            LearningAssignment.status != ASSIGNMENT_STATUS_DRAFT,
        )
        .order_by(LearningAssignment.id.desc())
    )
    assignments = result.scalars().all()
    items = []
    for assignment in assignments:
        sub_result = await db.execute(
            select(LearningSubmission).where(
                LearningSubmission.assignment_id == assignment.id,
                LearningSubmission.student_user_id == current_user.id,
            )
        )
        submission = sub_result.scalar_one_or_none()
        items.append(
            {
                **(await enrich_assignment_dict(db, assignment)),
                "submission": (await enrich_submission_dict(db, submission) if submission else None),
            }
        )
    return {"items": items}


@router.get("/student/class-wall")
async def student_class_wall(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Class work wall: all submitted classmate works (with teacher reviews)."""
    class_ids = await learner_class_ids(db, current_user)
    if is_student(current_user):
        require_student_password_ok(current_user)
    elif not class_ids:
        raise HTTPException(status_code=403, detail="Students only")
    if not class_ids:
        return {"items": []}
    result = await db.execute(
        select(LearningSubmission, LearningAssignment)
        .join(LearningAssignment, LearningAssignment.id == LearningSubmission.assignment_id)
        .where(
            LearningAssignment.class_id.in_(tuple(class_ids)),
            LearningSubmission.status == SUBMISSION_STATUS_SUBMITTED,
        )
        .order_by(
            LearningSubmission.review_pinned.desc(),
            LearningSubmission.submitted_at.desc().nullslast(),
            LearningSubmission.id.desc(),
        )
    )
    items = []
    for submission, assignment in result.all():
        items.append(
            await enrich_submission_dict(
                db,
                submission,
                include_preview=False,
                assignment_title=assignment.title,
            )
        )
    return {"items": items}


@router.post("/student/assignments/{assignment_id}/open")
async def student_open_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Open or create the student diagram for an assignment."""
    assignment = await get_assignment(db, assignment_id)
    await require_class_learner(db, current_user, int(assignment.class_id))
    submission = await get_or_create_submission(
        db,
        assignment,
        current_user,
        organization_id=getattr(current_user, "organization_id", None),
    )
    return {
        "assignment": assignment_public_dict(assignment),
        "submission": submission_public_dict(submission),
    }


@router.post("/student/assignments/{assignment_id}/draft")
async def student_bind_draft_diagram(
    assignment_id: int,
    body: DraftDiagramBindRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Keep homework pointed at the diagram the student just saved."""
    assignment = await get_assignment(db, assignment_id)
    await require_class_learner(db, current_user, int(assignment.class_id))
    submission = await bind_draft_diagram(
        db,
        assignment,
        current_user,
        body.diagram_id,
    )
    return submission_public_dict(submission)


@router.post("/student/assignments/{assignment_id}/submit")
async def student_submit_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Submit homework snapshot."""
    assignment = await get_assignment(db, assignment_id)
    await require_class_learner(db, current_user, int(assignment.class_id))
    submission = await submit_assignment(db, assignment, current_user)
    return submission_public_dict(submission)


@router.post("/student/change-password")
async def student_change_password(
    body: StudentChangePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    """Clear must_change_password after setting a new password."""
    require_student(current_user)
    async with system_rls_session() as db:
        user = await db.get(User, current_user.id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.password_hash = hash_password(body.new_password)
        user.must_change_password = False
        user.failed_login_attempts = 0
        user.locked_until = None
        try:
            await db.commit()
            await db.refresh(user)
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.error("[LearningSpace] Student password change failed user=%s: %s", current_user.id, exc)
            raise HTTPException(status_code=500, detail="Failed to change password") from exc
        await invalidate_user_cache_after_password_write(user, "Learning Space student password")
    logger.info("[LearningSpace] Student password changed user=%s", current_user.id)
    return {"ok": True}


@router.get("/me/context")
async def learning_space_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Role context for Learning Space UI."""
    learner_ids = await class_ids_for_membership_role(db, int(current_user.id), MEMBERSHIP_ROLE_LEARNER)
    assistant_ids = await class_ids_for_membership_role(db, int(current_user.id), MEMBERSHIP_ROLE_ASSISTANT)
    if is_student(current_user):
        cls = None
        if current_user.learning_class_id:
            cls = await db.get(LearningClass, current_user.learning_class_id)
        class_active = cls is not None and cls.status == CLASS_STATUS_ACTIVE
        return {
            "role": "student",
            "can_learn": class_active,
            "can_review": False,
            "can_publish": False,
            "must_change_password": bool(getattr(current_user, "must_change_password", False)),
            "class": ({"id": cls.id, "name": cls.name, "class_code": cls.class_code} if class_active and cls else None),
        }
    pilot = await get_enabled_pilot(db, int(current_user.id))
    can_manage = can_manage_learning_space_classes(current_user)
    can_learn = bool(learner_ids)
    can_review = bool(pilot) or bool(assistant_ids)
    can_publish = bool(pilot)
    if pilot:
        role = "pilot_teacher"
    elif assistant_ids:
        role = "assistant"
    elif learner_ids:
        role = "learner"
    elif can_manage:
        role = get_user_role(current_user) or "none"
    else:
        role = "none"
    payload: dict = {
        "role": role,
        "can_learn": can_learn,
        "can_review": can_review,
        "can_publish": can_publish,
        "can_manage_classes": can_manage,
    }
    if pilot:
        payload["organization_id"] = pilot.organization_id
    return payload


@router.get("/ai-permissions/{assignment_id}")
async def get_assignment_ai_permissions(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Return AI flags (and brief assignment) for canvas homework mode."""
    assignment = await get_assignment(db, assignment_id)
    payload = await enrich_assignment_dict(db, assignment)
    viewer = await resolve_assignment_viewer(db, current_user, assignment)
    if viewer == "learner":
        sub_result = await db.execute(
            select(LearningSubmission).where(
                LearningSubmission.assignment_id == assignment_id,
                LearningSubmission.student_user_id == current_user.id,
            )
        )
        submission = sub_result.scalar_one_or_none()
        payload["submission"] = submission_public_dict(submission) if submission else None
    return {
        "assignment_id": assignment_id,
        "ai_permissions": merge_ai_permissions(assignment.ai_permissions),
        "assignment": payload,
    }
