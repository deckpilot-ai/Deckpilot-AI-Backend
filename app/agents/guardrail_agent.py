"""Guardrail agents conforming to the multi-agent framework."""

from typing import Any

from app.agents.base import Agent
from app.services.guardrails import InputGuardrailService, OutputGuardrailService


class InputGuardrailAgent(Agent):
    """Agent responsible for sanitizing input, detecting prompt injections, and determining intent & verbosity budget."""

    name: str = "input_guardrail"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        content = context.get("content", "")
        has_attachments = context.get("has_attachments", False)
        mode = context.get("mode", "autopilot")

        result = InputGuardrailService.evaluate(
            content=content,
            has_attachments=has_attachments,
            mode=mode,
        )

        return {
            "status": "success" if result.is_safe else "blocked",
            "is_safe": result.is_safe,
            "intent": result.intent.value,
            "verbosity": result.verbosity.value,
            "sanitized_content": result.sanitized_content,
            "max_words": result.max_words,
            "direct_response": result.direct_response,
            "violation_reason": result.violation_reason,
            "metadata": result.metadata,
        }


class OutputGuardrailAgent(Agent):
    """Agent responsible for checking output size, trimming unsolicited fluff, and preventing information leakage."""

    name: str = "output_guardrail"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        content = context.get("content", "")
        input_guardrail_data = context.get("input_guardrail")

        if not input_guardrail_data:
            # Fallback evaluation if input guardrail was bypassed
            raw_input = context.get("raw_input", "")
            input_res = InputGuardrailService.evaluate(raw_input)
        else:
            from app.services.guardrails import (
                InputGuardrailResult,
                IntentCategory,
                VerbosityLevel,
            )
            input_res = InputGuardrailResult(
                is_safe=input_guardrail_data.get("is_safe", True),
                sanitized_content=input_guardrail_data.get("sanitized_content", ""),
                intent=IntentCategory(input_guardrail_data.get("intent", "unknown")),
                verbosity=VerbosityLevel(input_guardrail_data.get("verbosity", "standard")),
                max_words=input_guardrail_data.get("max_words", 250),
                direct_response=input_guardrail_data.get("direct_response"),
            )

        result = OutputGuardrailService.apply(content, input_res)

        return {
            "status": "success",
            "is_valid": result.is_valid,
            "content": result.content,
            "original_word_count": result.original_word_count,
            "final_word_count": result.final_word_count,
            "modifications": result.modifications,
        }
