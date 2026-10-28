from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_inventory_classifies_candidates_without_marking_them_safe_to_delete(tmp_path):
    objects = tmp_path / "objects.jsonl"
    refs = tmp_path / "references.jsonl"
    objects.write_text('\n'.join(json.dumps(row) for row in [
        {"key": "uploads/user/tracked.mp4", "size_bytes": 6},
        {"key": "outputs/user/job/legacy.mp4", "size_bytes": 4},
        {"key": "unexpected/file", "size_bytes": 2},
    ]))
    refs.write_text(json.dumps({"key": "uploads/user/tracked.mp4", "size_bytes": 6}))
    result = subprocess.run([sys.executable, "scripts/storage_orphan_inventory.py", "--objects", str(objects), "--references", str(refs), "--max-objects", "3"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert [row["classification"] for row in rows] == ["tracked", "unreferenced_candidate", "unknown_namespace"]
    assert all(row["deletion_authorized"] is False for row in rows)
    assert objects.read_text().count("size_bytes") == 3


def test_inventory_refuses_truncated_or_inconsistent_accounting(tmp_path):
    objects = tmp_path / "objects.jsonl"
    refs = tmp_path / "references.jsonl"
    objects.write_text('{"key":"uploads/u/a.mp4","size_bytes":7}\n')
    refs.write_text('{"key":"uploads/u/a.mp4","size_bytes":6}\n')
    result = subprocess.run([sys.executable, "scripts/storage_orphan_inventory.py", "--objects", str(objects), "--references", str(refs), "--max-objects", "1"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["classification"] == "size_mismatch"
    result = subprocess.run([sys.executable, "scripts/storage_orphan_inventory.py", "--objects", str(objects), "--references", str(refs), "--max-objects", "0"], capture_output=True, text=True)
    assert result.returncode != 0
