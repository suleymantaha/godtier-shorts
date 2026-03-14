"""Pure helpers for ViralAnalyzer prompting/parsing/fallback logic."""

from __future__ import annotations

import json
from typing import Callable


def clip_words(text: str, limit: int) -> str:
    return " ".join(text.split()[:limit]).strip()


def normalize_hook(text: str) -> str:
    hook = " ".join(text.split()[:7]).strip()
    return (hook or "DIKKAT CEKEN AN").upper()


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
        return {
            "segments": [
                {
                    "start_time": full_start,
                    "end_time": full_end,
                    "hook_text": normalize_hook(joined_text),
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
        title = clip_words(joined_text, 12) or "Otomatik Secilen Klip"
        selected.append(
            {
                "start_time": candidate["start_time"],
                "end_time": candidate["end_time"],
                "hook_text": normalize_hook(joined_text),
                "ui_title": title,
                "social_caption": f"{title} #shorts #viral",
                "viral_score": max(60, min(95, int(candidate["score"] * 5))),
            }
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
        "- BAĞLAM PENCERESİ: Ana vurucu cümleyi (punchline) bulduğunda, klibi o cümleden en az 10 saniye ÖNCE başlat (bağlam kurmak için) "
        "ve düşünce bittikten 5 saniye SONRA bitir.\n"
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
