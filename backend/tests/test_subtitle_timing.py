from __future__ import annotations

from backend.core.subtitle_timing import (
    build_words_from_segment_text,
    canonicalize_transcript_segments,
    build_chunk_payload,
    chunk_words,
    collect_valid_words,
    compute_word_coverage_ratio,
    normalize_subtitle_text,
    snap_segment_boundaries,
)


def test_normalize_subtitle_text_collapses_unicode_variants() -> None:
    assert normalize_subtitle_text("A\u200bb\u200cc …  ’x’  — test") == "Abc ... 'x' - test"


def test_snap_segment_boundaries_uses_word_coverage_gating() -> None:
    segments = [
        {
            "text": "hello brave world",
            "start": 1.0,
            "end": 2.2,
            "words": [
                {"word": "hello", "start": 1.0, "end": 1.3},
                {"word": "brave", "start": 1.3, "end": 1.7},
                {"word": "world", "start": 1.7, "end": 2.2},
            ],
        }
    ]

    snapped_start, snapped_end, report = snap_segment_boundaries(segments, 0.92, 2.08)
    assert snapped_start == 1.0
    assert snapped_end == 2.2
    assert report["enabled"] is True
    assert report["boundary_snaps_applied"] == 2


def test_snap_segment_boundaries_disables_when_word_coverage_is_low() -> None:
    segments = [{"text": "hello brave world", "start": 1.0, "end": 2.2, "words": []}]
    snapped_start, snapped_end, report = snap_segment_boundaries(segments, 0.92, 2.08)
    assert snapped_start == 0.92
    assert snapped_end == 2.08
    assert report["enabled"] is False


def test_chunk_words_merges_very_short_chunks_without_crossing_strong_punctuation() -> None:
    words = collect_valid_words(
        [
            {
                "text": "go now please",
                "start": 0.0,
                "end": 1.0,
                "words": [
                    {"word": "go", "start": 0.0, "end": 0.1},
                    {"word": "now", "start": 0.1, "end": 0.2},
                    {"word": "please", "start": 0.2, "end": 0.9},
                ],
            }
        ]
    )
    chunks = chunk_words(words, max_words=2)
    payload = build_chunk_payload(chunks)

    assert len(payload) == 1
    assert payload[0]["text"] == "go now please"
    assert payload[0]["duration"] > 0.45


def test_compute_word_coverage_ratio_counts_valid_words_against_normalized_tokens() -> None:
    ratio = compute_word_coverage_ratio(
        [
            {
                "text": "Hello, world!",
                "start": 0.0,
                "end": 1.0,
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.4},
                    {"word": "world", "start": 0.4, "end": 1.0},
                ],
            }
        ]
    )
    assert ratio == 1.0


def test_canonicalize_transcript_segments_preserves_word_slots_for_same_token_count() -> None:
    canonical = canonicalize_transcript_segments(
        [
            {
                "text": "fresh copy",
                "start": 0.0,
                "end": 2.0,
                "words": [
                    {"word": "hello", "start": 0.0, "end": 0.8, "score": 0.7},
                    {"word": "world", "start": 0.8, "end": 2.0, "score": 0.9},
                ],
            }
        ]
    )

    assert canonical == [
        {
            "text": "fresh copy",
            "start": 0.0,
            "end": 2.0,
            "words": [
                {"word": "fresh", "start": 0.0, "end": 0.8, "score": 0.7},
                {"word": "copy", "start": 0.8, "end": 2.0, "score": 0.9},
            ],
        }
    ]


def test_canonicalize_transcript_segments_rebuilds_words_when_token_count_changes() -> None:
    canonical = canonicalize_transcript_segments(
        [
            {
                "text": "fresh new copy",
                "start": 0.0,
                "end": 3.0,
                "words": [
                    {"word": "hello", "start": 0.0, "end": 1.0, "score": 0.7},
                    {"word": "world", "start": 1.0, "end": 3.0, "score": 0.9},
                ],
            }
        ]
    )

    assert canonical[0]["words"] == build_words_from_segment_text("fresh new copy", 0.0, 3.0)
