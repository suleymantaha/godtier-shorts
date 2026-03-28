"""Pure helpers for ViralAnalyzer prompting/parsing/fallback logic."""

from __future__ import annotations

import json
import re
from typing import Callable

from backend.core.render_contracts import resolve_duration_validation_status


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9']+")
_LOW_SIGNAL_PREFIXES = (
    "acaba",
    "bak",
    "bire bir",
    "diyorlar ki",
    "girecektir",
    "gençler bunu",
    "herhalde",
    "işte",
    "şimdi",
    "ve hala",
    "yani",
)
_FILLER_WORDS = {
    "abi",
    "acaba",
    "aslında",
    "bak",
    "bence",
    "bir",
    "bire",
    "bu",
    "bunu",
    "çok",
    "da",
    "de",
    "değil",
    "diyorlar",
    "gibi",
    "hala",
    "hatta",
    "herhalde",
    "hiç",
    "işte",
    "ki",
    "mi",
    "mu",
    "mü",
    "ne",
    "o",
    "orada",
    "orada",
    "sen",
    "şey",
    "şimdi",
    "ve",
    "var",
    "yani",
}


def clip_words(text: str, limit: int) -> str:
    return " ".join(text.split()[:limit]).strip()


def normalize_hook(text: str) -> str:
    hook = " ".join(text.split()[:7]).strip()
    return (hook or "DIKKAT CEKEN AN").upper()


def _collect_segment_window_text(
    transcript_data: list[dict],
    *,
    start_time: float,
    end_time: float,
) -> str:
    parts: list[str] = []
    for segment in transcript_data:
        seg_start = segment.get("start")
        seg_end = segment.get("end")
        if not isinstance(seg_start, (int, float)) or not isinstance(seg_end, (int, float)):
            continue
        if float(seg_end) <= start_time or float(seg_start) >= end_time:
            continue
        text = str(segment.get("text", "")).strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _split_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return []
    return [sentence.strip(" ,;:-") for sentence in _SENTENCE_SPLIT_RE.split(cleaned) if sentence.strip(" ,;:-")]


def _tokenize_words(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD_RE.finditer(text)]


def _starts_with_low_signal_prefix(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return any(lowered.startswith(prefix) for prefix in _LOW_SIGNAL_PREFIXES)


def _sentence_score(text: str) -> float:
    words = _tokenize_words(text)
    if not words:
        return float("-inf")

    informative_words = [word for word in words if word not in _FILLER_WORDS and len(word) >= 4]
    unique_words = len(set(informative_words))
    score = unique_words * 2.5 + len(informative_words) * 0.8

    if text.endswith("?"):
        score += 2.0
    if any(char.isdigit() for char in text):
        score += 1.0
    if _starts_with_low_signal_prefix(text):
        score -= 4.0
    if len(words) < 4:
        score -= 2.5
    if len(words) > 16:
        score -= 1.0
    return score


def choose_representative_sentence(
    transcript_data: list[dict],
    *,
    start_time: float,
    end_time: float,
    fallback_text: str = "",
) -> str:
    window_text = _collect_segment_window_text(
        transcript_data,
        start_time=start_time,
        end_time=end_time,
    )
    candidates = _split_sentences(window_text)
    if fallback_text.strip():
        candidates.extend(_split_sentences(fallback_text))

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = " ".join(candidate.lower().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)

    if not unique_candidates:
        return fallback_text.strip()

    return max(unique_candidates, key=_sentence_score)


def _normalize_title(text: str) -> str:
    compact = " ".join(text.split()).strip(" ,;:-")
    return clip_words(compact, 12) or "Otomatik Secilen Klip"


def _normalize_caption(text: str, *, fallback_title: str) -> str:
    base = " ".join(text.split()).strip(" ,;:-") or fallback_title
    return f"{base} #shorts #viral"


def _looks_low_quality(text: str) -> bool:
    compact = " ".join(text.split()).strip()
    if not compact:
        return True

    words = _tokenize_words(compact)
    informative_words = [word for word in words if word not in _FILLER_WORDS and len(word) >= 4]
    return _starts_with_low_signal_prefix(compact) or len(informative_words) < 2


def enrich_segment_copy(segment: dict, transcript_data: list[dict]) -> dict:
    try:
        start_time = float(segment.get("start_time"))
        end_time = float(segment.get("end_time"))
    except (TypeError, ValueError):
        return segment

    preferred_sentence = choose_representative_sentence(
        transcript_data,
        start_time=start_time,
        end_time=end_time,
        fallback_text=str(segment.get("ui_title") or segment.get("hook_text") or ""),
    )
    if not preferred_sentence:
        return segment

    if _looks_low_quality(str(segment.get("ui_title") or "")):
        segment["ui_title"] = _normalize_title(preferred_sentence)

    if _looks_low_quality(str(segment.get("hook_text") or "")):
        segment["hook_text"] = normalize_hook(preferred_sentence)

    caption = str(segment.get("social_caption") or "").strip()
    if _looks_low_quality(caption) or caption == str(segment.get("ui_title") or "").strip():
        segment["social_caption"] = _normalize_caption(
            preferred_sentence,
            fallback_title=str(segment.get("ui_title") or ""),
        )

    return segment


def normalize_viral_segments(
    result: dict | None,
    transcript_data: list[dict],
    *,
    limit: int,
    duration_min: float,
    duration_max: float,
) -> dict | None:
    if result is None or not isinstance(result, dict):
        return None

    raw_segments = result.get("segments")
    if not isinstance(raw_segments, list):
        return None

    usable_segments = [
        seg for seg in transcript_data if isinstance(seg, dict) and "start" in seg and "end" in seg
    ]
    if not usable_segments:
        return {"segments": []}

    transcript_start = float(usable_segments[0]["start"])
    transcript_end = float(usable_segments[-1]["end"])
    normalized_segments: list[dict] = []

    for candidate in raw_segments:
        if not isinstance(candidate, dict):
            continue
        try:
            start_time = float(candidate.get("start_time"))
            end_time = float(candidate.get("end_time"))
        except (TypeError, ValueError):
            continue

        if start_time < transcript_start or end_time > transcript_end:
            continue

        if resolve_duration_validation_status(
            start_time,
            end_time,
            duration_min=duration_min,
            duration_max=duration_max,
        ) != "ok":
            continue

        hook_text = str(candidate.get("hook_text", "")).strip()
        ui_title = str(candidate.get("ui_title", "")).strip()
        if not hook_text:
            hook_text = normalize_hook(ui_title or "DIKKAT CEKEN AN")
        if not ui_title:
            ui_title = clip_words(hook_text, 12) or "Otomatik Secilen Klip"

        social_caption = str(candidate.get("social_caption", "")).strip() or f"{ui_title} #shorts #viral"
        try:
            viral_score = int(candidate.get("viral_score", 70))
        except (TypeError, ValueError):
            viral_score = 70

        normalized_segments.append(
            enrich_segment_copy(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "hook_text": hook_text,
                    "ui_title": ui_title,
                    "social_caption": social_caption,
                    "viral_score": max(1, min(100, viral_score)),
                },
                transcript_data,
            )
        )
        if len(normalized_segments) >= limit:
            break

    return {"segments": normalized_segments}


def build_fallback_segments(
    transcript_data: list[dict],
    *,
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
        seg for seg in transcript_data if str(seg.get("text", "")).strip() and "start" in seg and "end" in seg
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
                candidates.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "window": list(window),
                        "score": density_score + min(len(window), 12) * 0.5,
                    }
                )

            if end_time - start_time >= target_duration:
                break

    if not candidates:
        full_start = float(usable_segments[0]["start"])
        full_end = float(usable_segments[-1]["end"])
        joined_text = " ".join(str(seg.get("text", "")).strip() for seg in usable_segments)
        title = clip_words(joined_text, 12) or "Otomatik Secilen Klip"
        if resolve_duration_validation_status(
            full_start,
            full_end,
            duration_min=min_duration,
            duration_max=max_duration,
        ) != "ok":
            return {"segments": []}
        return {
            "segments": [
                enrich_segment_copy(
                    {
                        "start_time": full_start,
                        "end_time": full_end,
                        "hook_text": normalize_hook(joined_text),
                        "ui_title": title,
                        "social_caption": f"{title} #shorts #viral",
                        "viral_score": 70,
                    },
                    transcript_data,
                )
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
        title = clip_words(joined_text, 12) or "Otomatik Secilen Klip"
        selected.append(
            enrich_segment_copy(
                {
                    "start_time": candidate["start_time"],
                    "end_time": candidate["end_time"],
                    "hook_text": normalize_hook(joined_text),
                    "ui_title": title,
                    "social_caption": f"{title} #shorts #viral",
                    "viral_score": max(60, min(95, int(candidate["score"] * 5))),
                },
                transcript_data,
            )
        )

        if len(selected) >= limit:
            break

    return {"segments": selected}


def parse_llm_json_response(content: str) -> dict | None:
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


def extract_message_content(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
        return "\n".join(chunks).strip()
    return str(content).strip() if content else ""


def build_transcript_text(transcript_data: list[dict], check_cancelled: Callable[[], None]) -> str:
    lines: list[str] = []
    for seg in transcript_data:
        check_cancelled()
        lines.append(
            f"[{seg.get('start', 0):.1f}s] ({seg.get('speaker', 'Unknown')}): {seg.get('text', '').strip()}"
        )
    return "\n".join(lines)


def default_segments_schema_json() -> str:
    schema = {
        "segments": [
            {
                "start_time": 0.0,
                "end_time": 0.0,
                "hook_text": "HOOK",
                "ui_title": "TITLE",
                "social_caption": "CAPTION",
                "viral_score": 90,
            }
        ]
    }
    return json.dumps(schema)


def build_metadata_prompt(full_text: str, *, num_clips: int, duration_min: float, duration_max: float) -> str:
    dur_range = f"{int(duration_min)}-{int(duration_max)}"
    return (
        "Sen dünyanın en iyi viral video kurgucusu, siyaset bilimcisi ve sosyal medya stratejistisin. "
        "Görevin, ekteki transkripti analiz ederek izleyicinin beyninde dopamin salgılatacak ve 'kaydırmayı durduracak' "
        f"EN VİRAL {num_clips} adet kesiti çıkarmaktır.\n\n"
        
        "VİRAL STRATEJİLER (BU KRİTERLERE ODAKLAN):\n"
        "1. DUYGUSAL ENTROPİ: Konuşmacının ses tonunun aniden yükseldiği, sinirlendiği veya büyük bir kahkaha attığı anlar altın madenidir.\n"
        "2. İTİRAF VE SIRLAR: 'Asıl bomba şurası', 'Kimse bilmiyor ama', 'İlk kez açıklıyorum' gibi kalıpların geçtiği blokları seç.\n"
        "3. ZITLIK VE ÇATIŞMA: İki farklı ismin veya zıt fikrin (Örn: Erdoğan vs. İmamoğlu) sert şekilde karşı karşıya getirildiği anları yakala.\n\n"
        
        "ZAMANLAMA VE KURGU KURALLARI:\n"
        f"- HER KLIP ZORUNLU OLARAK {dur_range} saniye araliginda olmalidir. Bu araligin disina cikma.\n"
        "- BAĞLAM PENCERESİ: Ana vurucu cümleyi bulduğunda klibi yalnız gerektiği kadar erken başlat; "
        "genelde 2-6 saniye öncesi yeterlidir. Görsel olarak konuya çok erken girmeyen, doğal açılışları tercih et.\n"
        "- BÜTÜNLÜK: Cümleleri asla ortadan kesme. Timestamp'lere %100 sadık kal.\n\n"
        
        "GÖREVLERİN:\n"
        "1. Her segment için 'hook_text' alanına metni aynen kopyalamak yerine, ÇARPICI BİR PAZARLAMA BAŞLIĞI oluştur. "
        "(Örn: 'Ekonomi kötü' yerine 'CEBİNİZDEKİ PARA NEDEN ERİYOR?')\n"
        "2. Viral potansiyeli 1-100 arası 'viral_score' ile puanla.\n"
        "3. TikTok/Shorts için hashtag'leri içeren merak uyandırıcı bir açıklama yaz.\n\n"
        
        "AKIL YÜRÜTME TALİMATI:\n"
        "JSON çıktısını üretmeden önce kendine şu soruyu sor: 'Bu klip neden keşfete düşer?' "
        "Sadece en yüksek tutma (retention) potansiyeline sahip olanları seç.\n\n"
        
        f"Çıktıyı SADECE şu JSON formatında ver: {default_segments_schema_json()}\n\n"
        f"TEKRAR HATIRLATMA: Her segment {dur_range} saniye araliginda olmak zorunda.\n\n"
        "ÖNEMLİ: Çıktıda sadece JSON olsun, açıklama ekleme.\n\n"
        f"TRANSKRİPT:\n{full_text}"
    )


def build_segment_prompt(
    full_text: str,
    *,
    limit: int,
    window_start: float,
    window_end: float,
    duration_min: float,
    duration_max: float,
) -> str:
    dur_range = f"{int(duration_min)}-{int(duration_max)}"
    return (
        "Sen profesyonel bir sosyal medya dedektifisin. "
        f"Videonun {window_start:.1f}s ile {window_end:.1f}s arasındaki kritik bölümüne odaklanıyorsun.\n\n"
        
        "GÖREVİN:\n"
        f"1. Bu dar aralıktaki EN ÇARPICI {limit} viral anı bul (Her biri {dur_range} saniye arası).\n"
        "2. HOOK OLUŞTURMA: İlk 3 saniyede izleyiciyi ekrana kilitleyecek BÜYÜK HARFLİ, provokatif bir 'hook_text' yaz.\n"
        "3. ANALİZ: Bu aralıktaki polemikleri, siyasi sarsıntıları veya duygusal patlamaları önceliklendir.\n\n"
        
        "ZAMANLAMA NOTU:\n"
        "Kliplerin başlangıcı mutlaka bir konunun girişine, bitişi ise vurucu bir sona denk gelmelidir. Yarım kalmış düşünceler viral olmaz.\n\n"
        
        f"Yanıtını SADECE JSON olarak ver: {default_segments_schema_json()}\n\n"
        "ÖNEMLİ: Başka metin ekleme, sadece saf JSON.\n\n"
        f"TRANSKRİPT PARÇASI:\n{full_text}"
    )
