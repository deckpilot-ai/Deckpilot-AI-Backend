"""Requirements analysis agent for interpreting user presentation briefs."""

import logging
import re
from typing import Any

from app.schemas.generation_state import PresentationGoal, PresentationType
from app.skills.skill_registry import get_skill_for_request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Directive extraction patterns
# ---------------------------------------------------------------------------
_COLOR_RE = re.compile(
    # Hex codes: #RGB or #RRGGBB
    r"(?:#[0-9a-fA-F]{3,6})"
    # OR named color explicitly: "color: blue", "primary color: navy blue", "use red"
    r"|(?:(?:primary|accent|background|secondary|color(?:s|scheme|palette)?|theme)\s*[=:\-]?\s*"
    r"((?:[a-zA-Z]{3,20}(?:\s[a-zA-Z]{3,20})?)))",
    re.IGNORECASE,
)
_DARK_LIGHT_RE = re.compile(r"\b(dark|light|minimal|minimalist)\s*(?:mode|theme|background|design)?\b", re.IGNORECASE)
_LAYOUT_RE = re.compile(
    r"\b(timeline|roadmap|two[- ]column|card[- ]grid|comparison|metrics|process|hero|closing|takeaway|image[- ]focus|quote)\b",
    re.IGNORECASE,
)
_INCLUDE_RE = re.compile(
    r"(?:include|add|show|cover|focus\s+on|highlight|must\s+have)\s+([^.!?\n]{5,120})",
    re.IGNORECASE,
)
_EXCLUDE_RE = re.compile(
    r"(?:exclude|remove|skip|omit|no|don[''t]+\s+(?:include|add|show|use))\s+([^.!?\n]{3,80})",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(
    r"(?:section[s]?|chapter[s]?|part[s]?|slide[s]?)\s*(?:\d+[:\-]?)?\s*:?\s*['\"]?([A-Z][A-Za-z0-9 ,\-&]{3,60})['\"]?",
    re.IGNORECASE,
)
_FONT_RE = re.compile(
    r"(?:use|with)?\s*(?:font|typeface|typography)\s*[=:–\-]?\s*([A-Za-z][A-Za-z0-9 \-]{2,40})",
    re.IGNORECASE,
)
_TONE_RE = re.compile(
    r"\b(professional|casual|formal|technical|friendly|bold|elegant|playful|modern|corporate|academic)\b",
    re.IGNORECASE,
)


class RequirementsAgent:
    """Extracts presentation goal, target slide count, audience, domain, and visual needs."""

    @classmethod
    def extract_document_title(cls, sample_text: str, reference_files: list[str] | None = None) -> str:
        """Extract a meaningful title from document text or filename when prompt is generic."""
        if sample_text:
            # 1. Look for repeated title patterns (e.g. Chapter heading printed above section title)
            m_rep = re.search(r'([A-Z][A-Za-z0-9\s,\'’\-]{4,45})\s+\1', sample_text[:1500])
            if m_rep:
                cand = m_rep.group(1).strip()
                if len(cand.split()) >= 2:
                    return cand

            # 2. Look for chapter or numbered title e.g. "5 – The Rise of Empires" or "Chapter 12 - Understanding Markets"
            m_chap = re.search(
                r'(?:(?:chapter|ch\.)\s*\d+\s*[-–—:]*|\b\d+\s*[-–—]\s*)([A-Z][A-Za-z0-9\s,\'’\-]{3,50}?)(?:\n|\r|\.|\s{2,}|\bThere\b|\bReprint\b|$)',
                sample_text[:1500],
                re.IGNORECASE,
            )
            if m_chap:
                cand = m_chap.group(1).strip()
                # Clean any duplicated trailing words
                words = cand.split()
                half = len(words) // 2
                if half >= 2 and words[:half] == words[half:2*half]:
                    cand = " ".join(words[:half])
                if len(cand) >= 4:
                    return cand

            # 3. Look for strong header line in first 5 lines
            lines = [l.strip() for l in sample_text[:1000].splitlines() if l.strip()]
            for line in lines[:5]:
                clean_l = re.sub(r'^\d+\s+', '', line).strip()
                if 4 <= len(clean_l) <= 50 and not re.search(r'\b(?:page|copyright|reprint|isbn|edition)\b', clean_l, re.I):
                    if any(w[0].isupper() for w in clean_l.split() if w):
                        return clean_l

        # Fallback to non-generic reference filename
        for f in (reference_files or []):
            stem = re.sub(r'\.(?:pdf|docx|pptx|xlsx|txt)$', '', f, flags=re.I)
            stem = re.sub(r'[-_]+', ' ', stem).strip()
            if not re.match(r'^(?:source\s*data|data|document|input|sample|upload|file|test)[\d\s\-_()]*$', stem, re.I):
                # Clean NCERT prefixes e.g. "NCERT Grade 7 - Chapter 12 - Understanding Markets" -> "Understanding Markets"
                m_ncert = re.search(r'(?:chapter\s*\d+\s*[-–—:]*)\s*([A-Za-z0-9\s,\'’\-]+)', stem, re.I)
                if m_ncert:
                    return m_ncert.group(1).strip()
                return stem

        return ""

    @classmethod
    def extract_explicit_slides(cls, user_prompt: str) -> list[dict[str, Any]]:
        """Extract explicit slide-by-slide structure, titles, bullets, and layout hints from prompt."""
        slides: list[dict[str, Any]] = []
        lines = user_prompt.strip().splitlines()
        
        current_slide: dict[str, Any] | None = None
        
        # Regex to detect a slide header line
        # e.g., "Slide 1: Executive Summary", "Slide 1 - Problem", "1. Solution Architecture", "1) Market Overview"
        slide_header_re = re.compile(
            r"^(?:(?:slide|page|section|part)\s*(\d+)[:\.\-\s]+|(\d+)[\.\)]\s+)(.*)$",
            re.IGNORECASE,
        )
        bullet_re = re.compile(r"^\s*[-*•>]\s+(.*)$")
        
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            
            m = slide_header_re.match(trimmed)
            if m:
                num_str = m.group(1) or m.group(2)
                title_cand = m.group(3).strip()
                
                if title_cand and len(title_cand) >= 2:
                    if current_slide:
                        slides.append(current_slide)
                    
                    # Extract layout hint if in parentheses e.g. "Roadmap (Timeline)" or "[Layout: Metrics Grid]"
                    layout_cand = ""
                    m_lay = re.search(r"[\(\[\{](?:layout|style|template|pattern)?\s*:?\s*([a-zA-Z0-9_\-\s]+)[\)\]\}]$", title_cand, re.IGNORECASE)
                    if m_lay:
                        inner = m_lay.group(1).strip().lower().replace(" ", "_").replace("-", "_")
                        inner = re.sub(r"^(?:layout|template|style)_+", "", inner)
                        if inner in (
                            "timeline", "timeline_band", "roadmap", "two_column", "card_grid", "comparison",
                            "metrics", "metrics_grid", "process", "process_steps", "hero",
                            "closing", "quote", "council_eight", "big_questions",
                            "stepped_value_chain", "two_highways", "forts_quote_emblem",
                            "concept_definition_image", "table_focus", "chart_focus",
                            "three_column", "grid", "cards", "executive_summary"
                        ):
                            layout_cand = inner
                            title_cand = title_cand[:m_lay.start()].strip()
                    
                    headline = title_cand
                    bullets = []
                    if " - " in title_cand:
                        parts = title_cand.split(" - ", 1)
                        headline = parts[0].strip()
                        if len(parts) > 1 and parts[1].strip():
                            bullets.append(parts[1].strip())
                    elif ":" in title_cand and len(title_cand.split(":")[0].split()) <= 4:
                        parts = title_cand.split(":", 1)
                        headline = parts[0].strip()
                        if len(parts) > 1 and parts[1].strip():
                            bullets.append(parts[1].strip())
                            
                    current_slide = {
                        "slideId": f"s{len(slides) + 1:02d}",
                        "headline": headline,
                        "purpose": headline,
                        "message": headline,
                        "bullets": bullets,
                        "layoutHint": layout_cand,
                    }
                    continue
            
            # If current_slide is active, check if this line is a bullet or detail for it
            if current_slide is not None:
                bm = bullet_re.match(trimmed)
                if bm:
                    current_slide["bullets"].append(bm.group(1).strip())
                elif trimmed.startswith(("Takeaway:", "Note:", "Key message:", "Conclusion:")):
                    current_slide["takeaway"] = trimmed.split(":", 1)[1].strip()
                elif len(trimmed) < 140 and not re.match(r"^(?:create|generate|make|build|prepare|please|also)\b", trimmed, re.I):
                    current_slide["bullets"].append(trimmed)

        if current_slide:
            slides.append(current_slide)
            
        return slides if len(slides) >= 2 else []

    @classmethod
    def extract_user_directives(cls, user_prompt: str) -> str:
        """Parse ALL explicit user instructions from the prompt into a structured directive block.

        Captures: colors, themes, dark/light mode, fonts, tone, preferred layouts,
        named sections/chapters, include/exclude rules, and explicit slide breakdowns.
        The result is injected verbatim into every downstream LLM call so no user
        instruction is ever silently dropped due to prompt truncation.
        """
        directives: list[str] = []

        # Colors / palette — hex codes (#RRGGBB) and explicitly named colors
        for m in _COLOR_RE.finditer(user_prompt):
            # Named color is in group 1; hex code is the full match with no group
            val = (m.group(1) or m.group(0)).strip().rstrip(",.:") if m.lastindex else m.group(0).strip()
            if val and len(val) >= 3:
                directives.append(f"COLOR: {val}")

        # Dark / light / minimal mode
        for m in _DARK_LIGHT_RE.finditer(user_prompt):
            directives.append(f"THEME: {m.group(1).lower()} mode")

        # Font preference
        for m in _FONT_RE.finditer(user_prompt):
            directives.append(f"FONT: {m.group(1).strip()}")

        # Tone adjectives
        tone_hits = {m.group(1).lower() for m in _TONE_RE.finditer(user_prompt)}
        if tone_hits:
            directives.append(f"TONE: {', '.join(sorted(tone_hits))}")

        # Layout preferences
        layout_hits = {
            m.group(1).lower().replace(" ", "_").replace("-", "_")
            for m in _LAYOUT_RE.finditer(user_prompt)
        }
        if layout_hits:
            directives.append(f"PREFERRED_LAYOUTS: {', '.join(sorted(layout_hits))}")

        # Explicit section/chapter names
        for m in _SECTION_RE.finditer(user_prompt):
            directives.append(f"SECTION: {m.group(1).strip()}")

        # Must-include items
        for m in _INCLUDE_RE.finditer(user_prompt):
            val = m.group(1).strip().rstrip(".,")
            if len(val) > 4:
                directives.append(f"INCLUDE: {val}")

        # Must-exclude items
        for m in _EXCLUDE_RE.finditer(user_prompt):
            val = m.group(1).strip().rstrip(".,")
            if len(val) > 2:
                directives.append(f"EXCLUDE: {val}")

        # Check for explicit slide outline in prompt
        explicit_slides = cls.extract_explicit_slides(user_prompt)
        if explicit_slides:
            directives.append("EXPLICIT_SLIDE_OUTLINE (MUST ADHERE STRICTLY IN EXACT ORDER):")
            for s in explicit_slides:
                slide_line = f"  * {s.get('slideId')}: {s.get('headline')}"
                if s.get('layoutHint'):
                    slide_line += f" [Layout: {s.get('layoutHint')}]"
                directives.append(slide_line)
                for b in s.get('bullets', []):
                    directives.append(f"      - {b}")

        # Deduplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for d in directives:
            if d not in seen:
                seen.add(d)
                unique.append(d)

        return "\n".join(unique)

    @classmethod
    def analyze_requirements(
        cls,
        user_prompt: str,
        reference_files: list[str] | None = None,
        reference_asset_count: int = 0,
        grounded_text_length: int = 0,
        target_slide_count: int | None = None,
        sample_text: str = "",
    ) -> PresentationGoal:
        prompt_lower = user_prompt.lower()
        sample_lower = (sample_text or "").lower()
        combined_text = f"{prompt_lower}\n{sample_lower[:3000]}"
        files = reference_files or []

        NUMBER_WORDS = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
            "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
            "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50
        }

        # 1. Slide Count detection (supports "12 page", "12 slides", "deck of 12", "12-page", "twelve slides")
        explicit_slides = cls.extract_explicit_slides(user_prompt)
        if target_slide_count is not None and target_slide_count > 0:
            slide_count = target_slide_count
        elif explicit_slides:
            slide_count = len(explicit_slides)
        else:
            count_match = re.search(
                r"\b(\d+)\s*[-_]?(?:slides?|pages?|pgs?|screens?|cards?|sections?|parts?)\b"
                r"|\b(?:deck|presentation|slides?|pages?)\s+of\s+(\d+)\b"
                r"|\b(?:target|count|length|size)\s*[:=]?\s*(\d+)\b"
                r"|\b(\d+)\s*[-_]?(?:slide|page)\s+(?:deck|presentation|ppt|pptx)\b",
                user_prompt,
                re.IGNORECASE,
            )
            detected_num = None
            if count_match:
                for grp in count_match.groups():
                    if grp and grp.isdigit():
                        detected_num = int(grp)
                        break

            if detected_num is None:
                for word, num in NUMBER_WORDS.items():
                    if re.search(rf"\b{word}\s*[-_]?(?:slides?|pages?|pgs?|screens?|cards?|deck|parts?)\b|\b(?:deck|presentation)\s+of\s+{word}\b", user_prompt, re.IGNORECASE):
                        detected_num = num
                        break

            if detected_num is not None:
                slide_count = max(1, min(detected_num, 60))
            elif "quick" in prompt_lower or "short" in prompt_lower or "summary" in prompt_lower:
                slide_count = 5
            elif "investor" in prompt_lower or "pitch" in prompt_lower:
                slide_count = 10
            elif reference_asset_count > 10 and grounded_text_length > 5000:
                # In-depth textbook or extensive reference doc default
                slide_count = 14
            else:
                slide_count = 8

        # 2. Presentation Type classification
        if "pitch" in prompt_lower or "investor" in prompt_lower or "fundraise" in prompt_lower or "seed" in prompt_lower:
            p_type = PresentationType.PITCH_DECK
            audience = "Venture Capitalists & Angel Investors"
            tone = "dynamic_visionary"
        elif "architecture" in prompt_lower or "cloud" in prompt_lower or "ai" in prompt_lower or "saas" in prompt_lower or "system" in prompt_lower:
            p_type = PresentationType.TECHNICAL_ARCHITECTURE
            audience = "CTOs, Technical Leads & Architects"
            tone = "modern_technical"
        elif "financial" in prompt_lower or "earning" in prompt_lower or "revenue" in prompt_lower or "budget" in prompt_lower or "q1" in prompt_lower or "q2" in prompt_lower or "q3" in prompt_lower or "q4" in prompt_lower:
            p_type = PresentationType.FINANCIAL_REVIEW
            audience = "CFOs, Executive Board & Investors"
            tone = "analytical_restrained"
        elif any(k in combined_text for k in ("history", "ncert", "chapter", "education", "lecture", "empire", "civilisation", "civilization", "dynasty", "bce", "archaeolog", "kautilya", "ashoka")):
            p_type = PresentationType.RESEARCH_EDUCATION
            audience = "Students, Educators & Domain Specialists"
            tone = "authoritative_editorial"
        elif "consulting" in prompt_lower or "transformation" in prompt_lower or "market entry" in prompt_lower:
            p_type = PresentationType.CONSULTING_DECK
            audience = "Senior Leadership & Strategy Teams"
            tone = "structured_insight_driven"
        else:
            p_type = PresentationType.BUSINESS_STRATEGY
            audience = "Executive Leadership & Board"
            tone = "executive_authoritative"

        # 3. Topic Extraction
        first_line = user_prompt.strip().split("\n")[0]
        clean_topic = re.sub(
            r"^(?:generate|create|make|build|prepare|produce|design)\s+(?:a|an)?\s*(?:\d+[- ]*(?:slides?|pages?|pgs?)\s+)?(?:presentation|deck|ppt|pptx)?\s*(?:on|about|for|from|of)?\s*",
            "",
            first_line,
            flags=re.IGNORECASE,
        ).strip()
        # Strip trailing presentation words
        clean_topic = re.sub(r"\s+(?:presentation|deck|ppt|pptx)$", "", clean_topic, flags=re.I).strip()

        # Check if extracted prompt topic is generic or instruction-only
        is_generic_prompt = (
            not clean_topic
            or len(clean_topic) < 3
            or bool(re.match(r"^(?:create|generate|make|build|prepare)?\s*(?:\d+[- ]*(?:slides?|pages?|pgs?))?\s*(?:ppt|pptx|presentation|deck|summary)?$", clean_topic, re.I))
            or bool(re.match(r"^(?:source\s*data(?:\.pdf)?|attached\s*(?:file|document|doc|pdf)|this\s*(?:document|pdf|file))$", clean_topic, re.I))
        )

        doc_title = cls.extract_document_title(sample_text, files)
        if is_generic_prompt and doc_title:
            topic = doc_title
        elif clean_topic and not is_generic_prompt:
            topic = clean_topic[:80].strip()
        elif doc_title:
            topic = doc_title
        else:
            topic = "Executive Strategic Review"

        # 4. Check references
        has_docs = reference_asset_count > 0 or len(files) > 0 or grounded_text_length > 0 or bool(sample_text)
        has_ppt = any(f.endswith(".pptx") for f in files)

        # 5. Determine chart/table needs
        req_charts = []
        if p_type in (PresentationType.FINANCIAL_REVIEW, PresentationType.PITCH_DECK, PresentationType.BUSINESS_STRATEGY):
            req_charts.extend(["column", "bar", "line"])
        
        req_tables = []
        if "table" in prompt_lower or p_type == PresentationType.FINANCIAL_REVIEW:
            req_tables.append("comparison_table")

        return PresentationGoal(
            topic=topic,
            objective=f"Deliver a clear, authoritative presentation on {topic} tailored to {audience}.",
            audience=audience,
            industry=p_type.value,
            presentation_type=p_type,
            target_slide_count=slide_count,
            tone=tone,
            narrative_arc="pyramid" if p_type != PresentationType.RESEARCH_EDUCATION else "chronological_thematic",
            has_reference_docs=has_docs,
            has_reference_ppt=has_ppt,
            required_charts=req_charts,
            required_tables=req_tables,
            user_directives=cls.extract_user_directives(user_prompt),
            explicit_slides=explicit_slides,
        )
