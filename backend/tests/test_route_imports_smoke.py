"""Smoke tests for route modules that depend on backend.models.schemas."""

import sys
import types


class _DummyYOLO:
    def __init__(self, *args, **kwargs) -> None:
        pass


def test_route_modules_import(monkeypatch) -> None:
    import fastapi.dependencies.utils as dep_utils

    monkeypatch.setattr(dep_utils, "ensure_multipart_is_installed", lambda: None)
    monkeypatch.setitem(sys.modules, "cv2", types.ModuleType("cv2"))

    ultralytics_stub = types.ModuleType("ultralytics")
    ultralytics_stub.YOLO = _DummyYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics_stub)

    import backend.api.routes.clips as clips_routes
    import backend.api.routes.social as social_routes
    import backend.api.routes.editor as editor_routes
    import backend.api.routes.jobs as job_routes
    from backend.api.server import create_app

    assert clips_routes.router is not None
    assert social_routes.router is not None
    assert editor_routes.router is not None
    assert job_routes.router is not None
    assert create_app() is not None
