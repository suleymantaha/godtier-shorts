from __future__ import annotations

from backend.core.render_quality import compute_render_quality_score, merge_transcript_quality


def test_merge_transcript_quality_marks_overflow_as_degraded() -> None:
    merged = merge_transcript_quality(
        base_quality={
            "status": "good",
            "word_coverage_ratio": 0.92,
            "segments_without_words": 0,
            "empty_text_segments_after_rebuild": 0,
        },
        subtitle_layout_quality={
            "subtitle_overflow_detected": True,
            "max_rendered_line_width_ratio": 1.12,
            "safe_area_violation_count": 1,
        },
        snapping_report={"boundary_snaps_applied": 1, "word_coverage_ratio": 0.92},
    )

    assert merged["status"] == "degraded"
    assert merged["boundary_snaps_applied"] == 1


def test_compute_render_quality_score_caps_fallback_tracking() -> None:
    score = compute_render_quality_score(
        tracking_quality={
            "status": "fallback",
            "mode": "tracked",
            "total_frames": 100,
            "fallback_frames": 80,
            "avg_center_jump_px": 22,
        },
        transcript_quality={
            "status": "good",
            "word_coverage_ratio": 0.95,
            "clamped_words_count": 0,
            "empty_text_segments_after_rebuild": 0,
            "subtitle_overflow_detected": False,
            "max_rendered_line_width_ratio": 0.7,
            "safe_area_violation_count": 0,
        },
        debug_timing={
            "merged_output_drift_ms": 0,
            "dropped_or_duplicated_frame_estimate": 0,
        },
        subtitle_layout_quality={
            "subtitle_overflow_detected": False,
            "max_rendered_line_width_ratio": 0.7,
            "safe_area_violation_count": 0,
        },
    )

    assert score <= 69
