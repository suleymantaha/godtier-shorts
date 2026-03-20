"""
backend/tests/test_job_request.py
==================================
JobRequest schema için unit testler.
num_clips, auto_mode, duration_min, duration_max validasyonu.
"""
import pytest
from pydantic_core import ValidationError

from backend.models.schemas import JobRequest


def test_job_request_accepts_new_fields():
    """JobRequest num_clips, auto_mode, duration_min, duration_max kabul eder."""
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        num_clips=10,
        auto_mode=True,
    )
    assert req.num_clips == 10
    assert req.auto_mode is True
    assert req.duration_min is None
    assert req.duration_max is None
    assert req.force_reanalyze is False
    assert req.force_rerender is False


def test_job_request_accepts_force_flags() -> None:
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        force_reanalyze=True,
        force_rerender=True,
    )
    assert req.force_reanalyze is True
    assert req.force_rerender is True


def test_job_request_auto_mode_true_uses_defaults():
    """auto_mode=True iken duration_min/max gonderilmezse 120/180 kullanilir (backend tarafinda)."""
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        auto_mode=True,
    )
    assert req.auto_mode is True
    # Schema'da optional - backend run_gpu_job'da 120/180 atanacak
    assert req.duration_min is None
    assert req.duration_max is None


def test_job_request_auto_mode_false_requires_valid_duration():
    """auto_mode=False iken duration_min < duration_max olmali."""
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        auto_mode=False,
        duration_min=60,
        duration_max=120,
    )
    assert req.duration_min == 60
    assert req.duration_max == 120


def test_job_request_auto_mode_false_rejects_invalid_range():
    """auto_mode=False iken duration_min >= duration_max hata verir."""
    with pytest.raises(ValidationError) as exc_info:
        JobRequest(
            youtube_url="https://youtube.com/watch?v=test",
            auto_mode=False,
            duration_min=180,
            duration_max=120,
        )
    assert "duration" in str(exc_info.value).lower() or "bitis" in str(exc_info.value).lower()


def test_job_request_num_clips_range():
    """num_clips 1-20 araliginda olmali."""
    req = JobRequest(youtube_url="https://youtube.com/watch?v=test", num_clips=1)
    assert req.num_clips == 1

    req = JobRequest(youtube_url="https://youtube.com/watch?v=test", num_clips=20)
    assert req.num_clips == 20

    with pytest.raises(ValidationError):
        JobRequest(youtube_url="https://youtube.com/watch?v=test", num_clips=0)

    with pytest.raises(ValidationError):
        JobRequest(youtube_url="https://youtube.com/watch?v=test", num_clips=21)


def test_job_request_duration_bounds():
    """duration_min ve duration_max 30-300 araliginda olmali."""
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        auto_mode=False,
        duration_min=30,
        duration_max=300,
    )
    assert req.duration_min == 30
    assert req.duration_max == 300

    with pytest.raises(ValidationError):
        JobRequest(
            youtube_url="https://youtube.com/watch?v=test",
            auto_mode=False,
            duration_min=20,
            duration_max=120,
        )

    with pytest.raises(ValidationError):
        JobRequest(
            youtube_url="https://youtube.com/watch?v=test",
            auto_mode=False,
            duration_min=120,
            duration_max=350,
        )


def test_job_request_rejects_unknown_style_name():
    with pytest.raises(ValidationError) as exc_info:
        JobRequest(
            youtube_url="https://youtube.com/watch?v=test",
            style_name="CUSTOM",
        )
    assert "unknown style_name" in str(exc_info.value)


def test_job_request_validates_layout_name():
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        layout="auto",
    )
    assert req.layout == "auto"

    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        layout="split",
    )
    assert req.layout == "split"

    with pytest.raises(ValidationError) as exc_info:
        JobRequest(
            youtube_url="https://youtube.com/watch?v=test",
            layout="grid",
        )
    assert "unknown requested layout" in str(exc_info.value)


def test_job_request_validates_animation_type():
    req = JobRequest(
        youtube_url="https://youtube.com/watch?v=test",
        animation_type="shake",
    )
    assert req.animation_type == "shake"

    with pytest.raises(ValidationError) as exc_info:
        JobRequest(
            youtube_url="https://youtube.com/watch?v=test",
            animation_type="warp",
        )
    assert "unknown animation_type" in str(exc_info.value)
