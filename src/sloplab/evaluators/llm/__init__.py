"""Optional LLM adapter package. Importing this module performs NO network calls."""

from sloplab.evaluators.llm.adapter import (
    AdapterError,
    HttpLLMClient,
    LLMClient,
    LlmEvaluator,
    LLMResponse,
)

__all__ = [
    "AdapterError",
    "HttpLLMClient",
    "LLMClient",
    "LLMResponse",
    "LlmEvaluator",
]
