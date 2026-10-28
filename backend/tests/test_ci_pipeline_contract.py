"""Contract tests for the production CI build and deploy gates (Task 23)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
VERIFY_WORKFLOW = WORKFLOWS / "verify.yml"
DEPLOY_WORKFLOW = WORKFLOWS / "deploy.yml"
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_production.sh"
MIGRATION_SAFETY_SCRIPT = ROOT / "scripts" / "check_migration_safety.py"


def _load_workflow(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _job_script(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))


def _load_migration_safety_module():
    spec = importlib.util.spec_from_file_location(
        "check_migration_safety", MIGRATION_SAFETY_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- PR gate ------------------------------------------------------------


def test_pr_gate_runs_tests_security_and_both_production_image_builds() -> None:
    workflow = _load_workflow(VERIFY_WORKFLOW)

    assert {"verify", "security", "docker-api", "docker-gpu"} <= set(workflow["jobs"])


def test_pr_gate_installs_ffmpeg_before_media_tests() -> None:
    steps = _load_workflow(VERIFY_WORKFLOW)["jobs"]["verify"]["steps"]
    install = next((i for i, step in enumerate(steps) if "apt-get install -y ffmpeg" in str(step.get("run", ""))), None)
    verify = next(i for i, step in enumerate(steps) if "scripts/verify.sh" in str(step.get("run", "")))

    assert install is not None and install < verify


def test_pr_gate_exercises_account_purge_on_postgres() -> None:
    env = _load_workflow(VERIFY_WORKFLOW)["jobs"]["verify"]["env"]

    assert env["ACCOUNT_PURGE_TEST_DATABASE_URL"] == env["TEST_DATABASE_URL"]


def test_verify_avoids_duplicate_push_and_pr_runs_for_feature_branches() -> None:
    workflow = _load_workflow(VERIFY_WORKFLOW)
    triggers = workflow.get("on", workflow.get(True))

    assert triggers["push"]["branches"] == ["main"]
    assert "pull_request" in triggers


def test_pr_gate_security_job_audits_dependencies_and_migrations() -> None:
    script = _job_script(_load_workflow(VERIFY_WORKFLOW)["jobs"]["security"])

    assert "pip_audit" in script or "pip-audit" in script
    assert "npm audit" in script
    assert "scripts/check_migration_safety.py" in script


def test_pr_gate_builds_gpu_image_without_requiring_a_gpu_runner() -> None:
    workflow = _load_workflow(VERIFY_WORKFLOW)
    gpu_job = workflow["jobs"]["docker-gpu"]

    assert gpu_job["runs-on"] == "ubuntu-latest"
    assert "Dockerfile.gpu" in yaml.safe_dump(gpu_job)
    assert "nvidia-smi" not in yaml.safe_dump(gpu_job)


def test_pr_gate_image_builds_do_not_push_to_the_registry() -> None:
    workflow = _load_workflow(VERIFY_WORKFLOW)

    for job_name in ("docker-api", "docker-gpu"):
        rendered = yaml.safe_dump(workflow["jobs"][job_name])
        assert "push: true" not in rendered
        assert "docker push" not in rendered


# --- Deploy gate --------------------------------------------------------


def test_deploy_runs_only_after_the_verify_gate_succeeds_on_main() -> None:
    workflow = _load_workflow(DEPLOY_WORKFLOW)
    # PyYAML parses a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))

    assert triggers["workflow_run"]["workflows"] == ["Verify"]
    assert triggers["workflow_run"]["types"] == ["completed"]

    guard = " ".join(DEPLOY_WORKFLOW.read_text(encoding="utf-8").split())
    assert "github.event.workflow_run.conclusion == 'success'" in guard
    assert "github.event.workflow_run.head_branch == 'main'" in guard

    for job_name in ("publish-api", "publish-gpu"):
        job_guard = workflow["jobs"][job_name]["if"]
        assert "github.event.workflow_run.event == 'push'" in job_guard
        assert "github.event.workflow_run.head_repository.full_name == github.repository" in job_guard


def test_deploy_publishes_both_images_to_ghcr_with_immutable_sha_tags() -> None:
    rendered = yaml.safe_dump(_load_workflow(DEPLOY_WORKFLOW))

    assert "ghcr.io" in rendered
    assert "Dockerfile.api" in rendered
    assert "Dockerfile.gpu" in rendered
    assert "github.event.workflow_run.head_sha" in rendered


def test_deploy_job_waits_for_both_published_images() -> None:
    jobs = _load_workflow(DEPLOY_WORKFLOW)["jobs"]

    assert set(jobs["deploy"]["needs"]) == {"publish-api", "publish-gpu"}


def test_deploy_workflow_reads_every_credential_from_secrets() -> None:
    rendered = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    for marker in ("DEPLOY_SSH_KEY", "DEPLOY_HOST", "DEPLOY_USER"):
        assert f"secrets.{marker}" in rendered
    assert "BEGIN OPENSSH PRIVATE KEY" not in rendered

    for line in rendered.splitlines():
        stripped = line.strip()
        if stripped.startswith("password:"):
            assert "secrets." in stripped, stripped


# --- Server-side deploy script -----------------------------------------


def test_deploy_script_fails_closed() -> None:
    assert "set -euo pipefail" in DEPLOY_SCRIPT.read_text(encoding="utf-8")


def test_deploy_script_backs_up_before_migrating_then_health_checks() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    backup = script.index("pg_dump")
    migrate = script.index("alembic")
    health = script.index("/health/ready")

    assert backup < migrate < health


def test_deploy_script_keeps_dotenv_values_out_of_the_shell() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "source .env" not in script
    assert 'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' in script
    assert 'port api 8000' in script


def test_deploy_script_rejects_a_server_compose_without_the_release_image() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert 'config --images' in script
    assert 'grep -Fxq -- "$API_IMAGE"' in script


def test_deploy_script_rolls_back_the_application_when_health_fails() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "rollback" in script.lower()
    assert "PREVIOUS_API_IMAGE" in script


def test_deploy_script_never_downgrades_the_database() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "alembic downgrade" not in script


# --- Destructive migration ban -----------------------------------------


def test_repository_migrations_pass_the_destructive_upgrade_ban() -> None:
    result = subprocess.run(
        [sys.executable, str(MIGRATION_SAFETY_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_destructive_upgrade_is_rejected(tmp_path: Path) -> None:
    module = _load_migration_safety_module()
    migration = tmp_path / "0099_bad.py"
    migration.write_text(
        "def upgrade() -> None:\n"
        "    op.drop_column('jobs', 'user_id')\n"
        "\n"
        "def downgrade() -> None:\n"
        "    op.drop_table('jobs')\n",
        encoding="utf-8",
    )

    findings = module.find_destructive_operations(migration)

    assert any("drop_column" in finding.operation for finding in findings)


def test_downgrade_only_destruction_is_allowed(tmp_path: Path) -> None:
    module = _load_migration_safety_module()
    migration = tmp_path / "0100_ok.py"
    migration.write_text(
        "def upgrade() -> None:\n"
        "    op.create_table('demo')\n"
        "\n"
        "def downgrade() -> None:\n"
        "    op.drop_table('demo')\n",
        encoding="utf-8",
    )

    assert module.find_destructive_operations(migration) == []


def test_raw_destructive_sql_in_upgrade_is_rejected(tmp_path: Path) -> None:
    module = _load_migration_safety_module()
    migration = tmp_path / "0101_raw.py"
    migration.write_text(
        "def upgrade() -> None:\n"
        "    op.execute('TRUNCATE TABLE credit_ledger')\n",
        encoding="utf-8",
    )

    findings = module.find_destructive_operations(migration)

    assert findings
