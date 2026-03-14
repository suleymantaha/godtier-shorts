import json
import os
import threading
from typing import Callable, Optional

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.config import VIRAL_SEGMENTS
from backend.services.viral_llm_adapters import ViralLLMAdapter, create_adapter, engine_label
from backend.services.viral_analyzer_core import (
    build_fallback_segments,
    build_metadata_prompt,
    build_segment_prompt,
    build_transcript_text,
    clip_words,
    extract_message_content,
    normalize_hook,
    parse_llm_json_response,
)

load_dotenv()


class ViralSegment(BaseModel):
    start_time: float = Field(description="Viral kısmın başlangıç saniyesi")
    end_time: float = Field(description="Viral kısmın bitiş saniyesi")
    hook_text: str = Field(description="Videonun ilk 3 saniyesinde ekrana basılacak devasa kanca metni")
    ui_title: str = Field(description="Dashboard'da görünecek ilgi çekici başlık")
    social_caption: str = Field(description="TikTok/Shorts açıklaması ve hashtagler")
    viral_score: int = Field(description="1-100 arası puan")


class ViralAnalysisResult(BaseModel):
    segments: list[ViralSegment]


class ViralAnalyzer:
    def __init__(self, engine: str = "cloud"):
        self.engine = (engine or "cloud").strip().lower()
        self.model_name = os.environ.get("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")
        self.local_model_name = os.environ.get("LMSTUDIO_MODEL", "local-model")

    @staticmethod
    def _clip_words(text: str, limit: int) -> str:
        return clip_words(text, limit)

    @staticmethod
    def _normalize_hook(text: str) -> str:
        return normalize_hook(text)

    def _build_fallback_segments(
        self,
        transcript_data: list[dict],
        limit: int = 5,
        window_start: float = 0,
        window_end: float = 0,
        min_duration: float = 25.0,
        max_duration: float = 95.0,
        target_duration: float | None = None,
    ) -> dict:
        return build_fallback_segments(
            transcript_data,
            limit=limit,
            window_start=window_start,
            window_end=window_end,
            min_duration=min_duration,
            max_duration=max_duration,
            target_duration=target_duration,
        )

    @staticmethod
    def _parse_llm_json_response(content: str) -> dict | None:
        return parse_llm_json_response(content)

    def _build_cloud_client(self) -> OpenAI | None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("⚠️ OPENROUTER_API_KEY bulunamadı. Cloud yerine fallback analiz kullanılacak.")
            return None
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    def _build_lmstudio_client(self) -> OpenAI | None:
        host = os.environ.get("LMSTUDIO_HOST", "").strip()
        if not host:
            logger.warning("⚠️ LMSTUDIO_HOST bulunamadı. LM Studio yerine fallback analiz kullanılacak.")
            return None

        base_url = host.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"

        api_key = os.environ.get("LM_STUDIO_API_KEY", "").strip() or "lm-studio"
        return OpenAI(base_url=base_url, api_key=api_key)

    @staticmethod
    def _extract_message_content(message: object) -> str:
        return extract_message_content(message)

    @staticmethod
    def _status_callback(ui_callback: Optional[Callable]) -> Callable[[str, int], None]:
        def _status(message: str, progress: int) -> None:
            if ui_callback:
                ui_callback({"message": message, "progress": progress})

        return _status

    @staticmethod
    def _cancel_checker(cancel_event: threading.Event | None) -> Callable[[], None]:
        def _check_cancelled() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Job cancelled by user")

        return _check_cancelled

    def _engine_label(self) -> str:
        return engine_label(self.engine)

    def _resolve_client(self) -> OpenAI | None:
        if self.engine == "cloud":
            return self._build_cloud_client()
        if self.engine == "lmstudio":
            return self._build_lmstudio_client()
        return None

    def _resolve_adapter(self) -> ViralLLMAdapter | None:
        return create_adapter(
            self.engine,
            cloud_model_name=self.model_name,
            local_model_name=self.local_model_name,
        )

    @staticmethod
    def _persist_segments(result: dict) -> None:
        with open(str(VIRAL_SEGMENTS), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

    def _fallback_result(
        self,
        transcript_data: list[dict],
        *,
        fallback_kw: dict,
        check_cancelled: Callable[[], None],
        persist: bool,
    ) -> dict:
        result = self._build_fallback_segments(transcript_data, **fallback_kw)
        check_cancelled()
        if persist:
            self._persist_segments(result)
        return result

    def _call_llm(
        self,
        client: OpenAI,
        adapter: ViralLLMAdapter,
        prompt: str,
        *,
        include_reasoning: bool,
        status: Optional[Callable[[str, int], None]] = None,
    ) -> dict | None:
        request_kwargs = adapter.build_request_kwargs(prompt, include_reasoning=include_reasoning)
        response = client.chat.completions.create(**request_kwargs)

        message = response.choices[0].message
        content = self._extract_message_content(message)

        if include_reasoning and status is not None:
            model_extra = getattr(message, "model_extra", None) or {}
            reasoning = getattr(message, "reasoning", None) or model_extra.get("reasoning")
            if reasoning:
                msg = f"🧠 AI Akıl Yürütme: {reasoning[:150]}..."
                logger.debug(msg)
                status(msg, 53)

        return self._parse_llm_json_response(content)

    @logger.catch
    def analyze_metadata(
        self,
        json_file_path: str,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        ui_callback: Optional[Callable] = None,
        cancel_event: threading.Event | None = None,
    ) -> dict | None:
        status = self._status_callback(ui_callback)
        check_cancelled = self._cancel_checker(cancel_event)
        engine_label = self._engine_label()

        logger.info(f"📂 {engine_label} analizi başlıyor: {json_file_path}")
        status("📂 AI Akıl Yürütme başlıyor...", 51)
        check_cancelled()

        with open(json_file_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
        check_cancelled()

        fallback_kw = {
            "limit": num_clips,
            "min_duration": duration_min,
            "max_duration": duration_max,
        }

        if self.engine not in {"cloud", "lmstudio"}:
            logger.warning(f"⚠️ {self.engine} motoru için güvenli fallback analiz kullanılıyor.")
            status("Yerel fallback analiz çalışıyor...", 55)
            return self._fallback_result(
                transcript_data,
                fallback_kw=fallback_kw,
                check_cancelled=check_cancelled,
                persist=True,
            )

        adapter = self._resolve_adapter()
        client = self._resolve_client()
        if client is None or adapter is None:
            status(f"{engine_label} hazir degil, fallback analiz kullaniliyor...", 55)
            return self._fallback_result(
                transcript_data,
                fallback_kw=fallback_kw,
                check_cancelled=check_cancelled,
                persist=True,
            )

        full_text = build_transcript_text(transcript_data, check_cancelled)
        prompt = build_metadata_prompt(
            full_text,
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
        )

        try:
            check_cancelled()
            result = self._call_llm(client, adapter, prompt, include_reasoning=True, status=status)
            if result is None:
                logger.error("❌ LLM çıktısında 'segments' anahtarı bulunamadı!")
                return None

            check_cancelled()
            self._persist_segments(result)
            logger.success(f"✅ Analiz tamamlandı ({len(result['segments'])} segment).")
            return result
        except Exception as exc:
            logger.error(f"❌ Analiz Hatası: {exc}")
            status(f"{engine_label} analiz hatasi alindi, fallback analiz kullaniliyor...", 56)
            return self._fallback_result(
                transcript_data,
                fallback_kw=fallback_kw,
                check_cancelled=check_cancelled,
                persist=True,
            )

    @logger.catch
    def analyze_transcript_segment(
        self,
        transcript_data: list,
        limit: int = 3,
        window_start: float = 0,
        window_end: float = 0,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        cancel_event: threading.Event | None = None,
    ) -> dict | None:
        check_cancelled = self._cancel_checker(cancel_event)
        check_cancelled()

        if duration_min > duration_max:
            duration_min, duration_max = duration_max, duration_min
        target_duration = (duration_min + duration_max) / 2.0

        fallback_kw = {
            "limit": limit,
            "window_start": window_start,
            "window_end": window_end,
            "min_duration": duration_min,
            "max_duration": duration_max,
            "target_duration": target_duration,
        }

        if self.engine not in {"cloud", "lmstudio"}:
            logger.warning(f"⚠️ {self.engine} motoru için segment fallback analizi kullanılıyor.")
            return self._fallback_result(
                transcript_data,
                fallback_kw=fallback_kw,
                check_cancelled=check_cancelled,
                persist=False,
            )

        adapter = self._resolve_adapter()
        client = self._resolve_client()
        if client is None or adapter is None:
            return self._fallback_result(
                transcript_data,
                fallback_kw=fallback_kw,
                check_cancelled=check_cancelled,
                persist=False,
            )

        logger.info(f"📂 Transkript segmenti analizi başlıyor (Limit: {limit})")
        full_text = build_transcript_text(transcript_data, check_cancelled)
        prompt = build_segment_prompt(
            full_text,
            limit=limit,
            window_start=window_start,
            window_end=window_end,
            duration_min=duration_min,
            duration_max=duration_max,
        )

        try:
            check_cancelled()
            result = self._call_llm(client, adapter, prompt, include_reasoning=False)
            if result is None:
                return None

            logger.success(f"✅ Segment analizi tamamlandı ({len(result['segments'])} segment).")
            return result
        except Exception as exc:
            logger.error(f"❌ Segment Analiz Hatası: {exc}")
            return self._fallback_result(
                transcript_data,
                fallback_kw=fallback_kw,
                check_cancelled=check_cancelled,
                persist=False,
            )
