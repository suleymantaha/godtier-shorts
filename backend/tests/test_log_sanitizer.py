from __future__ import annotations

from backend.core.log_sanitizer import sanitize_log_value, sanitize_subject


def test_sanitize_log_value_redacts_workspace_paths() -> None:
    message = "Klip bulunamadi: /home/arch/godtier-shorts/workspace/projects/proj_1/shorts/clip_1.mp4"

    sanitized = sanitize_log_value(message)

    assert sanitized == "Klip bulunamadi: [redacted-path]"


def test_sanitize_log_value_recurses_into_nested_payloads() -> None:
    payload = {
        "error": "Video bulunamadi: /home/arch/godtier-shorts/workspace/projects/proj_2/master.mp4",
        "items": ["/home/arch/godtier-shorts/workspace/projects/proj_2/transcript.json"],
    }

    sanitized = sanitize_log_value(payload)

    assert sanitized["error"] == "Video bulunamadi: [redacted-path]"
    assert sanitized["items"] == ["[redacted-path]"]


def test_sanitize_subject_returns_stable_fingerprint() -> None:
    assert sanitize_subject("user_a") == sanitize_subject("user_a")
    assert sanitize_subject("user_a") != sanitize_subject("user_b")
    assert sanitize_subject("anonymous") == "anonymous"
