from __future__ import annotations

import argparse
import json
import traceback

from loguru import logger

from backend.core.runtime_env import load_runtime_env
from backend.workers.torchaudio_compat import apply_torchaudio_compat_shims


def _emit_event(payload: dict[str, object]) -> None:
    from backend.services.diarization import WORKER_EVENT_PREFIX

    print(f"{WORKER_EVENT_PREFIX}{json.dumps(payload, ensure_ascii=False)}", flush=True)



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pyannote diarization in an isolated worker process.")
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--transcript-json-path", required=True)
    parser.add_argument("--num-speakers", type=int, default=None)
    return parser



def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        load_runtime_env()
    except Exception as exc:
        logger.warning("Runtime env yuklenemedi, varsayilan env ile devam ediliyor: {}", exc)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    apply_torchaudio_compat_shims()

    from backend.services.diarization import _run_diarization_local

    _emit_event({"type": "status", "message": "Izole diarization worker hazirlaniyor...", "progress": 41})

    try:
        ok = _run_diarization_local(
            args.audio_path,
            args.transcript_json_path,
            num_speakers=args.num_speakers,
            status_callback=lambda message, progress: _emit_event(
                {"type": "status", "message": message, "progress": int(progress)}
            ),
        )
        _emit_event({"type": "result", "ok": bool(ok)})
        return 0 if ok else 1
    except Exception as exc:
        _emit_event(
            {
                "type": "error",
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        logger.exception("Diarization worker patladi")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
