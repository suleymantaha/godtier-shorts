from __future__ import annotations

import importlib


def test_workflow_module_split_imports_stay_compatible() -> None:
    module_names = [
        "backend.core.workflow_helpers",
        "backend.core.workflows_pipeline",
        "backend.core.workflows_batch",
        "backend.core.workflows_manual",
        "backend.core.workflows_reburn",
        "backend.api.routes.jobs",
    ]

    imported_modules = [importlib.import_module(module_name) for module_name in module_names]

    assert imported_modules[0].render_pipeline_segments is not None
