from __future__ import annotations

import json
from pathlib import Path

from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.subtitle_styles import StyleManager

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "subtitle_parity_cases.json"


def _write_transcript(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_subtitle_parity_contract_cases(tmp_path: Path) -> None:
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    for case in cases:
        transcript_path = _write_transcript(tmp_path / f"{case['name']}.json", case["transcript"])
        output_path = tmp_path / f"{case['name']}.ass"
        renderer = SubtitleRenderer(StyleManager.get_preset(case["style_name"]), layout=case["layout"])
        renderer.generate_ass_file(str(transcript_path), str(output_path))

        report = renderer.last_render_report
        assert report["overflow_strategy"] == case["expected"]["overflow_strategy"]
        assert len(report["chunk_dump"]) == len(case["expected"]["chunks"])

        for chunk_payload, expected_chunk in zip(report["chunk_dump"], case["expected"]["chunks"], strict=True):
            assert chunk_payload["text"] == expected_chunk["text"]
            if "line_break_after" in expected_chunk:
                assert chunk_payload.get("line_break_after") == expected_chunk["line_break_after"]
            if "font_scale_below" in expected_chunk:
                assert float(chunk_payload.get("font_scale") or 1.0) < float(expected_chunk["font_scale_below"])
