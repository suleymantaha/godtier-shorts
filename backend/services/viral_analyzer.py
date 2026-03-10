import os
import json
import threading
from typing import Optional, Callable
from pydantic import BaseModel, Field
from openai import OpenAI
from loguru import logger
from backend.config import LOGS_DIR, VIRAL_SEGMENTS

# Environment değişkenlerini yükle
from dotenv import load_dotenv
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
        self.engine = engine
        self.model_name = "moonshotai/kimi-k2.5"
        self.local_model_name = os.environ.get("LMSTUDIO_MODEL", "local-model")

    @staticmethod
    def _clip_words(text: str, limit: int) -> str:
        return " ".join(text.split()[:limit]).strip()

    @staticmethod
    def _normalize_hook(text: str) -> str:
        hook = " ".join(text.split()[:7]).strip()
        return (hook or "DIKKAT CEKEN AN").upper()

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
        if target_duration is None:
            target_duration = (min_duration + max_duration) / 2.0
        usable_segments = [
            seg for seg in transcript_data
            if str(seg.get("text", "")).strip() and "start" in seg and "end" in seg
        ]
        if not usable_segments:
            return {"segments": []}
        candidates: list[dict] = []

        for start_idx, start_seg in enumerate(usable_segments):
            window: list[dict] = []
            start_time = float(start_seg["start"])
            end_time = start_time
            total_chars = 0

            for current_seg in usable_segments[start_idx:]:
                current_start = float(current_seg["start"])
                current_end = float(current_seg["end"])

                if current_start < window_start:
                    continue
                if window_end and current_end > window_end:
                    break
                if current_end - start_time > max_duration:
                    break

                window.append(current_seg)
                end_time = current_end
                total_chars += len(str(current_seg.get("text", "")).strip())

                duration = end_time - start_time
                if duration >= min_duration:
                    density_score = total_chars / max(duration, 1.0)
                    candidates.append({
                        "start_time": start_time,
                        "end_time": end_time,
                        "window": list(window),
                        "score": density_score + min(len(window), 12) * 0.5,
                    })

                if end_time - start_time >= target_duration:
                    break

        if not candidates:
            full_start = float(usable_segments[0]["start"])
            full_end = float(usable_segments[-1]["end"])
            joined_text = " ".join(str(seg.get("text", "")).strip() for seg in usable_segments)
            title = self._clip_words(joined_text, 12) or "Otomatik Secilen Klip"
            return {
                "segments": [
                    {
                        "start_time": full_start,
                        "end_time": full_end,
                        "hook_text": self._normalize_hook(joined_text),
                        "ui_title": title,
                        "social_caption": f"{title} #shorts #viral",
                        "viral_score": 70,
                    }
                ]
            }

        candidates.sort(key=lambda item: (item["score"], item["end_time"] - item["start_time"]), reverse=True)
        selected: list[dict] = []

        for candidate in candidates:
            overlaps_existing = any(
                not (
                    candidate["end_time"] <= existing["start_time"] + 3
                    or candidate["start_time"] >= existing["end_time"] - 3
                )
                for existing in selected
            )
            if overlaps_existing:
                continue

            joined_text = " ".join(str(seg.get("text", "")).strip() for seg in candidate["window"])
            title = self._clip_words(joined_text, 12) or "Otomatik Secilen Klip"
            selected.append({
                "start_time": candidate["start_time"],
                "end_time": candidate["end_time"],
                "hook_text": self._normalize_hook(joined_text),
                "ui_title": title,
                "social_caption": f"{title} #shorts #viral",
                "viral_score": max(60, min(95, int(candidate["score"] * 5))),
            })

            if len(selected) >= limit:
                break

        return {"segments": selected}

    @staticmethod
    def _parse_llm_json_response(content: str) -> dict | None:
        """LLM yanıtından JSON çıkarır. Markdown ```json``` ve süslü parantez temizliği yapar."""
        json_str = content.strip()
        if "```" in json_str:
            parts = json_str.split("```")
            for part in parts:
                if "{" in part and "}" in part:
                    json_str = part.strip()
                    if json_str.lower().startswith("json"):
                        json_str = json_str[4:].strip()
                    break

        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            start = json_str.find("{")
            end = json_str.rfind("}")
            if start != -1 and end != -1:
                result = json.loads(json_str[start : end + 1])
            else:
                raise json.JSONDecodeError("Geçerli JSON bulunamadı", json_str, 0)

        if isinstance(result, list):
            result = {"segments": result}
        if "segments" not in result:
            keys = list(result.keys())
            if keys and isinstance(result.get(keys[0]), list):
                result = {"segments": result[keys[0]]}
            else:
                return None
        return result

    def _build_cloud_client(self) -> OpenAI | None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("⚠️ OPENROUTER_API_KEY bulunamadı. Cloud yerine fallback analiz kullanılacak.")
            return None

        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

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
        def _status(msg: str, pct: int) -> None:
            if ui_callback: ui_callback({"message": msg, "progress": pct})

        def _check_cancelled() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Job cancelled by user")

        logger.info(f"📂 Claude (OpenRouter) analizi başlıyor: {json_file_path}")
        _status("📂 AI Akıl Yürütme başlıyor...", 51)
        _check_cancelled()

        with open(json_file_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
        _check_cancelled()

        fallback_kw = {
            "limit": num_clips,
            "min_duration": duration_min,
            "max_duration": duration_max,
        }

        if self.engine != "cloud":
            logger.warning(f"⚠️ {self.engine} motoru için güvenli fallback analiz kullanılıyor.")
            _status("Yerel fallback analiz çalışıyor...", 55)
            result = self._build_fallback_segments(transcript_data, **fallback_kw)
            _check_cancelled()
            with open(str(VIRAL_SEGMENTS), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            return result

        client = self._build_cloud_client()
        if client is None:
            _status("Cloud AI hazir degil, fallback analiz kullaniliyor...", 55)
            result = self._build_fallback_segments(transcript_data, **fallback_kw)
            _check_cancelled()
            with open(str(VIRAL_SEGMENTS), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            return result

        full_text = ""
        for seg in transcript_data:
            _check_cancelled()
            full_text += f"[{seg.get('start', 0):.1f}s] ({seg.get('speaker', 'Unknown')}): {seg.get('text', '').strip()}\n"

        schema = {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "hook_text": "HOOK",
                    "ui_title": "TITLE",
                    "social_caption": "CAPTION",
                    "viral_score": 90
                }
            ]
        }

        dur_range = f"{int(duration_min)}-{int(duration_max)}"
        prompt = (
            "Sen dünyanın en iyi viral video kurgucusu ve sosyal medya stratejistisin. "
            "Sana bir videonun saniye bazlı transkriptini veriyorum.\n"
            "GÖREVİN:\n"
            f"1. Videodaki en çarpıcı, duygusal veya bilgilendirici {num_clips} viral segmenti bul (her biri {dur_range} saniye arası - Shorts formatı).\n"
            "2. Her segment için şunları yap:\n"
            "   - İlk 3 saniyede ekrana basılacak ÇARPICI bir 'hook_text' yaz (BÜYÜK HARFLERLE, dikkat çekici)\n"
            "   - Dashboard'da görünecek 'ui_title' yaz\n"
            "   - TikTok/Shorts için sosyal medya açıklaması ve Trend hashtag'leri ekle\n"
            "   - Viral potansiyelini 1-100 arası 'viral_score' ile puanla\n"
            f"3. Yanıtını MUTLAKA şu JSON formatında ver: {json.dumps(schema)}\n\n"
            "ÖNEMLİ: Çıktıda sadece JSON olsun, başka hiçbir açıklama metni ekleme.\n\n"
            "VİRAL STRATEJİLER:\n"
            "- "
            f"TRANSKRİPT:\n{full_text}"
        )

        try:
            _check_cancelled()
            # OpenRouter / Claude 3.5 Sonnet Çağrısı
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Sen profesyonel bir viral analiz uzmanısın. Yanıtın sadece saf JSON olmalı."},
                    {"role": "user", "content": prompt},
                ],
                extra_headers={
                    "HTTP-Referer": "http://localhost:5173", # OpenRouter için şart
                    "X-Title": "GodTierShorts",
                },
                extra_body={
                    "include_reasoning": True
                },
                temperature=0.1
            )
            
            message = response.choices[0].message
            content = message.content.strip() if message.content else ""
            
            # Reasoning (düşünme) detaylarını loglayalım
            model_extra = getattr(message, "model_extra", None) or {}
            reasoning = getattr(message, "reasoning", None) or model_extra.get("reasoning")
            if reasoning:
                msg = f"🧠 AI Akıl Yürütme: {reasoning[:150]}..."
                logger.debug(msg)
                _status(msg, 53)
            
            result = self._parse_llm_json_response(content)
            if result is None:
                logger.error(f"❌ LLM çıktısında 'segments' anahtarı bulunamadı! Çıktı: {content[:200]}...")
                return None

            _check_cancelled()
            with open(str(VIRAL_SEGMENTS), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            
            logger.success(f"✅ Analiz tamamlandı ({len(result['segments'])} segment).")
            return result
        except Exception as e:
            logger.error(f"❌ Analiz Hatası: {e}")
            _status("Cloud analiz hatasi alindi, fallback analiz kullaniliyor...", 56)
            result = self._build_fallback_segments(transcript_data, **fallback_kw)
            _check_cancelled()
            with open(str(VIRAL_SEGMENTS), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            return result

    @logger.catch
    def analyze_transcript_segment(
        self,
        transcript_data: list,
        limit: int = 3,
        window_start: float = 0,
        window_end: float = 0,
        cancel_event: threading.Event | None = None,
    ) -> dict | None:
        """Belirli bir transkript parçasını analiz eder ve N adet viral an bulur."""
        def _check_cancelled() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Job cancelled by user")

        _check_cancelled()

        if self.engine != "cloud":
            logger.warning(f"⚠️ {self.engine} motoru için segment fallback analizi kullanılıyor.")
            return self._build_fallback_segments(
                transcript_data,
                limit=limit,
                window_start=window_start,
                window_end=window_end,
            )

        client = self._build_cloud_client()
        if client is None:
            return self._build_fallback_segments(
                transcript_data,
                limit=limit,
                window_start=window_start,
                window_end=window_end,
            )
            
        logger.info(f"📂 Transkript segmenti analizi başlıyor (Limit: {limit})")

        full_text = ""
        for seg in transcript_data:
            _check_cancelled()
            full_text += f"[{seg.get('start', 0):.1f}s] ({seg.get('speaker', 'Unknown')}): {seg.get('text', '').strip()}\n"

        schema = {
            "segments": [
                {
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "hook_text": "HOOK",
                    "ui_title": "TITLE",
                    "social_caption": "CAPTION",
                    "viral_score": 90
                }
            ]
        }

        prompt = (
            "Sen dünyanın en iyi viral video kurgucusu ve sosyal medya stratejistisin.\n"
            f"Sana videonun {window_start:.1f}s ile {window_end:.1f}s arasındaki transkriptini veriyorum.\n"
            "GÖREVİN:\n"
            f"1. Bu aralıktaki EN ÇARPICI {limit} adet viral segmenti bul (her biri 120-180 saniye arası - Shorts formatı).\n"
            "2. Her segment için şunları yap:\n"
            "   - İlk 3 saniyede ekrana basılacak ÇARPICI bir 'hook_text' yaz (BÜYÜK HARFLERLE)\n"
            "   - Dashboard'da görünecek 'ui_title' yaz\n"
            "   - TikTok/Shorts için sosyal medya açıklaması ve Trend hashtag'leri ekle\n"
            "   - Viral potansiyelini 1-100 arası 'viral_score' ile puanla\n"
            f"3. Yanıtını MUTLAKA şu JSON formatında ver: {json.dumps(schema)}\n\n"
            "ÖNEMLİ: Çıktıda sadece JSON olsun, başka hiçbir açıklama metni ekleme.\n\n"
            f"TRANSKRİPT:\n{full_text}"
        )

        try:
            _check_cancelled()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Sen profesyonel bir viral analiz uzmanısın. Yanıtın sadece saf JSON olmalı."},
                    {"role": "user", "content": prompt},
                ],
                extra_headers={
                    "HTTP-Referer": "http://localhost:5173",
                    "X-Title": "GodTierShorts",
                },
                temperature=0.1
            )

            message = response.choices[0].message
            content = message.content.strip() if message.content else ""
            result = self._parse_llm_json_response(content)
            if result is None:
                return None
            
            logger.success(f"✅ Segment analizi tamamlandı ({len(result['segments'])} segment).")
            return result
        except Exception as e:
            logger.error(f"❌ Segment Analiz Hatası: {e}")
            return self._build_fallback_segments(
                transcript_data,
                limit=limit,
                window_start=window_start,
                window_end=window_end,
            )