"""Input and Output Guardrails for AI Chat.

Enforces intent understanding, adaptive verbosity budgets, prompt injection safety,
and strict conciseness so that simple greetings (e.g. 'Hi') or casual queries
never produce unnecessary walls of text or unsolicited feature lists.
"""

import re
import unicodedata
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    GREETING = "greeting"
    POLITENESS = "politeness"
    CAPABILITY_QUERY = "capability_query"
    CASUAL_HELP = "casual_help"
    DECK_GENERATION = "deck_generation"
    ADVISORY = "advisory"
    REVISION = "revision"
    OUT_OF_SCOPE = "out_of_scope"
    UNKNOWN = "unknown"


class VerbosityLevel(str, Enum):
    MINIMAL = "minimal"      # 1-2 sentences, max ~30 words (greetings, thanks)
    CONCISE = "concise"      # 2-4 sentences, max ~80 words (capabilities, quick Q&A)
    STANDARD = "standard"    # Structured response (advisory, planning, analysis)


# Word budget limits per verbosity level
VERBOSITY_WORD_LIMITS: dict[VerbosityLevel, int] = {
    VerbosityLevel.MINIMAL: 35,
    VerbosityLevel.CONCISE: 85,
    VerbosityLevel.STANDARD: 350,
}

# Regex patterns for greetings
GREETING_PATTERNS = [
    r"^(hi|hello|hey|hola|sup|yo|greetings|howdy|good\s*(morning|afternoon|evening|day))(\s+(there|copilot|deckpilot|assistant|bot|team|all|everyone))?(!|\.|\?|\s)*$",
    r"^(how\s+are\s+you|how's\s+it\s+going|what'?s\s+up|how\s+do\s+you\s+do)(!|\.|\?|\s)*$",
]

# Regex patterns for casual politeness / acknowledgement
POLITENESS_PATTERNS = [
    r"^(thanks(\s+a\s+lot)?|thank\s+you(\s+(so\s+much|very\s+much))?|thx|ty|much\s+appreciated)(!|\.|\?|\s)*$",
    r"^(ok|okay|cool|nice|great|awesome|got\s+it|understood|sure|alright|perfect)(!|\.|\?|\s)*$",
    r"^(bye|goodbye|see\s+you|cya)(!|\.|\?|\s)*$",
]

# Capability inquiries
CAPABILITY_PATTERNS = [
    r"^(who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|tell\s+me\s+about\s+yourself)(!|\.|\?|\s)*$",
    r"^(how\s+does\s+this\s+work|what\s+is\s+deckpilot|what\s+do\s+you\s+do)(!|\.|\?|\s)*$",
    r"^(can\s+you\s+(make|create|build)\s+(a\s+)?(presentation|deck|slides)\??)$",
]

# Casual help
HELP_PATTERNS = [
    r"^(help|can\s+you\s+help\s+me|i\s+need\s+help|assist\s+me)(!|\.|\?|\s)*$",
]

# Presentation creation triggers
PRESENTATION_KEYWORDS = [
    "create", "build", "generate", "make", "design", "draft", "produce",
    "presentation", "deck", "slide", "slides", "pitch", "pitchdeck",
    "powerpoint", "pptx", "keynote", "slideshow", "qbr", "roadmap"
]

# Prompt injection & jailbreak indicators
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"(reveal|print|show|output|leak|display)\s+(me\s+)?(your\s+)?(initial\s+|original\s+)?(system\s+prompt|prompt|instructions)",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"dan\s+mode|jailbreak|bypass\s+all\s+filters",
    r"system\s*:\s*you\s+are\s+now",
]

# Boilerplate patterns to remove from LLM responses
BOILERPLATE_PATTERNS = [
    r"^as\s+an\s+ai\s+(language\s+model|presentation\s+copilot)[,\.]?\s*",
    r"^certainly[!\.,]?\s*(i('d\s+be|\s+would\s+be)?\s+happy\s+to\s+help[!\.,]?)?\s*",
    r"^sure[!\.,]?\s*(i\s+can\s+help\s+with\s+that[!\.,]?)?\s*",
    r"^of\s+course[!\.,]?\s*",
    r"((feel\s+free\s+to\s+ask|let\s+me\s+know\s+if\s+you\s+need)[^\.\!\n]*)[!\.]?\s*$",
    r"i\s+hope\s+this\s+helps[!\.]?\s*$",
]


class InputGuardrailResult(BaseModel):
    is_safe: bool = True
    sanitized_content: str
    intent: IntentCategory
    verbosity: VerbosityLevel
    max_words: int
    direct_response: str | None = None
    violation_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutputGuardrailResult(BaseModel):
    is_valid: bool = True
    content: str
    original_word_count: int
    final_word_count: int
    modifications: list[str] = Field(default_factory=list)


class InputGuardrailService:
    """Evaluates incoming chat messages to understand intent, sanitize input, and set verbosity constraints."""

    MAX_INPUT_LENGTH = 10000

    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """Removes control characters, zero-width chars, and excessive whitespace."""
        if not text:
            return ""
        # Normalize unicode
        text = unicodedata.normalize("NFKC", text)
        # Strip zero-width spaces and control characters (except standard newlines/tabs)
        text = "".join(ch for ch in text if ch in ("\n", "\t", "\r") or unicodedata.category(ch)[0] != "C")
        # Strip whitespace per line and collapse multiple blank lines
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        # Truncate to maximum input length
        if len(text) > cls.MAX_INPUT_LENGTH:
            text = text[:cls.MAX_INPUT_LENGTH]
        return text

    @classmethod
    def check_injection(cls, text: str) -> tuple[bool, str | None]:
        """Checks for adversarial prompt injection patterns."""
        lower = text.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, lower):
                return False, f"Prompt injection pattern detected: {pattern}"
        return True, None

    @classmethod
    def classify_intent(cls, text: str, has_attachments: bool = False, mode: str = "autopilot") -> tuple[IntentCategory, VerbosityLevel, str | None]:
        """
        Classifies user message intent and determines the target verbosity budget.
        Returns (intent, verbosity, optional direct response).
        """
        if has_attachments:
            return IntentCategory.DECK_GENERATION, VerbosityLevel.STANDARD, None

        lower = text.lower().strip()

        # 1. Empty message
        if not lower:
            return IntentCategory.UNKNOWN, VerbosityLevel.MINIMAL, "How can I assist you with your presentation today?"

        # 2. Greeting intent (e.g. "Hi", "Hello", "Good morning")
        for pattern in GREETING_PATTERNS:
            if re.match(pattern, lower):
                return (
                    IntentCategory.GREETING,
                    VerbosityLevel.MINIMAL,
                    "Hello! I am your **deckpilotAI** Copilot. What presentation can I help you create today?",
                )

        # 3. Politeness / Acknowledgement (e.g. "Thanks", "Ok", "Cool")
        for pattern in POLITENESS_PATTERNS:
            if re.match(pattern, lower):
                return (
                    IntentCategory.POLITENESS,
                    VerbosityLevel.MINIMAL,
                    "You're welcome! Let me know whenever you'd like to create or refine a presentation.",
                )

        # 4. Capability inquiries (e.g. "Who are you?", "What can you do?")
        for pattern in CAPABILITY_PATTERNS:
            if re.match(pattern, lower):
                return (
                    IntentCategory.CAPABILITY_QUERY,
                    VerbosityLevel.CONCISE,
                    "I am **deckpilotAI** Copilot. I turn ideas, outlines, and documents into executive PowerPoint decks. Tell me your topic, and I will research, outline, and build your slides.",
                )

        # 5. Casual help (e.g. "Can you help me?", "Help")
        for pattern in HELP_PATTERNS:
            if re.match(pattern, lower):
                return (
                    IntentCategory.CASUAL_HELP,
                    VerbosityLevel.CONCISE,
                    "Absolutely! I can create complete presentations, formulate slide outlines, or research strategic topics. What topic are you working on?",
                )

        # 6. Mode overrides
        if mode == "ask":
            return IntentCategory.ADVISORY, VerbosityLevel.STANDARD, None
        if mode == "plan":
            has_presentation_kw = any(kw in lower for kw in PRESENTATION_KEYWORDS)
            words = lower.split()
            if has_presentation_kw or (len(words) >= 4 and not lower.endswith("?")):
                return IntentCategory.DECK_GENERATION, VerbosityLevel.STANDARD, None
            return IntentCategory.ADVISORY, VerbosityLevel.CONCISE, None

        # 7. Deck generation detection
        has_presentation_kw = any(kw in lower for kw in PRESENTATION_KEYWORDS)
        has_slide_count = bool(re.search(r"\b\d+\s*(-|\s)?(slide|slides)\b", lower))

        if has_slide_count or (has_presentation_kw and len(lower.split()) >= 3):
            return IntentCategory.DECK_GENERATION, VerbosityLevel.STANDARD, None

        # Substantial statements without question mark typically indicate deck topics
        if len(lower.split()) >= 6 and not lower.endswith("?"):
            return IntentCategory.DECK_GENERATION, VerbosityLevel.STANDARD, None

        # Default conversational question or inquiry
        return IntentCategory.ADVISORY, VerbosityLevel.CONCISE, None

    @classmethod
    def evaluate(cls, content: str, has_attachments: bool = False, mode: str = "autopilot") -> InputGuardrailResult:
        """Runs the complete input guardrail pipeline."""
        sanitized = cls.sanitize_input(content)

        # Safety check
        is_safe, violation = cls.check_injection(sanitized)
        if not is_safe:
            return InputGuardrailResult(
                is_safe=False,
                sanitized_content=sanitized,
                intent=IntentCategory.OUT_OF_SCOPE,
                verbosity=VerbosityLevel.MINIMAL,
                max_words=VERBOSITY_WORD_LIMITS[VerbosityLevel.MINIMAL],
                direct_response="I cannot fulfill requests that attempt to override system security instructions. How can I help you build a presentation?",
                violation_reason=violation,
            )

        intent, verbosity, direct_response = cls.classify_intent(sanitized, has_attachments, mode)
        max_words = VERBOSITY_WORD_LIMITS.get(verbosity, 250)

        return InputGuardrailResult(
            is_safe=True,
            sanitized_content=sanitized,
            intent=intent,
            verbosity=verbosity,
            max_words=max_words,
            direct_response=direct_response,
            violation_reason=None,
            metadata={
                "has_attachments": has_attachments,
                "mode": mode,
                "input_word_count": len(sanitized.split()),
            },
        )


class OutputGuardrailService:
    """Validates and shapes outgoing assistant responses to ensure conciseness, safety, and relevance."""

    # Phrases indicating potential internal leakage
    LEAK_PATTERNS: ClassVar[list[str]] = [
        r"COPILOT_CHAT_SYSTEM_PROMPT",
        r"PLAN_MODE_SYSTEM_PROMPT",
        r"ASK_MODE_SYSTEM_PROMPT",
        r"sk-[a-zA-Z0-9]{20,}",
    ]

    @classmethod
    def strip_boilerplate(cls, text: str) -> str:
        """Strips generic AI disclaimers and conversational filler iteratively."""
        cleaned = text.strip()
        changed = True
        while changed:
            changed = False
            for pattern in BOILERPLATE_PATTERNS:
                new_cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
                if new_cleaned != cleaned:
                    cleaned = new_cleaned
                    changed = True
        return cleaned

    @classmethod
    def check_leaks(cls, text: str) -> bool:
        """Checks for accidental leakage of system prompts or secret tokens."""
        for pattern in cls.LEAK_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    @classmethod
    def apply(cls, content: str, input_result: InputGuardrailResult) -> OutputGuardrailResult:
        """
        Applies output guardrails against the generated content based on the input context.
        Enforces word limits, strips unwanted boilerplate, and prevents giant responses for simple queries.
        """
        if not content:
            # Provide standard fallback based on intent
            content = input_result.direct_response or "How can I assist you with your presentation today?"

        modifications: list[str] = []
        original_words = len(content.split())
        cleaned = cls.strip_boilerplate(content)
        if cleaned != content:
            modifications.append("stripped_boilerplate")

        # Check for system leakage
        if cls.check_leaks(cleaned):
            cleaned = "I am ready to help you create, structure, or refine your presentation. What is your topic?"
            modifications.append("redacted_leak")

        # Specific Guardrail: If intent was GREETING or POLITENESS, NEVER allow multi-paragraph walls of text
        if input_result.intent == IntentCategory.GREETING:
            # If the response contains bullet lists, modes breakdown, or is > 35 words, enforce a crisp greeting
            has_bullets = any(cleaned.strip().startswith(b) or f"\n{b}" in cleaned for b in ["•", "*", "-", "1."])
            if original_words > input_result.max_words or has_bullets:
                cleaned = "Hello! I am your **deckpilotAI** Copilot. What presentation can I help you create today?"
                modifications.append("enforced_concise_greeting")

        elif input_result.intent == IntentCategory.POLITENESS:
            if original_words > input_result.max_words:
                cleaned = "You're welcome! Let me know whenever you'd like to work on your presentation."
                modifications.append("enforced_concise_politeness")

        elif input_result.intent in (IntentCategory.CAPABILITY_QUERY, IntentCategory.CASUAL_HELP):
            # For capability questions, limit to concise overview
            words = cleaned.split()
            if len(words) > input_result.max_words:
                cleaned = " ".join(words[:input_result.max_words]).rstrip(".,;:") + "."
                modifications.append("trimmed_to_capability_budget")

        else:
            # General word budget enforcement (e.g. max 350 words for standard chat)
            words = cleaned.split()
            max_allowed = int(input_result.max_words * 1.3)  # Allow 30% tolerance before hard cutoff
            if len(words) > max_allowed:
                cleaned = " ".join(words[:input_result.max_words]).rstrip(".,;:") + "..."
                modifications.append("trimmed_to_word_budget")

        final_words = len(cleaned.split())

        return OutputGuardrailResult(
            is_valid=True,
            content=cleaned,
            original_word_count=original_words,
            final_word_count=final_words,
            modifications=modifications,
        )
