from __future__ import annotations

import numpy as np
import pytest

from backend.services.video_processor import DetectionCandidate, TrackSlotState, TrackingDiagnostics, VideoProcessor


def test_is_split_layout_stable_requires_majority_of_sampled_frames() -> None:
    stable = VideoProcessor._is_split_layout_stable(
        [
            (1920, [300.0, 900.0]),
            (1920, [320.0, 930.0]),
            (1920, [340.0]),
            (1920, [350.0, 980.0]),
            (1920, []),
        ]
    )
    assert stable is True


def test_is_split_layout_stable_rejects_close_centers() -> None:
    stable = VideoProcessor._is_split_layout_stable(
        [
            (1920, [500.0, 700.0]),
            (1920, [510.0, 690.0]),
            (1920, [520.0, 710.0]),
        ]
    )
    assert stable is False


def test_is_split_layout_stable_requires_distribution_across_clip_regions() -> None:
    frame_results = []
    for sample_index in range(16):
        centers = [320.0, 1220.0] if sample_index < 10 else [640.0]
        frame_results.append((1920, centers, sample_index, 16))

    assert VideoProcessor._is_split_layout_stable(frame_results) is False


def test_is_split_layout_stable_accepts_uniformly_distributed_two_person_frames() -> None:
    frame_results = [
        (1920, [300.0, 1300.0], sample_index, 16)
        for sample_index in range(16)
    ]

    assert VideoProcessor._is_split_layout_stable(frame_results) is True


def test_resolve_layout_for_segment_uses_auto_split_when_clip_is_stable(monkeypatch) -> None:
    processor = VideoProcessor(device="cpu")
    frames = [np.zeros((1080, 1920, 3), dtype=np.uint8) for _ in range(16)]
    frame_iter = iter(frames)

    monkeypatch.setattr(processor, "_ensure_model_loaded", lambda: None)
    monkeypatch.setattr(processor, "_extract_probe_frame", lambda _path, _time: next(frame_iter, None))
    monkeypatch.setattr(processor, "_detect_person_centers", lambda _frame: [320.0, 1320.0])

    layout, reason = processor.resolve_layout_for_segment(
        input_video="clip.mp4",
        start_time=0.0,
        end_time=24.0,
        requested_layout="auto",
    )

    assert layout == "split"
    assert reason is None


def test_resolve_layout_for_segment_allows_stable_dominant_pair_with_extra_person(monkeypatch) -> None:
    processor = VideoProcessor(device="cpu")
    frames = [np.zeros((1080, 1920, 3), dtype=np.uint8) for _ in range(16)]
    frame_iter = iter(frames)
    candidates = [
        DetectionCandidate(
            track_id=1,
            box=(160.0, 100.0, 600.0, 960.0),
            center_x=380.0,
            area=378400.0,
            confidence=0.94,
            aspect_ratio=0.51,
            visibility_score=0.9,
        ),
        DetectionCandidate(
            track_id=2,
            box=(1180.0, 120.0, 1640.0, 980.0),
            center_x=1410.0,
            area=395600.0,
            confidence=0.93,
            aspect_ratio=0.53,
            visibility_score=0.89,
        ),
        DetectionCandidate(
            track_id=3,
            box=(860.0, 280.0, 980.0, 640.0),
            center_x=920.0,
            area=43200.0,
            confidence=0.61,
            aspect_ratio=0.33,
            visibility_score=0.5,
        ),
    ]

    monkeypatch.setattr(processor, "_ensure_model_loaded", lambda: None)
    monkeypatch.setattr(processor, "_extract_probe_frame", lambda _path, _time: next(frame_iter, None))
    monkeypatch.setattr(processor, "_detect_person_centers", lambda _frame: [380.0, 920.0, 1410.0])
    monkeypatch.setattr(processor, "_predict_people", lambda _frame: list(candidates))

    report = processor.resolve_layout_for_segment(
        input_video="clip.mp4",
        start_time=0.0,
        end_time=24.0,
        requested_layout="auto",
    )

    assert report.resolved_layout == "split"
    assert report.scene_class == "multi_person_dominant_pair"
    assert report.speaker_count_peak == 3


def test_video_processor_requires_cuda_when_flag_enabled(monkeypatch) -> None:
    processor = VideoProcessor(device="cuda")

    class FakeModel:
        def to(self, _device: str) -> None:
            raise AssertionError("should not reach model.to when CUDA is required but unavailable")

    monkeypatch.setattr("backend.services.video_processor.YOLO", lambda _path: FakeModel())
    monkeypatch.setattr("backend.services.video_processor.torch.cuda.is_available", lambda: False)
    monkeypatch.setenv("REQUIRE_CUDA_FOR_APP", "1")

    with pytest.raises(RuntimeError, match="CUDA zorunlu"):
        processor._ensure_model_loaded()


def test_analyze_opening_shot_reports_delayed_subject_visibility(monkeypatch) -> None:
    processor = VideoProcessor(device="cpu")
    frames = [np.zeros((1080, 1920, 3), dtype=np.uint8) for _ in range(6)]
    frame_iter = iter(frames)
    visible_candidate = DetectionCandidate(
        track_id=1,
        box=(500.0, 120.0, 840.0, 900.0),
        center_x=670.0,
        area=265200.0,
        confidence=0.92,
        aspect_ratio=0.43,
        visibility_score=0.88,
    )
    detections = iter([[], [], [visible_candidate], [visible_candidate], [visible_candidate], [visible_candidate]])

    monkeypatch.setattr(processor, "_ensure_model_loaded", lambda: None)
    monkeypatch.setattr(processor, "_extract_probe_frame", lambda _path, _time: next(frame_iter, None))
    monkeypatch.setattr(processor, "_predict_people", lambda _frame: list(next(detections)))

    report = processor.analyze_opening_shot(
        input_video="clip.mp4",
        start_time=10.0,
        end_time=20.0,
        resolved_layout="single",
    )

    assert report["layout_validation_status"] == "opening_subject_delayed"
    assert float(report["suggested_start_time"]) > 10.0
    assert float(report["opening_visibility_delay_ms"]) > 500.0


def test_analyze_opening_shot_split_returns_initial_slot_centers(monkeypatch) -> None:
    processor = VideoProcessor(device="cpu")
    frames = [np.zeros((1080, 1920, 3), dtype=np.uint8) for _ in range(6)]
    frame_iter = iter(frames)
    left_candidate = DetectionCandidate(
        track_id=1,
        box=(180.0, 120.0, 620.0, 980.0),
        center_x=400.0,
        area=378400.0,
        confidence=0.94,
        aspect_ratio=0.51,
        visibility_score=0.92,
    )
    right_candidate = DetectionCandidate(
        track_id=2,
        box=(1180.0, 130.0, 1640.0, 990.0),
        center_x=1410.0,
        area=395600.0,
        confidence=0.93,
        aspect_ratio=0.53,
        visibility_score=0.9,
    )

    monkeypatch.setattr(processor, "_ensure_model_loaded", lambda: None)
    monkeypatch.setattr(processor, "_extract_probe_frame", lambda _path, _time: next(frame_iter, None))
    monkeypatch.setattr(processor, "_predict_people", lambda _frame: [left_candidate, right_candidate])

    report = processor.analyze_opening_shot(
        input_video="clip.mp4",
        start_time=0.0,
        end_time=12.0,
        resolved_layout="split",
    )

    assert report["layout_validation_status"] == "ok"
    assert report["initial_slot_centers"] == [400.0, 1410.0]


def test_stabilize_tracking_center_waits_for_split_sustained_motion() -> None:
    processor = VideoProcessor(device="cpu")
    state = TrackSlotState("primary", 640.0)

    first = processor._stabilize_tracking_center(
        state=state,
        target_cx=720.0,
        frame_width=1920,
        layout="split",
        mode="tracked",
        tracker_weak=False,
    )
    second = processor._stabilize_tracking_center(
        state=state,
        target_cx=720.0,
        frame_width=1920,
        layout="split",
        mode="tracked",
        tracker_weak=False,
    )
    third = processor._stabilize_tracking_center(
        state=state,
        target_cx=720.0,
        frame_width=1920,
        layout="split",
        mode="tracked",
        tracker_weak=False,
    )

    assert first[0] == 640.0
    assert first[1] is True
    assert second[0] == 640.0
    assert third[0] > 640.0
    assert third[1] is False


def test_stabilize_tracking_center_uses_nearly_static_split_when_tracker_is_weak() -> None:
    processor = VideoProcessor(device="cpu")
    state = TrackSlotState("secondary", 640.0)

    for _ in range(3):
        stabilized = processor._stabilize_tracking_center(
            state=state,
            target_cx=820.0,
            frame_width=1920,
            layout="split",
            mode="tracked",
            tracker_weak=True,
        )
        assert stabilized[0] == 640.0
        assert stabilized[1] is True

    fourth = processor._stabilize_tracking_center(
        state=state,
        target_cx=820.0,
        frame_width=1920,
        layout="split",
        mode="tracked",
        tracker_weak=True,
    )

    assert fourth[0] > 640.0
    assert fourth[1] is False


def test_active_speaker_switch_confirms_after_two_consistent_frames() -> None:
    processor = VideoProcessor(device="cpu")
    state = TrackSlotState("primary", 500.0, confirmed_track_id=1)
    diagnostics = TrackingDiagnostics(mode="tracked", fps=30.0, layout="single")
    current = DetectionCandidate(
        track_id=1,
        box=(300.0, 120.0, 700.0, 900.0),
        center_x=500.0,
        area=312000.0,
        confidence=0.92,
        aspect_ratio=0.51,
        visibility_score=0.9,
        motion_score=0.08,
        mouth_motion_score=0.08,
    )
    challenger = DetectionCandidate(
        track_id=2,
        box=(1120.0, 120.0, 1520.0, 900.0),
        center_x=1320.0,
        area=312000.0,
        confidence=0.91,
        aspect_ratio=0.51,
        visibility_score=0.88,
        motion_score=0.58,
        mouth_motion_score=0.58,
    )

    first = processor._select_active_speaker_switch_candidate(
        state=state,
        same_id_candidate=current,
        candidates=[current, challenger],
        diagnostics=diagnostics,
        layout="single",
    )
    second = processor._select_active_speaker_switch_candidate(
        state=state,
        same_id_candidate=current,
        candidates=[current, challenger],
        diagnostics=diagnostics,
        layout="single",
    )

    assert first is None
    assert second == challenger


def test_active_speaker_catchup_moves_fast_enough_for_visible_switch() -> None:
    processor = VideoProcessor(device="cpu")
    state = TrackSlotState("primary", 500.0)
    state.active_speaker_catchup_frames_remaining = 12

    next_center, movement_suppressed, _deadzone_hit, _sustained_frames = processor._stabilize_tracking_center(
        state=state,
        target_cx=900.0,
        frame_width=1920,
        layout="single",
        mode="tracked",
        tracker_weak=False,
    )

    assert movement_suppressed is False
    assert next_center - 500.0 >= 95.0


def test_tracking_diagnostics_merge_reports_split_jitter_metrics() -> None:
    primary = TrackingDiagnostics(mode="tracked", fps=30.0, layout="split")
    secondary = TrackingDiagnostics(mode="tracked", fps=30.0, layout="split")
    primary.total_frames = 10
    secondary.total_frames = 10
    primary.jump_samples = [1.0, 3.0, 14.0, 15.0]
    secondary.jump_samples = [1.0, 2.0, 4.0, 5.0]
    primary.total_center_jump_px = sum(primary.jump_samples)
    secondary.total_center_jump_px = sum(secondary.jump_samples)
    merged = TrackingDiagnostics.merge(primary, secondary, panel_swap_count=0)

    assert merged["status"] == "degraded"
    assert merged["primary_p95_center_jump_px"] >= 14.0
    assert merged["secondary_p95_center_jump_px"] >= 4.0
    assert merged["split_motion_policy"] == "stable"


def test_build_h264_encoder_args_prefers_cpu_when_nvenc_disabled() -> None:
    assert VideoProcessor._build_h264_encoder_args(prefer_nvenc=False) == [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
    ]


def test_build_h264_encoder_args_uses_nvenc_when_enabled() -> None:
    assert VideoProcessor._build_h264_encoder_args(prefer_nvenc=True) == [
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p6",
        "-b:v",
        "8M",
    ]


def test_track_people_falls_back_to_predict_when_lap_is_missing(monkeypatch) -> None:
    processor = VideoProcessor(device="cpu")
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    class _FakeModel:
        def track(self, *_args, **_kwargs):
            raise ModuleNotFoundError("No module named 'lap'", name="lap")

    fallback_candidate = DetectionCandidate(
        track_id=99,
        box=(100.0, 100.0, 300.0, 900.0),
        center_x=200.0,
        area=160000.0,
        confidence=0.9,
        aspect_ratio=0.25,
        visibility_score=0.8,
    )
    import typing
    processor.model = typing.cast(typing.Any, _FakeModel())
    monkeypatch.setattr(processor, "_predict_people", lambda _frame: [fallback_candidate])

    candidates = processor._track_people(frame)

    assert candidates == [fallback_candidate]
    assert processor._tracker_available is False


def test_tracking_stride_uses_sampling_on_cpu_or_predict_fallback() -> None:
    processor = VideoProcessor(device="cpu")
    assert processor._tracking_stride() == 3
    processor._device = "cuda"
    processor._tracker_available = False
    assert processor._tracking_stride() == 3
    processor._tracker_available = True
    assert processor._tracking_stride() == 1


def test_single_tracking_switches_from_listener_to_confirmed_active_speaker() -> None:
    processor = VideoProcessor(device="cpu")
    state = TrackSlotState(
        "primary",
        1440.0,
        confirmed_track_id=1,
        last_confirmed_box=(960.0, 220.0, 1915.0, 915.0),
        last_confirmed_center=1440.0,
        last_confirmed_area=663725.0,
        last_confirmed_aspect_ratio=955.0 / 695.0,
        last_visibility_score=0.61,
    )
    diagnostics = TrackingDiagnostics(mode="tracked", fps=30.0, layout="single")
    listener = DetectionCandidate(
        track_id=1,
        box=(960.0, 220.0, 1915.0, 915.0),
        center_x=1440.0,
        area=663725.0,
        confidence=0.96,
        aspect_ratio=955.0 / 695.0,
        visibility_score=0.61,
        mouth_motion_score=0.02,
    )
    speaker = DetectionCandidate(
        track_id=2,
        box=(70.0, 205.0, 955.0, 915.0),
        center_x=512.5,
        area=628350.0,
        confidence=0.94,
        aspect_ratio=885.0 / 710.0,
        visibility_score=0.62,
        mouth_motion_score=0.92,
    )

    for frame_index in range(3):
        processor._process_tracking_slot(
            state=state,
            candidates=[listener, speaker],
            frame_width=1920,
            frame_height=1080,
            panel_center=960.0,
            diagnostics=diagnostics,
            layout="single",
            frame_index=frame_index,
            cut_confidence=0.0,
            crop_width=608,
        )

    assert state.confirmed_track_id == 2
    assert state.current_cx < 1400.0
    assert diagnostics.active_track_id_switches == 1


def test_high_priority_diarization_switching_and_dynamic_calibration() -> None:
    from backend.services.diarization import DiarizationEntry
    processor = VideoProcessor(device="cpu")
    
    # Başlangıç durumu: Track ID 1 takip ediliyor
    state = TrackSlotState(
        "primary",
        1440.0,
        confirmed_track_id=1,
    )
    diagnostics = TrackingDiagnostics(mode="tracked", fps=30.0, layout="single")
    
    # Speaker map: SPEAKER_01 -> track_id 2
    speaker_track_map = {"SPEAKER_01": 2}
    diarization_index = [
        DiarizationEntry(start=0.0, end=5.0, speaker="SPEAKER_01"),
    ]
    
    # Ekranda 2 aday var
    cand_1 = DetectionCandidate(
        track_id=1,
        box=(960.0, 220.0, 1915.0, 915.0),
        center_x=1440.0,
        area=663725.0,
        confidence=0.96,
        aspect_ratio=1.0,
        visibility_score=0.9,
        mouth_motion_score=0.01,
    )
    cand_2 = DetectionCandidate(
        track_id=2,
        box=(70.0, 205.0, 955.0, 915.0),
        center_x=512.5,
        area=628350.0,
        confidence=0.94,
        aspect_ratio=1.0,
        visibility_score=0.9,
        mouth_motion_score=0.1,
    )
    
    # 1. kare: Geçiş isteği başlatılır (streak=1)
    processor._process_tracking_slot(
        state=state,
        candidates=[cand_1, cand_2],
        frame_width=1920,
        frame_height=1080,
        panel_center=960.0,
        diagnostics=diagnostics,
        layout="single",
        frame_index=1,
        cut_confidence=0.0,
        crop_width=608,
        diarization_index=diarization_index,
        frame_time=1.0,
        speaker_track_map=speaker_track_map,
    )
    assert state.confirmed_track_id == 1  # Henüz geçilmedi (streak=1 < 2)
    
    # 2. kare: Geçiş onaylanır (streak=2 >= 2) ve geçilir
    processor._process_tracking_slot(
        state=state,
        candidates=[cand_1, cand_2],
        frame_width=1920,
        frame_height=1080,
        panel_center=960.0,
        diagnostics=diagnostics,
        layout="single",
        frame_index=2,
        cut_confidence=0.0,
        crop_width=608,
        diarization_index=diarization_index,
        frame_time=1.1,
        speaker_track_map=speaker_track_map,
    )
    assert state.confirmed_track_id == 2  # Streak tamamlandı, geçiş başarılı!


def test_analyze_speaker_dominance_and_auto_layout(monkeypatch) -> None:
    from backend.core.workflow_render_ops import _analyze_speaker_dominance, _resolve_segment_window
    import backend.core.workflow_render_ops as ops
    from backend.config import ProjectPaths
    from backend.services.video_processor import VideoProcessor
    
    # 1. Monologue: Only SPEAKER_01 speaking
    transcript = [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_01"},
        {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
    ]
    dominant_ratio, speaker_count, second_ratio = _analyze_speaker_dominance(transcript, 0.0, 10.0)
    assert speaker_count == 1
    assert dominant_ratio == 1.0
    assert second_ratio == 0.0
    
    # 2. Split dialogue: SPEAKER_01 for 6.0s, SPEAKER_02 for 4.0s
    transcript = [
        {"start": 0.0, "end": 6.0, "speaker": "SPEAKER_01"},
        {"start": 6.0, "end": 10.0, "speaker": "SPEAKER_02"},
    ]
    dominant_ratio, speaker_count, second_ratio = _analyze_speaker_dominance(transcript, 0.0, 10.0)
    assert speaker_count == 2
    assert abs(dominant_ratio - 0.6) < 1e-5
    assert abs(second_ratio - 0.4) < 1e-5
    
    # 3. Weak secondary dialogue: SPEAKER_01 for 9.0s, SPEAKER_02 for 1.0s (10% of total speaking) -> should force single layout since second_ratio < 0.20
    transcript = [
        {"start": 0.0, "end": 9.0, "speaker": "SPEAKER_01"},
        {"start": 9.0, "end": 10.0, "speaker": "SPEAKER_02"},
    ]
    dominant_ratio, speaker_count, second_ratio = _analyze_speaker_dominance(transcript, 0.0, 10.0)
    assert speaker_count == 2
    assert abs(dominant_ratio - 0.9) < 1e-5
    assert abs(second_ratio - 0.1) < 1e-5
    
    # Mocking snap and subtitle resolution functions for _resolve_segment_window
    def dummy_snap(transcript, s, e):
        return s, e, {}
        
    class DummySubPlan:
        resolved_layout = "single"
        
    def dummy_resolve_sub(*args, **kwargs):
        return DummySubPlan()

    monkeypatch.setattr(
        ops,
        "apply_opening_validation",
        lambda **kwargs: (kwargs["start_t"], {"layout_validation_status": "mocked"})
    )

    processor = VideoProcessor(device="cpu")

    # If requested_layout is auto, with second_ratio = 10% (< 20%), it must choose "single" layout
    res_start, res_end, custom_meta, render_plan, report = _resolve_segment_window(
        video_processor=processor,
        source_video=None,
        transcript_source=transcript,
        start_t=0.0,
        end_t=10.0,
        requested_layout="auto",
        cut_as_short=True,
        manual_center_x=None,
        snap_segment_boundaries=dummy_snap,
        resolve_subtitle_render_plan=dummy_resolve_sub,
    )
    assert render_plan.resolved_layout == "single"


def test_stabilize_tracking_center_split_controlled_return_ease_in() -> None:
    """Split layout controlled_return modunda ease-in damping faktörünün uygulandığını doğrular."""
    processor = VideoProcessor(device="cpu")
    from backend.services.video_processor import SPLIT_CONTROLLED_RETURN_PAN_RATIO, SPLIT_EMA_ALPHA

    # 1. lost_streak = 9 (return_frames = 1, ease_in = 0.1)
    state1 = TrackSlotState("primary", 640.0)
    state1.lost_streak = 9
    profile1 = processor._movement_profile(
        layout="split",
        mode="controlled_return",
        frame_width=1000,
        tracker_weak=False,
        state=state1,
    )

    # 2. lost_streak = 13 (return_frames = 5, ease_in = 0.5)
    state2 = TrackSlotState("primary", 640.0)
    state2.lost_streak = 13
    profile2 = processor._movement_profile(
        layout="split",
        mode="controlled_return",
        frame_width=1000,
        tracker_weak=False,
        state=state2,
    )

    # 3. lost_streak = 18 (return_frames = 10, ease_in = 1.0)
    state3 = TrackSlotState("primary", 640.0)
    state3.lost_streak = 18
    profile3 = processor._movement_profile(
        layout="split",
        mode="controlled_return",
        frame_width=1000,
        tracker_weak=False,
        state=state3,
    )

    # Adım boyutlarının ve EMA alfalarının kademeli olarak arttığını kontrol edelim
    assert profile1[1] < profile2[1] < profile3[1]
    assert profile1[2] < profile2[2] < profile3[2]

    # Tam ease_in (1.0) durumundaki değerlerin tam sınır limitlerine ulaştığını doğrulayalım
    assert abs(profile3[1] - 1000 * SPLIT_CONTROLLED_RETURN_PAN_RATIO) < 1e-5
    assert abs(profile3[2] - SPLIT_EMA_ALPHA) < 1e-5


