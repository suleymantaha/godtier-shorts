import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.core.exceptions import InvalidInputError
from backend.core.workflow_render_ops import run_cut_points_workflow


def run_workflow(points, monkeypatch):
    from backend.core import workflows_manual

    rendered = []

    class ManualWorkflow:
        def __init__(self, ctx):
            pass

        async def run(self, **kwargs):
            rendered.append((kwargs["start_t"], kwargs["end_t"]))
            return kwargs["output_name"]

    monkeypatch.setattr(workflows_manual, "ManualClipWorkflow", ManualWorkflow)
    ctx = SimpleNamespace(_check_cancelled=lambda: None, _update_status=lambda *args: None)
    kwargs = dict(cut_points=points, transcript_data=[], job_id=None, style_name="HORMOZI",
                  animation_type="pop", project_id=None, layout="auto", skip_subtitles=True,
                  cut_as_short=True)
    return asyncio.run(run_cut_points_workflow(ctx, **kwargs)), rendered


@pytest.mark.parametrize("points", [
    [], [1], [1, 1], [0, 2, 1], [0, 1, 1], [-1, 1], [0, float("nan")],
    [0, float("inf")], [False, 1], [0, "1"], list(range(22)), [0, 10 ** 1000],
])
def test_invalid_internal_cut_points_fail_before_any_render(points, monkeypatch):
    from backend.core import workflows_manual

    def unexpected_init(ctx):
        pytest.fail("Invalid points must be rejected before creating the render workflow")

    monkeypatch.setattr(workflows_manual, "ManualClipWorkflow", unexpected_init)
    ctx = SimpleNamespace()
    with pytest.raises(InvalidInputError) as error:
        asyncio.run(run_cut_points_workflow(
            ctx, cut_points=points, transcript_data=[], job_id=None, style_name="HORMOZI",
            animation_type="pop", project_id=None, layout="auto", skip_subtitles=True,
            cut_as_short=True,
        ))
    assert error.value.code == "INVALID_INPUT"
    assert error.value.status_code == 400


def test_valid_internal_cut_points_keep_requested_segments(monkeypatch):
    outputs, rendered = run_workflow([0, 1.5, 3], monkeypatch)
    assert len(outputs) == 2
    assert rendered == [(0, 1.5), (1.5, 3)]


def test_cut_points_invalid_input_keeps_public_http_error_contract():
    from starlette.requests import Request

    from backend.api.error_handlers import app_error_handler

    request = Request({"type": "http", "headers": []})
    response = asyncio.run(app_error_handler(request, InvalidInputError("Invalid cut points")))
    assert response.status_code == 400
    assert json.loads(response.body)["code"] == "INVALID_INPUT"
