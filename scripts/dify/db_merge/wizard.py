"""
Prompted dump and merge. The operator does not pass flags.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import csv
import io
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts.dify.db_merge.locate import (
    Discovered,
    VerifiedPg,
    candidate_dify_dirs,
    default_dump_dir,
    discovered_from_dir,
    locate_stacks,
    verify_stack,
)
from scripts.dify.db_merge.models import MergePlan, PlanError, SourceMove
from scripts.dify.db_merge.plan import parse_uuid, persona_from_fields, plan_from_sources
from scripts.dify.db_merge.runner import dump_database, execute_sql, list_apps, merge_script

_DUMP_TIMEOUT = 7200
_MERGE_TIMEOUT = 1800
_LIST_TIMEOUT = 120
_WORKFLOW_TITLE = re.compile(r"^(?P<agent>.+?)\s*[Vv]\d+(?:\.\d+)*\s*【(?P<school>[^】]+)】\s*$")
Reader = Callable[[str], str]


_COMPARISON_FIELDS = (
    "role",
    "name",
    "conversations_before",
    "conversations_after",
    "messages_before",
    "messages_after",
    "end_users_before",
    "end_users_after",
    "persona_patched",
)


@dataclass(frozen=True)
class CountReport:
    """Printed before/after table, and whether the counts balance."""

    text: str
    balanced: bool


@dataclass(frozen=True)
class ComparisonRow:
    """One workflow in the before/after report."""

    role: str
    name: str
    conversations_before: int
    conversations_after: int
    messages_before: int
    messages_after: int
    end_users_before: int
    end_users_after: int
    persona_patched: int


@dataclass(frozen=True)
class AppRow:
    """One Dify app in the inventory CSV."""

    app_id: str
    name: str
    mode: str
    conversations: str
    messages: str


def run_interactive(read: Reader | None = None) -> None:
    """Find Dify, verify Postgres, then ask what to do."""
    reader = _tty_reader() if read is None else read
    found = _select_stack(reader)
    if found is None:
        return
    verified = verify_stack(found)
    _print_verified(verified)
    if not _confirm(reader, "Use this database"):
        return
    while True:
        rows = _scan_workflows(verified)
        choice = _choose(
            reader,
            "What do you want to do?",
            ["Merge school workflows", "Dump database", "Quit"],
        )
        if choice == 0:
            if len(rows) < 2:
                print("Need at least two workflows.")
                continue
            _merge(reader, verified, rows)
        elif choice == 1:
            _dump(reader, verified)
        else:
            return


def parse_app_rows(text: str) -> list[AppRow]:
    """Parse the apps inventory CSV."""
    reader = csv.DictReader(io.StringIO(text))
    rows: list[AppRow] = []
    for raw in reader:
        app_id = (raw.get("id") or "").strip()
        if not app_id:
            continue
        rows.append(
            AppRow(
                app_id=app_id,
                name=(raw.get("name") or "").strip(),
                mode=(raw.get("mode") or "").strip(),
                conversations=(raw.get("conversations") or "").strip(),
                messages=(raw.get("messages") or "").strip(),
            )
        )
    return rows


def _tty_reader() -> Reader:
    if not sys.stdin.isatty():
        raise PlanError("run python -m scripts.dify.db_merge in a terminal")

    def read_line(prompt: str) -> str:
        return input(prompt)

    return read_line


def _select_stack(reader: Reader) -> Discovered | None:
    found = locate_stacks()
    if found:
        if len(found) == 1:
            return found[0]
        labels = [f"{row.compose_file}  service {row.service or 'postgres'}" for row in found]
        return found[_choose(reader, "Which Dify Postgres?", labels)]
    print("No Dify Postgres container was found.")
    candidates = candidate_dify_dirs()
    if not candidates:
        print("No Dify compose file under /root.")
        typed = reader("Compose directory (blank to quit): ").strip()
        if not typed:
            return None
        return discovered_from_dir(Path(typed))
    if len(candidates) == 1:
        row = discovered_from_dir(candidates[0])
        print(f"Dify compose: {row.compose_file}")
        return row
    labels = [str(discovered_from_dir(path).compose_file) for path in candidates]
    return discovered_from_dir(candidates[_choose(reader, "Which Dify install under /root?", labels)])


def _print_verified(item: VerifiedPg) -> None:
    print("Dify Postgres")
    print(f"  yaml:            {item.compose_file}")
    print(f"  service:         {item.service}")
    print(f"  database:        {item.database}")
    print(f"  host data:       {item.host_data}")
    print(f"  container mount: {item.mount_source} -> {item.mount_dest}")
    print(f"  data_directory:  {item.data_directory}")
    print("  verified")


def workflow_title_parts(name: str) -> tuple[str, str] | None:
    """Agent name and school from a studio title such as ``远二启慧星v1.3【远东二小】``."""
    match = _WORKFLOW_TITLE.match(name.strip())
    if match is None:
        return None
    agent = match.group("agent").strip()
    school = match.group("school").strip()
    if not agent or not school:
        return None
    return agent, school


def _scan_workflows(item: VerifiedPg) -> list[AppRow]:
    rows = parse_app_rows(list_apps(item.target, _LIST_TIMEOUT))
    if not rows:
        print("No workflows.")
        return []
    _print_workflows(rows)
    return rows


def _dump(reader: Reader, item: VerifiedPg) -> bool:
    out_dir = default_dump_dir(item.target.compose_dir)
    if not _confirm_yes(reader, f"Dump {item.database} to {out_dir}"):
        return False
    dump_path, apps_path, csv_text = dump_database(item.target, out_dir, _DUMP_TIMEOUT)
    print(f"dump: {dump_path}")
    print(f"apps: {apps_path}")
    print(csv_text, end="" if csv_text.endswith("\n") else "\n")
    return True


def format_count_comparison(text: str, *, rolled_back: bool) -> CountReport:
    """Turn the merge CSV into a before/after listing. Unreadable CSV is not balanced."""
    rows = _parse_comparison(text)
    if rows is None:
        banner = _comparison_banner(rolled_back, balanced=False)
        body = text if text.endswith("\n") else f"{text}\n"
        return CountReport(text=f"{banner}\n{body}", balanced=False)
    balanced = _counts_balance(rows)
    lines = [_comparison_banner(rolled_back, balanced=balanced), ""]
    for row in rows:
        lines.extend(_workflow_lines(row))
        lines.append("")
    lines.append(_balance_line(rows, balanced=balanced))
    return CountReport(text="\n".join(lines) + "\n", balanced=balanced)


def _run_merge(item: VerifiedPg, plan: MergePlan, *, rolled_back: bool) -> CountReport:
    text = execute_sql(item.target, merge_script(item.target, plan, _MERGE_TIMEOUT), _MERGE_TIMEOUT)
    report = format_count_comparison(text, rolled_back=rolled_back)
    print(report.text, end="" if report.text.endswith("\n") else "\n")
    return report


def _comparison_banner(rolled_back: bool, *, balanced: bool) -> str:
    if rolled_back:
        return "Dry run. Rolled back. The after numbers were not saved."
    if balanced:
        return "Actual run. The output workflow has the moved chat."
    return (
        "Actual run committed, but the before/after report does not balance. "
        "Restore the database dump before using the output workflow."
    )


def _workflow_lines(row: ComparisonRow) -> list[str]:
    title = row.name or "(unnamed)"
    return [
        f"{title}  ({row.role})",
        f"  conversations    {row.conversations_before} -> {row.conversations_after}",
        f"  messages         {row.messages_before} -> {row.messages_after}",
        f"  end users        {row.end_users_before} -> {row.end_users_after}",
        f"  persona patched  {row.persona_patched}",
    ]


def _parse_comparison(text: str) -> list[ComparisonRow] | None:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not set(_COMPARISON_FIELDS).issubset(set(reader.fieldnames)):
        return None
    rows: list[ComparisonRow] = []
    for raw in reader:
        parsed = _comparison_row(raw)
        if parsed is None:
            return None
        rows.append(parsed)
    if not rows:
        return None
    return rows


def _comparison_row(raw: dict[str, str | None]) -> ComparisonRow | None:
    role = (raw.get("role") or "").strip()
    if role not in {"input", "output"}:
        return None
    numbers: dict[str, int] = {}
    for field in _COMPARISON_FIELDS[2:]:
        cell = (raw.get(field) or "").strip()
        if not cell.isdigit():
            return None
        numbers[field] = int(cell)
    return ComparisonRow(
        role=role,
        name=(raw.get("name") or "").strip(),
        conversations_before=numbers["conversations_before"],
        conversations_after=numbers["conversations_after"],
        messages_before=numbers["messages_before"],
        messages_after=numbers["messages_after"],
        end_users_before=numbers["end_users_before"],
        end_users_after=numbers["end_users_after"],
        persona_patched=numbers["persona_patched"],
    )


def _counts_balance(rows: list[ComparisonRow]) -> bool:
    inputs = [row for row in rows if row.role == "input"]
    outputs = [row for row in rows if row.role == "output"]
    if len(outputs) != 1 or not inputs:
        return False
    output = outputs[0]
    if any(row.conversations_after or row.messages_after for row in inputs):
        return False
    conversations = sum(row.conversations_before - row.conversations_after for row in inputs)
    messages = sum(row.messages_before - row.messages_after for row in inputs)
    end_users = sum(row.end_users_before - row.end_users_after for row in inputs)
    persona = sum(row.persona_patched for row in inputs)
    gained_conversations = output.conversations_after - output.conversations_before
    gained_messages = output.messages_after - output.messages_before
    gained_users = output.end_users_after - output.end_users_before
    return (
        conversations == gained_conversations
        and messages == gained_messages
        and end_users == gained_users
        and persona == output.persona_patched
    )


def _balance_line(rows: list[ComparisonRow], *, balanced: bool) -> str:
    if not balanced:
        return "Check failed: the output workflow does not have every moved row."
    output = next(row for row in rows if row.role == "output")
    inputs = [row for row in rows if row.role == "input"]
    moved_conversations = output.conversations_after - output.conversations_before
    moved_messages = output.messages_after - output.messages_before
    moved_users = output.end_users_after - output.end_users_before
    stayed = sum(row.end_users_after for row in inputs)
    return (
        f"Check: {moved_conversations} conversations and {moved_messages} messages moved onto the output. "
        f"{moved_users} end users moved. {stayed} end users stayed on an input. "
        "The output workflow has every moved conversation, message, and end user. "
        "Workflow definitions stay on the original workflows."
    )


def _merge(reader: Reader, item: VerifiedPg, rows: list[AppRow]) -> None:
    sources = _ask_inputs(reader, rows)
    target = _ask_output(reader, rows, sources)
    print("Inputs:")
    for row in sources:
        print(f"  {row.name or row.app_id}")
    print(f"Output: {target.name or target.app_id}")
    if not _confirm(reader, "Move chat history from those inputs into the output"):
        return
    plan_sources = [_ask_persona(reader, row) for row in sources]
    mode = _choose(
        reader,
        "Dry run or actual run?",
        ["Dry run (lock, compare, roll back)", "Actual run"],
    )
    execute = mode == 1
    label = target.name or target.app_id
    if execute and not _dump(reader, item):
        print("No new dump. The actual run still writes this database.")
    if execute and reader(f"Type {label} to run: ").strip() != label:
        raise PlanError("output name did not match; nothing was changed")
    plan = plan_from_sources(target.app_id, plan_sources, execute=execute)
    if any(not source.persona for source in plan.sources) and not _confirm(reader, "An input has no persona. Continue"):
        return
    _run_merge(item, plan, rolled_back=not execute)


def _print_workflows(rows: list[AppRow]) -> None:
    print("Workflows")
    for index, row in enumerate(rows, start=1):
        label = row.name or "(unnamed)"
        print(f"  [{index}] {label}  ({row.conversations} conversations)")


def _ask_inputs(reader: Reader, rows: list[AppRow]) -> list[AppRow]:
    raw = reader("Input workflows (comma-separated numbers, for example 1,3,8): ")
    numbers = _parse_numbers(raw, len(rows))
    chosen = [rows[number - 1] for number in numbers]
    if not chosen:
        raise PlanError("select at least one input workflow")
    return chosen


def _ask_output(reader: Reader, rows: list[AppRow], sources: list[AppRow]) -> AppRow:
    target = rows[_ask_index(reader, "Final merge output (one number): ", len(rows))]
    if target.app_id in {row.app_id for row in sources}:
        raise PlanError("the output workflow cannot also be an input")
    return target


def _ask_persona(reader: Reader, row: AppRow) -> SourceMove:
    print(f"Input: {row.name or row.app_id}")
    parsed = workflow_title_parts(row.name)
    agent_default = "" if parsed is None else parsed[0]
    school_default = "" if parsed is None else parsed[1]
    while True:
        try:
            persona = persona_from_fields(
                _defaulted(reader, "  agent name", agent_default),
                reader("  alias (blank uses the agent name): "),
                _defaulted(reader, "  school", school_default),
            )
        except PlanError as exc:
            print(exc)
            continue
        return SourceMove(app_id=parse_uuid(row.app_id, "workflow id"), persona=persona)


def _defaulted(reader: Reader, label: str, default: str) -> str:
    if not default:
        return reader(f"{label}: ")
    typed = reader(f"{label} [{default}]: ").strip()
    return typed or default


def _parse_numbers(raw: str, count: int) -> list[int]:
    numbers: list[int] = []
    for part in raw.split(","):
        text = part.strip()
        if not text:
            continue
        if not text.isdigit():
            raise PlanError(f"{text} is not a workflow number")
        number = int(text)
        if number < 1 or number > count:
            raise PlanError(f"{number} is not a workflow number")
        if number not in numbers:
            numbers.append(number)
    return numbers


def _ask_index(reader: Reader, prompt: str, count: int) -> int:
    numbers = _parse_numbers(reader(prompt), count)
    if len(numbers) != 1:
        raise PlanError("enter one workflow number")
    return numbers[0] - 1


def _choose(reader: Reader, title: str, labels: list[str]) -> int:
    print(title)
    for index, label in enumerate(labels, start=1):
        print(f"  [{index}] {label}")
    while True:
        raw = reader("Choose: ").strip()
        if raw.isdigit():
            number = int(raw)
            if 1 <= number <= len(labels):
                return number - 1
        print("Enter one of the numbers above.")


def _confirm(reader: Reader, prompt: str) -> bool:
    return reader(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}


def _confirm_yes(reader: Reader, prompt: str) -> bool:
    return reader(f"{prompt} [Y/n]: ").strip().lower() in {"", "y", "yes"}
