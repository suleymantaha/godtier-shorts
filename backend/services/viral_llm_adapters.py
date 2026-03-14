"""Provider adapters for ViralAnalyzer LLM calls."""

from __future__ import annotations

from dataclasses import dataclass

SYSTEM_PROMPT = "Sen profesyonel bir viral analiz uzmanısın. Yanıtın sadece saf JSON olmalı."


@dataclass(frozen=True)
class ViralLLMAdapter:
    engine: str
    model_name: str

    def build_request_kwargs(self, prompt: str, *, include_reasoning: bool) -> dict:
        request_kwargs: dict = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        self._apply_provider_options(request_kwargs, include_reasoning=include_reasoning)
        return request_kwargs

    def _apply_provider_options(self, request_kwargs: dict, *, include_reasoning: bool) -> None:
        _ = include_reasoning


class OpenRouterAdapter(ViralLLMAdapter):
    def _apply_provider_options(self, request_kwargs: dict, *, include_reasoning: bool) -> None:
        request_kwargs["extra_headers"] = {
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "GodTierShorts",
        }
        if include_reasoning:
            request_kwargs["extra_body"] = {"include_reasoning": True}


class LMStudioAdapter(ViralLLMAdapter):
    pass


def create_adapter(engine: str, *, cloud_model_name: str, local_model_name: str) -> ViralLLMAdapter | None:
    if engine == "cloud":
        return OpenRouterAdapter(engine=engine, model_name=cloud_model_name)
    if engine == "lmstudio":
        return LMStudioAdapter(engine=engine, model_name=local_model_name)
    return None


def engine_label(engine: str) -> str:
    if engine == "cloud":
        return "Cloud (OpenRouter)"
    if engine == "lmstudio":
        return "LM Studio"
    return f"{engine} (fallback)"
