import pytest

from backend.models.schemas import JobRequest


@pytest.mark.smoke
def test_smoke_job_request_minimal():
    req = JobRequest(youtube_url='https://youtube.com/watch?v=1')
    assert req.youtube_url.startswith('https://')
