"""
SQL for an in-place Dify history move.

The script updates chat tables only. It does not update apps, workflows,
api_tokens, or workflow_runs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json

from scripts.dify.db_merge.models import MergePlan
from scripts.dify.db_merge.schema import SchemaFacts


def apps_inventory_sql(facts: SchemaFacts) -> str:
    """CSV of apps with conversation and message counts."""
    order = "a.created_at NULLS LAST, a.id" if facts.apps_created_at else "a.id"
    mode_expr = "COALESCE(a.mode, '')" if facts.apps_mode else "''"
    return f"""
COPY (
  SELECT a.id::text AS id,
         COALESCE(a.name, '') AS name,
         {mode_expr} AS mode,
         (SELECT count(*) FROM public.conversations AS c WHERE c.app_id = a.id) AS conversations,
         (SELECT count(*) FROM public.messages AS m WHERE m.app_id = a.id) AS messages
  FROM public.apps AS a
  ORDER BY {order}
) TO STDOUT WITH (FORMAT csv, HEADER true);
""".strip()


def build_merge_sql(plan: MergePlan, facts: SchemaFacts) -> str:
    """One psql script. Dry-run ends in ROLLBACK after the count report."""
    ending = "COMMIT;" if plan.execute else "ROLLBACK;"
    target = plan.target_app_id
    parts = [
        "-- Move MindMate chat history onto one Dify app. Workflow rows stay put.",
        "SET lock_timeout = '30s';",
        "SET statement_timeout = '30min';",
        "BEGIN;",
        "DO $mglock$ BEGIN PERFORM pg_advisory_xact_lock(hashtext('mindgraph_dify_history_merge')); END $mglock$;",
        _lock_sql(facts),
        _source_table_sql(plan),
        _moved_conversations_sql(),
        _assert_apps_sql(target),
        _counts_before_sql(target),
        _end_user_map_sql(target, facts),
        _repoint_sql("public.conversations", "row.id IN (SELECT id FROM mg_moved_conversations)"),
        _repoint_sql("public.messages", "row.conversation_id IN (SELECT id FROM mg_moved_conversations)"),
        _feedback_repoint_sql(facts),
        _move_app_sql("public.conversations", target),
        _move_messages_sql(target),
        _feedback_move_sql(facts, target),
        _move_end_users_sql(target),
        _annotation_move_sql(facts, target),
        _patch_inputs_sql(facts),
        _leftover_sql(target, facts),
        _target_has_everything_sql(target, facts),
        _report_sql(),
        ending,
    ]
    return "\n\n".join(part for part in parts if part) + "\n"


def dollar_quote(value: str) -> str:
    """Quote ``value`` so psql cannot treat it as SQL."""
    tag = "mgq"
    while f"${tag}$" in value:
        tag += "x"
    return f"${tag}${value}${tag}$"


def _source_table_sql(plan: MergePlan) -> str:
    rows: list[str] = []
    for source in plan.sources:
        payload = json.dumps(source.persona, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        rows.append(f"  ('{source.app_id}'::uuid, {dollar_quote(payload)}::jsonb)")
    joined = ",\n".join(rows)
    return f"""
CREATE TEMP TABLE mg_source_apps (
  app_id uuid PRIMARY KEY,
  persona jsonb NOT NULL
) ON COMMIT DROP;

INSERT INTO mg_source_apps (app_id, persona) VALUES
{joined};
""".strip()


def _moved_conversations_sql() -> str:
    return """
CREATE TEMP TABLE mg_moved_conversations ON COMMIT DROP AS
SELECT c.id, s.app_id AS source_app_id, s.persona
FROM public.conversations AS c
JOIN mg_source_apps AS s ON s.app_id = c.app_id;
""".strip()


def _assert_apps_sql(target: str) -> str:
    return f"""
DO $mgcheck$
DECLARE
  missing_target int;
  missing_source int;
BEGIN
  SELECT count(*) INTO missing_target FROM public.apps WHERE id = '{target}'::uuid;
  IF missing_target <> 1 THEN
    RAISE EXCEPTION 'target app not found: {target}';
  END IF;
  SELECT count(*) INTO missing_source
  FROM mg_source_apps AS s
  LEFT JOIN public.apps AS a ON a.id = s.app_id
  WHERE a.id IS NULL;
  IF missing_source <> 0 THEN
    RAISE EXCEPTION 'one or more source apps were not found';
  END IF;
END
$mgcheck$;
""".strip()


def _end_user_map_sql(target: str, facts: SchemaFacts) -> str:
    order_tail = "e.created_at NULLS LAST, e.id" if facts.end_user_created_at else "e.id"
    return f"""
CREATE TEMP TABLE mg_end_user_map (
  old_id uuid PRIMARY KEY,
  new_id uuid NOT NULL,
  collapsed boolean NOT NULL
) ON COMMIT DROP;

INSERT INTO mg_end_user_map (old_id, new_id, collapsed)
SELECT src.id, src.id, false
FROM public.end_users AS src
JOIN mg_source_apps AS s ON s.app_id = src.app_id
WHERE src.session_id IS NULL OR btrim(src.session_id) = '';

INSERT INTO mg_end_user_map (old_id, new_id, collapsed)
SELECT src.id, canon.id, src.id <> canon.id
FROM public.end_users AS src
JOIN mg_source_apps AS s ON s.app_id = src.app_id
JOIN LATERAL (
  SELECT e.id
  FROM public.end_users AS e
  WHERE e.tenant_id IS NOT DISTINCT FROM src.tenant_id
    AND e.session_id = src.session_id
    AND e.type IS NOT DISTINCT FROM src.type
    AND (
      e.app_id = '{target}'::uuid
      OR e.app_id IN (SELECT app_id FROM mg_source_apps)
    )
  ORDER BY
    CASE WHEN e.app_id = '{target}'::uuid THEN 0 ELSE 1 END,
    {order_tail}
  LIMIT 1
) AS canon ON true
WHERE src.session_id IS NOT NULL AND btrim(src.session_id) <> '';
""".strip()


def _repoint_sql(table: str, scope: str) -> str:
    return f"""
UPDATE {table} AS row
SET from_end_user_id = map.new_id
FROM mg_end_user_map AS map
WHERE row.from_end_user_id = map.old_id
  AND map.collapsed
  AND {scope};
""".strip()


def _feedback_repoint_sql(facts: SchemaFacts) -> str:
    if not facts.feedback_end_user:
        return ""
    if facts.feedback_conversation:
        scope = "row.conversation_id IN (SELECT id FROM mg_moved_conversations)"
    elif facts.feedback_message:
        scope = (
            "row.message_id IN (SELECT msg.id FROM public.messages AS msg "
            "JOIN mg_moved_conversations AS mv ON mv.id = msg.conversation_id)"
        )
    elif facts.feedback_app_id:
        scope = "row.app_id IN (SELECT app_id FROM mg_source_apps)"
    else:
        return ""
    return _repoint_sql("public.message_feedbacks", scope)


def _lock_sql(facts: SchemaFacts) -> str:
    tables = ["public.end_users", "public.conversations", "public.messages"]
    if facts.feedback_app_id or facts.feedback_end_user:
        tables.append("public.message_feedbacks")
    if facts.annotation_app_id:
        tables.append("public.message_annotations")
    joined = ", ".join(tables)
    return f"LOCK TABLE {joined} IN SHARE ROW EXCLUSIVE MODE;"


def _move_app_sql(table: str, target: str) -> str:
    return f"""
UPDATE {table} AS row
SET app_id = '{target}'::uuid
WHERE row.app_id IN (SELECT app_id FROM mg_source_apps);
""".strip()


def _move_messages_sql(target: str) -> str:
    return f"""
UPDATE public.messages AS row
SET app_id = '{target}'::uuid
WHERE row.app_id IN (SELECT app_id FROM mg_source_apps)
   OR row.conversation_id IN (SELECT id FROM mg_moved_conversations);
""".strip()


def _feedback_move_sql(facts: SchemaFacts, target: str) -> str:
    if not facts.feedback_app_id:
        return ""
    clauses = ["row.app_id IN (SELECT app_id FROM mg_source_apps)"]
    if facts.feedback_conversation:
        clauses.append("row.conversation_id IN (SELECT id FROM mg_moved_conversations)")
    if facts.feedback_message:
        clauses.append(
            "row.message_id IN (SELECT msg.id FROM public.messages AS msg "
            "JOIN mg_moved_conversations AS mv ON mv.id = msg.conversation_id)"
        )
    joined = "\n   OR ".join(clauses)
    return f"""
UPDATE public.message_feedbacks AS row
SET app_id = '{target}'::uuid
WHERE {joined};
""".strip()


def _annotation_move_sql(facts: SchemaFacts, target: str) -> str:
    if not facts.annotation_app_id:
        return ""
    where = "row.app_id IN (SELECT app_id FROM mg_source_apps)"
    if facts.annotation_conversation:
        where += "\n   OR row.conversation_id IN (SELECT id FROM mg_moved_conversations)"
    return f"""
UPDATE public.message_annotations AS row
SET app_id = '{target}'::uuid
WHERE {where};
""".strip()


def _move_end_users_sql(target: str) -> str:
    return f"""
UPDATE public.end_users AS src
SET app_id = '{target}'::uuid
FROM mg_end_user_map AS map
WHERE src.id = map.old_id
  AND NOT map.collapsed;
""".strip()


def _patch_inputs_sql(facts: SchemaFacts) -> str:
    merged = "COALESCE(conv.inputs::jsonb, '{}'::jsonb) || mv.persona"
    if facts.inputs_udt == "json":
        assigned = f"({merged})::json"
    else:
        assigned = merged
    return f"""
UPDATE public.conversations AS conv
SET inputs = {assigned}
FROM mg_moved_conversations AS mv
WHERE conv.id = mv.id
  AND mv.persona <> '{{}}'::jsonb;
""".strip()


def _leftover_sql(target: str, facts: SchemaFacts) -> str:
    feedback_check = ""
    if facts.feedback_app_id:
        feedback_check = """
  SELECT count(*) INTO leftover
  FROM public.message_feedbacks
  WHERE app_id IN (SELECT app_id FROM mg_source_apps);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'message feedback still on source apps: %', leftover;
  END IF;
"""
    return f"""
DO $mgleft$
DECLARE
  leftover bigint;
BEGIN
  SELECT count(*) INTO leftover
  FROM public.conversations
  WHERE app_id IN (SELECT app_id FROM mg_source_apps);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'conversations still on source apps: %', leftover;
  END IF;
  SELECT count(*) INTO leftover
  FROM public.messages
  WHERE app_id IN (SELECT app_id FROM mg_source_apps);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'messages still on source apps: %', leftover;
  END IF;
{feedback_check}
  SELECT count(*) INTO leftover
  FROM public.end_users AS src
  JOIN mg_end_user_map AS map ON map.old_id = src.id
  WHERE NOT map.collapsed
    AND src.app_id <> '{target}'::uuid;
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'end users were not moved onto the target app: %', leftover;
  END IF;
END
$mgleft$;
""".strip()


def _target_has_everything_sql(target: str, facts: SchemaFacts) -> str:
    extra = _feedback_on_target_sql(target, facts) + _annotations_on_target_sql(target, facts)
    return f"""
DO $mgfull$
DECLARE
  leftover bigint;
  expected bigint;
BEGIN
  SELECT count(*) INTO leftover
  FROM mg_moved_conversations AS mv
  LEFT JOIN public.conversations AS c ON c.id = mv.id
  WHERE c.id IS NULL OR c.app_id <> '{target}'::uuid;
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'target is missing moved conversations: %', leftover;
  END IF;
  SELECT count(*) INTO leftover
  FROM public.messages AS msg
  JOIN mg_moved_conversations AS mv ON mv.id = msg.conversation_id
  WHERE msg.app_id <> '{target}'::uuid;
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'target is missing messages from moved conversations: %', leftover;
  END IF;
  SELECT COALESCE(sum(conversations), 0)::bigint INTO expected FROM mg_counts_before;
  SELECT count(*) INTO leftover FROM public.conversations WHERE app_id = '{target}'::uuid;
  IF leftover <> expected THEN
    RAISE EXCEPTION 'target conversation count % does not equal the before total %', leftover, expected;
  END IF;
  SELECT messages INTO expected FROM mg_message_expected;
  SELECT count(*) INTO leftover FROM public.messages WHERE app_id = '{target}'::uuid;
  IF leftover <> expected THEN
    RAISE EXCEPTION 'target message count % does not equal the before total %', leftover, expected;
  END IF;
  SELECT COALESCE((SELECT end_users FROM mg_counts_before WHERE is_output), 0)::bigint
       + (SELECT count(*) FROM mg_end_user_map WHERE NOT collapsed)
  INTO expected;
  SELECT count(*) INTO leftover FROM public.end_users WHERE app_id = '{target}'::uuid;
  IF leftover <> expected THEN
    RAISE EXCEPTION 'target end user count % does not equal the before total %', leftover, expected;
  END IF;
  SELECT count(*) INTO leftover
  FROM public.conversations AS c
  JOIN mg_moved_conversations AS mv ON mv.id = c.id
  LEFT JOIN public.end_users AS e ON e.id = c.from_end_user_id
  WHERE c.from_end_user_id IS NOT NULL
    AND (e.id IS NULL OR e.app_id <> '{target}'::uuid);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'a moved conversation does not point at an end user on the target: %', leftover;
  END IF;
  SELECT count(*) INTO leftover
  FROM public.messages AS msg
  JOIN mg_moved_conversations AS mv ON mv.id = msg.conversation_id
  LEFT JOIN public.end_users AS e ON e.id = msg.from_end_user_id
  WHERE msg.from_end_user_id IS NOT NULL
    AND (e.id IS NULL OR e.app_id <> '{target}'::uuid);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'a moved message does not point at an end user on the target: %', leftover;
  END IF;
  SELECT count(*) INTO leftover
  FROM public.conversations AS c
  JOIN mg_moved_conversations AS mv ON mv.id = c.id
  WHERE mv.persona <> '{{}}'::jsonb
    AND (
      NOT (COALESCE(c.inputs::jsonb, '{{}}'::jsonb) ? 'mg_agent_name')
      OR NOT (COALESCE(c.inputs::jsonb, '{{}}'::jsonb) ? 'mg_agent_alias')
      OR NOT (COALESCE(c.inputs::jsonb, '{{}}'::jsonb) ? 'mg_school_name')
    );
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'persona was not written onto moved conversations: %', leftover;
  END IF;
{extra}END
$mgfull$;
""".strip()


def _feedback_on_target_sql(target: str, facts: SchemaFacts) -> str:
    if not facts.feedback_app_id:
        return ""
    links: list[str] = []
    if facts.feedback_conversation:
        links.append("f.conversation_id IN (SELECT id FROM mg_moved_conversations)")
    if facts.feedback_message:
        links.append(
            "f.message_id IN ("
            "SELECT msg.id FROM public.messages AS msg "
            "JOIN mg_moved_conversations AS mv ON mv.id = msg.conversation_id)"
        )
    if not links:
        return ""
    joined = " OR ".join(links)
    sender = ""
    if facts.feedback_end_user:
        sender = f"""
  SELECT count(*) INTO leftover
  FROM public.message_feedbacks AS f
  LEFT JOIN public.end_users AS e ON e.id = f.from_end_user_id
  WHERE ({joined})
    AND f.from_end_user_id IS NOT NULL
    AND (e.id IS NULL OR e.app_id IS DISTINCT FROM '{target}'::uuid);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'feedback does not point at an end user on the target: %', leftover;
  END IF;
"""
    return f"""
  SELECT count(*) INTO leftover
  FROM public.message_feedbacks AS f
  WHERE ({joined})
    AND f.app_id IS DISTINCT FROM '{target}'::uuid;
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'target is missing feedback for moved conversations: %', leftover;
  END IF;
{sender}"""


def _annotations_on_target_sql(target: str, facts: SchemaFacts) -> str:
    if not facts.annotation_app_id:
        return ""
    linked = ""
    if facts.annotation_conversation:
        linked = f"""
  SELECT count(*) INTO leftover
  FROM public.message_annotations AS note
  WHERE note.conversation_id IN (SELECT id FROM mg_moved_conversations)
    AND note.app_id IS DISTINCT FROM '{target}'::uuid;
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'target is missing annotations for moved conversations: %', leftover;
  END IF;
"""
    return f"""
  SELECT count(*) INTO leftover
  FROM public.message_annotations
  WHERE app_id IN (SELECT app_id FROM mg_source_apps);
  IF leftover <> 0 THEN
    RAISE EXCEPTION 'annotations still on source workflows: %', leftover;
  END IF;
{linked}"""


def _counts_before_sql(target: str) -> str:
    return f"""
CREATE TEMP TABLE mg_counts_before ON COMMIT DROP AS
SELECT
  a.id AS app_id,
  COALESCE(a.name, '') AS name,
  (a.id = '{target}'::uuid) AS is_output,
  (SELECT count(*) FROM public.conversations AS c WHERE c.app_id = a.id) AS conversations,
  (SELECT count(*) FROM public.messages AS m WHERE m.app_id = a.id) AS messages,
  (SELECT count(*) FROM public.end_users AS e WHERE e.app_id = a.id) AS end_users
FROM public.apps AS a
WHERE a.id = '{target}'::uuid
   OR a.id IN (SELECT app_id FROM mg_source_apps);

CREATE TEMP TABLE mg_message_expected ON COMMIT DROP AS
SELECT count(*)::bigint AS messages
FROM public.messages AS m
WHERE m.app_id = '{target}'::uuid
   OR m.app_id IN (SELECT app_id FROM mg_source_apps)
   OR m.conversation_id IN (SELECT id FROM mg_moved_conversations);
""".strip()


def _report_sql() -> str:
    persona = "mv.persona <> '{}'::jsonb"
    output_persona = f"(SELECT count(*) FROM mg_moved_conversations AS mv WHERE {persona})"
    input_persona = (
        f"(SELECT count(*) FROM mg_moved_conversations AS mv WHERE mv.source_app_id = b.app_id AND {persona})"
    )
    return f"""
COPY (
  SELECT
    CASE WHEN b.is_output THEN 'output' ELSE 'input' END AS role,
    b.name,
    b.conversations AS conversations_before,
    (SELECT count(*) FROM public.conversations AS c WHERE c.app_id = b.app_id) AS conversations_after,
    b.messages AS messages_before,
    (SELECT count(*) FROM public.messages AS m WHERE m.app_id = b.app_id) AS messages_after,
    b.end_users AS end_users_before,
    (SELECT count(*) FROM public.end_users AS e WHERE e.app_id = b.app_id) AS end_users_after,
    CASE WHEN b.is_output THEN {output_persona} ELSE {input_persona} END AS persona_patched
  FROM mg_counts_before AS b
  ORDER BY b.is_output, b.name
) TO STDOUT WITH (FORMAT csv, HEADER true);
""".strip()
