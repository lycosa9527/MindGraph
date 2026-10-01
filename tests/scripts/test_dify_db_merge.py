"""Dify history dump/merge planning. No Docker and no database."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dify.db_merge.cli import main
from scripts.dify.db_merge.compose import load_stack, pick_db_service
from scripts.dify.db_merge.envfile import parse_env_file
from scripts.dify.db_merge.locate import (
    Discovered,
    Mount,
    PgBind,
    VerifiedPg,
    assert_pg_location,
    default_dump_dir,
    dify_compose_dirs,
    discovered_from_inspect,
    pg_bind_from_compose,
)
from scripts.dify.db_merge.models import ComposeError, ComposeTarget, MergePlan, PlanError, SchemaError, SourceMove
from scripts.dify.db_merge.plan import persona_from_fields, plan_from_sources
from scripts.dify.db_merge.schema import SchemaFacts, parse_column_csv
from scripts.dify.db_merge.sql import apps_inventory_sql, build_merge_sql, dollar_quote
from scripts.dify.db_merge.wizard import format_count_comparison, run_interactive, workflow_title_parts

TARGET = "11111111-1111-1111-1111-111111111111"
SOURCE = "22222222-2222-2222-2222-222222222222"
OTHER = "33333333-3333-3333-3333-333333333333"

_CATALOG = """\
table_name,column_name,udt_name
apps,id,uuid
apps,name,varchar
apps,mode,varchar
apps,created_at,timestamp
end_users,id,uuid
end_users,app_id,uuid
end_users,tenant_id,uuid
end_users,session_id,varchar
end_users,type,varchar
end_users,created_at,timestamp
conversations,id,uuid
conversations,app_id,uuid
conversations,from_end_user_id,uuid
conversations,inputs,json
messages,id,uuid
messages,app_id,uuid
messages,conversation_id,uuid
messages,from_end_user_id,uuid
message_feedbacks,id,uuid
message_feedbacks,app_id,uuid
message_feedbacks,conversation_id,uuid
message_feedbacks,from_end_user_id,uuid
"""


def _facts(
    *,
    apps_created_at: bool = True,
    apps_mode: bool = True,
    end_user_created_at: bool = True,
    inputs_udt: str = "json",
    feedback_app_id: bool = True,
    feedback_end_user: bool = True,
    feedback_conversation: bool = True,
    feedback_message: bool = False,
    annotation_app_id: bool = False,
    annotation_conversation: bool = False,
) -> SchemaFacts:
    return SchemaFacts(
        apps_created_at=apps_created_at,
        apps_mode=apps_mode,
        end_user_created_at=end_user_created_at,
        inputs_udt=inputs_udt,
        feedback_app_id=feedback_app_id,
        feedback_end_user=feedback_end_user,
        feedback_conversation=feedback_conversation,
        feedback_message=feedback_message,
        annotation_app_id=annotation_app_id,
        annotation_conversation=annotation_conversation,
    )


def _source(app_id: str, name: str = "远二启慧星", school: str = "远二") -> SourceMove:
    return SourceMove(app_id=app_id, persona=persona_from_fields(name, "", school))


def test_env_file_strips_quotes_and_skips_comments() -> None:
    """Quoted values and export prefixes are kept; comments are not."""
    parsed = parse_env_file(
        "\n".join(
            [
                "# comment",
                'export DB_USERNAME="postgres"',
                "DB_DATABASE='dify'",
                "DB_PASSWORD=difyai123456",
                "NOT_A_PAIR",
            ]
        )
    )
    assert parsed["DB_USERNAME"] == "postgres"
    assert parsed["DB_DATABASE"] == "dify"
    assert parsed["DB_PASSWORD"] == "difyai123456"
    assert "NOT_A_PAIR" not in parsed


def test_load_stack_reads_database_name(tmp_path: Path) -> None:
    """Compose dir supplies the database user and name, not a published port."""
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DB_USERNAME=postgres\nDB_DATABASE=dify\n", encoding="utf-8")
    stack = load_stack(tmp_path, "")
    assert stack.db_name == "dify"
    assert stack.service == ""
    assert "--profile" in stack.command(["ps"])
    assert "postgresql" in stack.command(["ps"])
    assert "difyai123456" not in stack.command(["ps"])


def test_load_stack_rejects_unsafe_user(tmp_path: Path) -> None:
    """A database user cannot carry SQL or shell metacharacters."""
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DB_USERNAME=postgres;drop\nDB_DATABASE=dify\n", encoding="utf-8")
    with pytest.raises(PlanError):
        load_stack(tmp_path, "")


def test_pick_db_service_prefers_current_compose_name() -> None:
    """Current Dify names the service db_postgres; older stacks used db."""
    assert pick_db_service(["nginx", "db_postgres", "api"], None) == "db_postgres"
    assert pick_db_service(["db", "api"], None) == "db"
    with pytest.raises(ComposeError):
        pick_db_service(["db_postgres", "db"], None)
    with pytest.raises(ComposeError):
        pick_db_service(["api"], None)


def test_catalog_requires_message_app_id() -> None:
    """A dump we cannot scope by app_id is refused before any update."""
    tables = parse_column_csv(_CATALOG.replace("messages,app_id,uuid\n", ""))
    with pytest.raises(SchemaError, match="messages.app_id"):
        SchemaFacts.from_catalog(tables)


def test_dollar_quote_changes_tag_when_text_contains_delimiter() -> None:
    """The quote tag grows until it does not appear in the value."""
    quoted = dollar_quote("hello $mgq$ world")
    assert quoted.startswith("$mgqx$")
    assert quoted.endswith("$mgqx$")
    assert "hello $mgq$ world" in quoted


def test_dry_run_rolls_back_and_leaves_workflow_tables() -> None:
    """Dry-run reports the move and does not rewrite the chatflow graph."""
    plan = plan_from_sources(TARGET, [_source(SOURCE), _source(OTHER, "八一思行者", "八一")], execute=False)
    sql = build_merge_sql(plan, _facts())
    assert sql.strip().endswith("ROLLBACK;")
    assert "\nCOMMIT;" not in sql
    assert SOURCE in sql
    assert OTHER in sql
    assert "远二启慧星" in sql
    assert "八一思行者" in sql
    assert "mg_agent_alias" in sql
    assert "workflow_conversation_variables" not in sql
    for forbidden in (
        "UPDATE public.apps",
        "UPDATE public.workflows",
        "UPDATE public.workflow_runs",
        "UPDATE public.api_tokens",
    ):
        assert forbidden not in sql
    assert ")::json" in sql
    assert "message_feedbacks" in sql
    assert "mg_counts_before" in sql
    assert "conversations_before" in sql
    assert "conversations_after" in sql
    assert "source_app_id" in sql
    assert "PERFORM pg_advisory_xact_lock" in sql
    assert "SELECT pg_advisory_xact_lock" not in sql
    assert "target is missing moved conversations" in sql
    assert "target is missing messages from moved conversations" in sql
    assert "target conversation count" in sql
    assert "persona was not written onto moved conversations" in sql
    assert "target is missing feedback" in sql
    assert "a moved message does not point at an end user on the target" in sql
    assert "mg_message_expected" in sql
    assert "row.conversation_id IN (SELECT id FROM mg_moved_conversations)" in sql
    assert "message_annotations" not in sql


def test_annotations_move_onto_the_output() -> None:
    """Saved annotations follow the conversation onto the output workflow."""
    plan = plan_from_sources(TARGET, [_source(SOURCE)], execute=False)
    sql = build_merge_sql(plan, _facts(annotation_app_id=True, annotation_conversation=True))
    assert "UPDATE public.message_annotations" in sql
    assert "target is missing annotations" in sql
    assert "UPDATE public.workflows" not in sql


def test_execute_commits() -> None:
    """An actual run is the only path that commits."""
    plan = plan_from_sources(TARGET, [_source(SOURCE)], execute=True)
    sql = build_merge_sql(plan, _facts(inputs_udt="jsonb", feedback_app_id=False, feedback_end_user=False))
    assert sql.strip().endswith("COMMIT;")
    assert "\nROLLBACK;" not in sql
    assert "message_feedbacks" not in sql
    assert ")::json\n" not in sql


def test_persona_text_cannot_close_the_statement() -> None:
    """A school name with SQL punctuation stays inside the dollar quote."""
    nasty = "O'Brien; DROP TABLE public.apps;--"
    persona = persona_from_fields(nasty, "", "School")
    plan = plan_from_sources(TARGET, [SourceMove(app_id=SOURCE, persona=persona)], execute=False)
    sql = build_merge_sql(plan, _facts())
    assert nasty in sql
    assert sql.strip().endswith("ROLLBACK;")
    assert "UPDATE public.apps" not in sql


def test_plan_rejects_target_as_source() -> None:
    """Moving an app onto itself is refused."""
    with pytest.raises(PlanError):
        plan_from_sources(TARGET, [_source(TARGET)], execute=False)
    with pytest.raises(PlanError):
        plan_from_sources(TARGET, [_source(SOURCE), _source(SOURCE)], execute=False)


def test_persona_requires_name_and_school() -> None:
    """A partial persona would leave Start variables half-set on old threads."""
    with pytest.raises(PlanError):
        persona_from_fields("MindMate", "", "")
    assert not persona_from_fields("", "", "")
    filled = persona_from_fields("MindMate", "", "School")
    assert filled["mg_agent_alias"] == "MindMate"


def test_apps_sql_orders_by_id_when_created_at_is_absent() -> None:
    """Older catalogs still list apps without assuming created_at."""
    sql = apps_inventory_sql(_facts(apps_created_at=False, apps_mode=False))
    assert "NULLS LAST" not in sql
    assert "ORDER BY a.id" in sql


def test_main_rejects_arguments() -> None:
    """The tool asks questions; it does not take flags."""
    assert main(["--compose-dir", "/tmp"]) == 2
    assert main(["apps"]) == 2


def test_compose_volume_is_the_postgres_bind(tmp_path: Path) -> None:
    """The Postgres service volume is used, and the MySQL volume is ignored."""
    text = "\n".join(
        [
            "services:",
            "  db_postgres:",
            "    image: postgres:15-alpine",
            "    volumes:",
            "      - ./volumes/db/data:/var/lib/postgresql/data",
            "  db_mysql:",
            "    image: mysql:8.0",
            "    volumes:",
            "      - ./volumes/mysql/data:/var/lib/mysql",
        ]
    )
    bind = pg_bind_from_compose(text, tmp_path)
    assert bind.service == "db_postgres"
    assert bind.host_path == (tmp_path / "volumes" / "db" / "data").resolve()
    assert bind.destination == "/var/lib/postgresql/data"


def test_location_requires_compose_mount_and_data_directory(tmp_path: Path) -> None:
    """The yaml path, the container mount, and data_directory have to be the same database."""
    data = tmp_path / "volumes" / "db" / "data"
    data.mkdir(parents=True)
    host = data.resolve()
    bind = PgBind("db_postgres", host, "", "/var/lib/postgresql/data")
    mount = Mount(str(host), "/var/lib/postgresql/data", "bind", "")
    assert_pg_location(bind, [mount], "/var/lib/postgresql/data/pgdata", "dify", "dify")
    other = tmp_path / "elsewhere"
    other.mkdir()
    mismatched = Mount(str(other.resolve()), "/var/lib/postgresql/data", "bind", "")
    with pytest.raises(PlanError, match="does not match"):
        assert_pg_location(bind, [mismatched], "/var/lib/postgresql/data/pgdata", "dify", "dify")
    with pytest.raises(PlanError, match="outside"):
        assert_pg_location(bind, [mount], "/tmp/not-pg", "dify", "dify")


def test_inspect_uses_compose_label(tmp_path: Path) -> None:
    """A running db_postgres container points at its compose file."""
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text("services: {}\n", encoding="utf-8")
    payload = {
        "Id": "abc",
        "Config": {
            "Image": "postgres:15-alpine",
            "Labels": {
                "com.docker.compose.service": "db_postgres",
                "com.docker.compose.project.working_dir": str(tmp_path),
                "com.docker.compose.project.config_files": str(compose),
                "com.docker.compose.project": "docker",
            },
        },
        "State": {"Running": True},
        "Mounts": [],
    }
    found = discovered_from_inspect(payload)
    assert found is not None
    assert found.running is True
    assert found.compose_file == compose
    assert found.service == "db_postgres"


def test_decline_stops_before_the_menu(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """After the paths check, declining leaves the database alone."""
    found = Discovered(
        compose_dir=Path("/tmp/dify"),
        compose_file=Path("/tmp/dify/docker-compose.yaml"),
        project_name="docker",
        service="db_postgres",
        container_id="abc",
        running=True,
    )
    verified = VerifiedPg(
        target=ComposeTarget(
            compose_dir=Path("/tmp/dify"),
            compose_file=Path("/tmp/dify/docker-compose.yaml"),
            project_name="docker",
            db_user="postgres",
            db_name="dify",
            service="db_postgres",
        ),
        compose_file=Path("/tmp/dify/docker-compose.yaml"),
        service="db_postgres",
        database="dify",
        host_data="/tmp/dify/volumes/db/data",
        mount_source="/tmp/dify/volumes/db/data",
        mount_dest="/var/lib/postgresql/data",
        data_directory="/var/lib/postgresql/data/pgdata",
    )
    monkeypatch.setattr("scripts.dify.db_merge.wizard.locate_stacks", lambda: [found])
    monkeypatch.setattr("scripts.dify.db_merge.wizard.verify_stack", lambda _found: verified)
    answers = iter(["n"])
    run_interactive(read=lambda _prompt: next(answers))
    printed = capsys.readouterr().out
    assert "verified" in printed
    assert "docker-compose.yaml" in printed
    assert "What do you want to do?" not in printed


_DIFY_COMPOSE = "\n".join(
    [
        "services:",
        "  db_postgres:",
        "    image: postgres:15-alpine",
        "    volumes:",
        "      - ./volumes/db/data:/var/lib/postgresql/data",
    ]
)


def test_root_scan_finds_dify_and_skips_volumes(tmp_path: Path) -> None:
    """``/root/dify/docker`` is the install; the Postgres volume tree is not searched."""
    install = tmp_path / "dify" / "docker"
    install.mkdir(parents=True)
    (install / "docker-compose.yaml").write_text(_DIFY_COMPOSE, encoding="utf-8")
    hidden = tmp_path / "dify" / "docker" / "volumes" / "db" / "data"
    hidden.mkdir(parents=True)
    (hidden / "docker-compose.yaml").write_text(_DIFY_COMPOSE, encoding="utf-8")
    other = tmp_path / "neodify" / "docker"
    other.mkdir(parents=True)
    (other / "docker-compose.yaml").write_text(_DIFY_COMPOSE, encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")
    found = dify_compose_dirs(tmp_path)
    assert found[0] == install.resolve()
    assert other.resolve() in found
    assert hidden not in found
    assert all("volumes" not in path.parts for path in found)


def test_dump_dir_follows_root_install() -> None:
    """A stack under /root dumps beside it, not into the compose directory."""
    assert default_dump_dir(Path("/root/dify/docker")) == Path("/root/dify-dump")
    assert default_dump_dir(Path("/root/neodify/docker")) == Path("/root/neodify-dump")


def test_single_root_install_is_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One compose file under the server root is used without asking for a path."""
    install = tmp_path / "dify" / "docker"
    install.mkdir(parents=True)
    (install / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")
    verified = VerifiedPg(
        target=ComposeTarget(
            compose_dir=install,
            compose_file=install / "docker-compose.yaml",
            project_name="docker",
            db_user="postgres",
            db_name="dify",
            service="db_postgres",
        ),
        compose_file=install / "docker-compose.yaml",
        service="db_postgres",
        database="dify",
        host_data=str(install / "volumes" / "db" / "data"),
        mount_source=str(install / "volumes" / "db" / "data"),
        mount_dest="/var/lib/postgresql/data",
        data_directory="/var/lib/postgresql/data/pgdata",
    )
    monkeypatch.setattr("scripts.dify.db_merge.wizard.locate_stacks", lambda: [])
    monkeypatch.setattr("scripts.dify.db_merge.wizard.candidate_dify_dirs", lambda: [install])
    monkeypatch.setattr("scripts.dify.db_merge.wizard.verify_stack", lambda _found: verified)
    run_interactive(read=lambda _prompt: "n")
    printed = capsys.readouterr().out
    assert f"Dify compose: {install.resolve() / 'docker-compose.yaml'}" in printed
    assert "Compose directory" not in printed


_COMPARISON_CSV = "\n".join(
    [
        "role,name,conversations_before,conversations_after,messages_before,messages_after,"
        "end_users_before,end_users_after,persona_patched",
        "input,远二启慧星v1.3【远东二小】,12,0,40,0,4,1,12",
        "input,侨智融创 V1.3【华侨中学】,3,0,9,0,2,0,3",
        "output,MindMate,1,16,2,51,1,6,15",
        "",
    ]
)


def test_comparison_lists_before_and_after() -> None:
    """A dry run shows each workflow's counts and whether they balance."""
    report = format_count_comparison(_COMPARISON_CSV, rolled_back=True)
    assert report.balanced is True
    assert "12 -> 0" in report.text
    assert "1 -> 16" in report.text
    assert "1 end users stayed on an input." in report.text
    assert "every moved conversation, message, and end user" in report.text
    gap = _COMPARISON_CSV.replace("1,16,2,51,1,6,15", "1,10,2,51,1,6,15")
    failed = format_count_comparison(gap, rolled_back=True)
    assert failed.balanced is False
    assert "Check failed" in failed.text
    committed = format_count_comparison(gap, rolled_back=False)
    assert "Restore the database dump" in committed.text


def test_workflow_title_parts_match_school_cards() -> None:
    """Studio cards are ``{agent}V1.3【{school}】``. The alias is not in the title."""
    assert workflow_title_parts("远二启慧星v1.3【远东二小】") == ("远二启慧星", "远东二小")
    assert workflow_title_parts("侨智融创 V1.3【华侨中学】") == ("侨智融创", "华侨中学")
    assert workflow_title_parts("融和宝宝V1.3【广州市回民小学】") == ("融和宝宝", "广州市回民小学")
    assert workflow_title_parts("七一思伴V1.3【西安市第七十一中学】") == ("七一思伴", "西安市第七十一中学")
    assert workflow_title_parts("MindMate_test上使用版") is None


def test_merge_asks_for_inputs_then_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """School clones are the inputs. One shared workflow is the merge output."""
    verified = _verified()
    inventory = "\n".join(
        [
            "id,name,mode,conversations,messages",
            f"{SOURCE},远二启慧星v1.3【远东二小】,advanced-chat,12,40",
            f"{OTHER},侨智融创 V1.3【华侨中学】,advanced-chat,3,9",
            f"{TARGET},MindMate,advanced-chat,0,0",
        ]
    )
    plans: list[MergePlan] = []
    monkeypatch.setattr("scripts.dify.db_merge.wizard.locate_stacks", lambda: [_discovered()])
    monkeypatch.setattr("scripts.dify.db_merge.wizard.verify_stack", lambda _found: verified)
    monkeypatch.setattr("scripts.dify.db_merge.wizard.list_apps", lambda _target, _timeout: inventory)

    def remember_plan(_target: object, plan: MergePlan, _timeout: int) -> str:
        plans.append(plan)
        return "-- sql\n"

    monkeypatch.setattr("scripts.dify.db_merge.wizard.merge_script", remember_plan)
    monkeypatch.setattr("scripts.dify.db_merge.wizard.execute_sql", lambda _t, _sql, _timeout: _COMPARISON_CSV)
    prompts: list[str] = []
    answers = iter(["y", "1", "1,2", "3", "y", "", "启慧", "", "", "", "", "1", "3"])

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    run_interactive(read=read)
    printed = capsys.readouterr().out
    assert prompts.index("Input workflows (comma-separated numbers, for example 1,3,8): ") < prompts.index(
        "Final merge output (one number): "
    )
    assert "远二启慧星v1.3【远东二小】" in printed
    assert "侨智融创 V1.3【华侨中学】" in printed
    assert "Output: MindMate" in printed
    assert "Dry run or actual run?" in printed
    assert "Dry run. Rolled back. The after numbers were not saved." in printed
    assert "Actual run." not in printed
    assert "远二启慧星v1.3【远东二小】  (input)" in printed
    assert "conversations    12 -> 0" in printed
    assert "Commit this move" not in prompts
    assert len(plans) == 1
    plan = plans[0]
    assert plan.target_app_id == TARGET
    assert plan.execute is False
    assert plan.sources[0].persona["mg_agent_name"] == "远二启慧星"
    assert plan.sources[0].persona["mg_agent_alias"] == "启慧"
    assert plan.sources[0].persona["mg_school_name"] == "远东二小"
    assert plan.sources[1].persona["mg_agent_name"] == "侨智融创"
    assert plan.sources[1].persona["mg_agent_alias"] == "侨智融创"
    assert plan.sources[1].app_id == OTHER


def test_actual_run_dumps_before_it_writes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """An actual run saves a dump before it commits, unless the operator declines."""
    inventory = "\n".join(
        [
            "id,name,mode,conversations,messages",
            f"{SOURCE},远二启慧星v1.3【远东二小】,advanced-chat,12,40",
            f"{TARGET},MindMate,advanced-chat,0,0",
        ]
    )
    order: list[str] = []
    monkeypatch.setattr("scripts.dify.db_merge.wizard.locate_stacks", lambda: [_discovered()])
    monkeypatch.setattr("scripts.dify.db_merge.wizard.verify_stack", lambda _found: _verified())
    monkeypatch.setattr("scripts.dify.db_merge.wizard.list_apps", lambda _target, _timeout: inventory)

    def remember_dump(_target: object, _out: object, _timeout: int) -> tuple[str, str, str]:
        order.append("dump")
        return "dump-path", "apps-path", "id,name\n"

    def remember_sql(_target: object, _sql: str, _timeout: int) -> str:
        order.append("sql")
        return _COMPARISON_CSV

    monkeypatch.setattr("scripts.dify.db_merge.wizard.dump_database", remember_dump)
    monkeypatch.setattr("scripts.dify.db_merge.wizard.merge_script", lambda _t, _plan, _timeout: "-- sql\n")
    monkeypatch.setattr("scripts.dify.db_merge.wizard.execute_sql", remember_sql)
    answers = iter(["y", "1", "1", "2", "y", "", "", "", "2", "", "MindMate", "3"])
    run_interactive(read=lambda _prompt: next(answers))
    printed = capsys.readouterr().out
    assert order == ["dump", "sql"]
    assert "Actual run. The output workflow has the moved chat." in printed
    assert "No new dump." not in printed


def test_output_workflow_cannot_also_be_an_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared workflow is the destination, so it is not also a source."""
    inventory = "\n".join(
        [
            "id,name,mode,conversations,messages",
            f"{SOURCE},远二启慧星v1.3【远东二小】,advanced-chat,1,1",
            f"{TARGET},MindMate,advanced-chat,0,0",
        ]
    )
    monkeypatch.setattr("scripts.dify.db_merge.wizard.locate_stacks", lambda: [_discovered()])
    monkeypatch.setattr("scripts.dify.db_merge.wizard.verify_stack", lambda _found: _verified())
    monkeypatch.setattr("scripts.dify.db_merge.wizard.list_apps", lambda _target, _timeout: inventory)
    answers = iter(["y", "1", "1", "1"])
    with pytest.raises(PlanError, match="output workflow cannot also be an input"):
        run_interactive(read=lambda _prompt: next(answers))


def _discovered() -> Discovered:
    return Discovered(
        compose_dir=Path("/tmp/dify"),
        compose_file=Path("/tmp/dify/docker-compose.yaml"),
        project_name="docker",
        service="db_postgres",
        container_id="abc",
        running=True,
    )


def _verified() -> VerifiedPg:
    return VerifiedPg(
        target=ComposeTarget(
            compose_dir=Path("/tmp/dify"),
            compose_file=Path("/tmp/dify/docker-compose.yaml"),
            project_name="docker",
            db_user="postgres",
            db_name="dify",
            service="db_postgres",
        ),
        compose_file=Path("/tmp/dify/docker-compose.yaml"),
        service="db_postgres",
        database="dify",
        host_data="/tmp/dify/volumes/db/data",
        mount_source="/tmp/dify/volumes/db/data",
        mount_dest="/var/lib/postgresql/data",
        data_directory="/var/lib/postgresql/data/pgdata",
    )
