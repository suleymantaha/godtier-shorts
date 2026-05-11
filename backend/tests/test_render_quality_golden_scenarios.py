from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.core.workflow_artifacts import assess_layout_safety


GOLDEN_RENDER_SCENARIOS = [
    {
        "name": "problem_clip_listener_lock_requires_auto_repair",
        "render_plan": SimpleNamespace(
            resolved_layout="single",
            layout_safety_status="safe",
            layout_safety_mode="shadow",
            layout_safety_contract_version=1,
            layout_fallback_reason="split_not_stable",
            layout_auto_fix_reason="split_face_safety",
            layout_auto_fix_applied=True,
            scene_class="dual_overlap_risky",
            speaker_count_peak=3,
            dominant_speaker_confidence=None,
        ),
        "requested_layout": "auto",
        "tracking_quality": {
            "status": "good",
            "listener_lock_suspected": True,
            "listener_lock_suspected_frames": 6,
            "startup_settle_ms": 500.0,
            "speaker_switch_count": 1,
            "speaker_activity_confidence": 0.5037,
        },
        "expected_publication_status": "auto_repair",
        "expected_reasons": {
            "listener_lock_suspected",
            "startup_settle_slow",
            "split_layout_fallback",
            "multi_person_overlap_risky",
        },
    },
    {
        "name": "clean_single_speaker_is_publish_ready",
        "render_plan": SimpleNamespace(
            resolved_layout="single",
            layout_safety_status="safe",
            layout_safety_mode="shadow",
            layout_safety_contract_version=1,
            layout_fallback_reason=None,
            layout_auto_fix_reason=None,
            layout_auto_fix_applied=False,
            scene_class="single_dynamic",
            speaker_count_peak=1,
            dominant_speaker_confidence=None,
        ),
        "requested_layout": "auto",
        "tracking_quality": {
            "status": "good",
            "listener_lock_suspected": False,
            "startup_settle_ms": 0.0,
            "identity_confidence": 0.98,
        },
        "expected_publication_status": "publish_ready",
        "expected_reasons": set(),
    },
    {
        "name": "unsafe_split_requires_review",
        "render_plan": SimpleNamespace(
            resolved_layout="split",
            layout_safety_status="safe",
            layout_safety_mode="enforce",
            layout_safety_contract_version=1,
            layout_fallback_reason=None,
            layout_auto_fix_reason=None,
            layout_auto_fix_applied=False,
            scene_class="dual_separated",
            speaker_count_peak=2,
            dominant_speaker_confidence=None,
        ),
        "requested_layout": "split",
        "tracking_quality": {
            "status": "good",
            "panel_swap_count": 1,
            "unsafe_split_frames": 4,
        },
        "expected_publication_status": "review_required",
        "expected_reasons": {"split_runtime_unsafe"},
    },
]


@pytest.mark.parametrize(
    "scenario",
    GOLDEN_RENDER_SCENARIOS,
    ids=[scenario["name"] for scenario in GOLDEN_RENDER_SCENARIOS],
)
def test_golden_render_quality_scenarios_hold_publication_contract(scenario: dict) -> None:
    safety = assess_layout_safety(
        render_plan=scenario["render_plan"],
        requested_layout=str(scenario["requested_layout"]),
        tracking_quality=dict(scenario["tracking_quality"]),
        manual_center_x=None,
    )

    assert safety["render_publication_status"] == scenario["expected_publication_status"]
    assert set(safety["quality_gate_reasons"]) == scenario["expected_reasons"]
