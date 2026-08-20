"""
backend/api/routes/settings.py
===============================
AI motoru durum takibi ve bağlantı test endpoint'leri.
"""
from __future__ import annotations

import os
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.security import AuthContext, require_policy
from backend.services.viral_analyzer import ViralAnalyzer, _is_usable_key

router = APIRouter(prefix="/api/settings", tags=["settings"])


class TestAiEngineRequest(BaseModel):
    engine: str = Field(default="nvidia", description="Test edilecek AI motoru: nvidia, cloud, lmstudio, local")


def _mask_key(key: str | None) -> str | None:
    if not _is_usable_key(key):
        return None
    stripped = (key or "").strip()
    if len(stripped) <= 8:
        return "****"
    return f"{stripped[:5]}...{stripped[-4:]}"


@router.get("/ai-status")
async def get_ai_status(
    auth: AuthContext = Depends(require_policy("view_settings")),
) -> dict[str, Any]:
    """AI motorlarının ve API konfigürasyonlarının canlı durumunu döner."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    lmstudio_host = os.environ.get("LMSTUDIO_HOST", "").strip()

    openrouter_valid = _is_usable_key(openrouter_key)
    nvidia_valid = _is_usable_key(nvidia_key)
    lmstudio_valid = bool(lmstudio_host)

    if openrouter_valid:
        effective_default = "cloud"
    elif nvidia_valid:
        effective_default = "nvidia"
    elif lmstudio_valid:
        effective_default = "lmstudio"
    else:
        effective_default = "fallback"

    return {
        "status": "ok",
        "effective_default_engine": effective_default,
        "engines": {
            "nvidia": {
                "configured": nvidia_valid,
                "masked_key": _mask_key(nvidia_key),
                "model": os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
                "label": "Cloud (NVIDIA NIM)",
            },
            "cloud": {
                "configured": openrouter_valid,
                "masked_key": _mask_key(openrouter_key),
                "model": os.environ.get("OPENROUTER_MODEL", "moonshotai/kimi-k2.5"),
                "fallback_to_nvidia": not openrouter_valid and nvidia_valid,
                "label": "Cloud (OpenRouter)",
            },
            "lmstudio": {
                "configured": lmstudio_valid,
                "host": lmstudio_host or "http://localhost:1234",
                "model": os.environ.get("LMSTUDIO_MODEL", "local-model"),
                "label": "Local (LM Studio)",
            },
            "local": {
                "configured": True,
                "label": "Local (Kural Bazlı Fallback)",
            },
        },
    }


@router.post("/test-ai")
async def test_ai_engine(
    payload: TestAiEngineRequest,
    auth: AuthContext = Depends(require_policy("view_settings")),
) -> dict[str, Any]:
    """Seçilen AI motorunun erişilebilirliğini ve bağlantısını doğrulayan test çağrısı yapar."""
    target_engine = (payload.engine or "nvidia").strip().lower()
    analyzer = ViralAnalyzer(engine=target_engine)

    client = analyzer._resolve_client()
    adapter = analyzer._resolve_adapter()
    actual_engine = analyzer._engine_label()

    if client is None or adapter is None:
        return {
            "ok": False,
            "engine": target_engine,
            "actual_engine": actual_engine,
            "message": f"{target_engine.upper()} motoru için API anahtarı veya servis konfigürasyonu eksik.",
        }

    try:
        dummy_prompt = "Tek kelimelik test yanıtı ver: 'OK'"
        result = analyzer._call_llm(client, adapter, dummy_prompt, include_reasoning=False)
        return {
            "ok": True,
            "engine": target_engine,
            "actual_engine": actual_engine,
            "message": f"Bağlantı başarılı ({actual_engine}).",
            "sample_response": result,
        }
    except Exception as exc:
        return {
            "ok": False,
            "engine": target_engine,
            "actual_engine": actual_engine,
            "message": f"Bağlantı testi başarısız: {str(exc)}",
        }
