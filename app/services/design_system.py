"""Versioned consulting design contract shared by AI and deterministic rendering.

Adapted from the user-supplied consulting-pptx-design skill. Its original source
is retained in docs/consulting-pptx-design; runtime uses Python, not model code.
"""

import re
from typing import Any

DESIGN_SYSTEM_VERSION = "consulting-pptx-design/1.0"
LAYOUTS = (
    "hero", "roadmap", "concept", "comparison", "card_grid", "metrics_grid",
    "process_steps", "timeline", "case_study", "quote", "dark_panel", "takeaways", "closing",
    "two_column", "editorial", "hierarchy", "image_focus", "bar_chart",
    "big_questions", "timeline_columns", "diagram_hierarchy", "saptanga", "stat_callouts",
    "dark_quote", "legacy", "two_column_definition",
    "A1", "A2", "A3", "A4", "A5", "A6", "A8", "A10", "A11", "A13", "A14", "A15",
    "A16", "A17", "A18", "A24", "A25", "A26", "A27", "A28", "A29", "A30",
)

DECK_DESIGN_SYSTEM_PROMPT = """
CONSULTING-PPTX-DESIGN v1.0
Use comparisons for contrasts, timelines only for dated source milestones,
3-4 connected steps for actual processes, 2-4 stats only when source numbers
exist, 2-6 cards for grouped ideas. Preserve the topic rather than forcing a
business/investor narrative onto history, education, science or training.

No em dashes, invented figures, quotes, case studies, captions or filler.
Every factual assertion must be supported by the user brief or supplied sources.
Missing evidence: omit the claim or label it as an open question/proposal.
Never invent realistic metrics to fill cards. Do not invent documentary imagery.
Select real source images only by the supplied imageArtifactId; if none fits,
use text/cards instead. Never request generated substitute photos.

Writer JSON may additionally include: eyebrow, chapter, takeaway, speakerNotes,
metrics: [{value, label, sourceQuote}], quote: {text, attribution, sourceQuote},
imageArtifactId. sourceQuote must be a verbatim excerpt from supplied evidence;
the metric value and label, or quote text and attribution, must occur in that
excerpt. Unsupported special content is omitted by the application.
Use concise, source-backed bullets; no fixed minimum count and no filler.
The renderer owns typography, components and geometry. QA must not claim
full visual inspection unless every slide was actually rendered and inspected.
"""

PALETTES = {
    "history": ("#6B221C", "#E4791F", "#F7EEE3"),
    "governance": ("#0C3B39", "#0E7C7B", "#E9F3F1"),
    "sustainability": ("#0F2922", "#059669", "#F1F6F4"),
    "markets": ("#132A52", "#2563EB", "#EEF2F8"),
    "health": ("#164B50", "#0D9488", "#EDF5F4"),
    "technology": ("#0F172A", "#0284C7", "#F0F9FF"),
}


def strip_citations(text: str) -> str:
    """Strip raw document citations, filenames, page links, and bracketed anchors."""
    if not text:
        return ""
    val = str(text)
    # 1. Parenthetical / bracketed file references e.g. (source data.pdf#page=15), [doc.pdf:12], (source.pdf)
    val = re.sub(
        r"\s*\(\s*(?:source\s*:?\s*)?[^)\s]+\.(?:pdf|docx?|pptx?|xlsx?|txt|csv|html?)(?:#(?:page=\d+|[a-zA-Z0-9_\-]+))?\s*(?:,\s*p(?:age|\.)\s*\d+)?\s*\)",
        "",
        val,
        flags=re.IGNORECASE,
    )
    val = re.sub(
        r"\s*\[\s*(?:source\s*:?\s*)?[^\]\s]+\.(?:pdf|docx?|pptx?|xlsx?|txt|csv|html?)(?:#(?:page=\d+|[a-zA-Z0-9_\-]+))?\s*(?:,\s*p(?:age|\.)\s*\d+)?\s*\]",
        "",
        val,
        flags=re.IGNORECASE,
    )
    # 2. Standalone file links with anchors e.g. source data.pdf#page=15, report.pdf#page=3
    val = re.sub(
        r"\b(?:source\s*:?\s*)?[a-zA-Z0-9_\- ]+\.(?:pdf|docx?|pptx?|xlsx?)(?:#(?:page=\d+|[a-zA-Z0-9_\-]+))",
        "",
        val,
        flags=re.IGNORECASE,
    )
    # 3. Clean up any trailing space before punctuation e.g. "territories ." -> "territories."
    val = re.sub(r"\s+([.,;:!?])", r"\1", val)
    return val


def clean_text(value: Any) -> str:
    cleaned = strip_citations(str(value or ""))
    cleaned = cleaned.replace("\u2014", " - ").replace("**", "").replace("Â·", " • ").replace("â€”", " - ").replace("", "")
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def default_brand(topic: str) -> dict[str, Any]:
    from app.services.deck_archetypes import PaletteGenerator
    tokens = PaletteGenerator.generate_palette(topic)
    
    domain = "markets"
    for key, words in (
        ("history", r"history|heritage|empire|medieval|maratha|harapp|civilisation|civilization"),
        ("governance", r"civic|governance|federal|government|parliament|legislature|democracy|constitution"),
        ("sustainability", r"sustainab|climate|renewable|environment"),
        ("health", r"health|medical|biotech|clinical"),
        ("technology", r"technology|software|\bAI\b|kubernetes|cloud|saas"),
    ):
        if re.search(words, topic, re.IGNORECASE):
            domain = key
            break
            
    return {
        "titleFont": {"name": "Cambria"},
        "bodyFont": {"name": "Calibri"},
        "colors": {
            "ink": tokens.ink,
            "primary": tokens.primary,
            "secondary": tokens.secondary,
            "accent": tokens.primary,
            "tint_a": tokens.tint_a,
            "tint_b": tokens.tint_b,
            "alert": tokens.alert,
            "background": "#FFFFFF",
            "paper": "#FAFAF9",
            "neutral": tokens.tint_a,
            "card_fill": tokens.tint_a,
        },
        "designSystem": DESIGN_SYSTEM_VERSION,
        "subject": domain,
    }


def normalize_brand(brand: Any, topic: str) -> dict[str, Any]:
    result = default_brand(topic)
    colors = brand.get("colors", {}) if isinstance(brand, dict) else {}
    for key in ("ink", "primary", "secondary", "accent", "tint_a", "tint_b", "alert", "neutral", "card_fill", "paper"):
        value = colors.get(key) if isinstance(colors, dict) else None
        if isinstance(value, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
            result["colors"][key] = "#" + value.lstrip("#")
    
    # Maintain backwards compatibility aliases
    if "primary" in result["colors"] and "accent" not in colors:
        result["colors"]["accent"] = result["colors"]["primary"]
    if "tint_a" in result["colors"] and "neutral" not in colors:
        result["colors"]["neutral"] = result["colors"]["tint_a"]

    # A light primary breaks the dark-slide treatment. Reject it deterministically.
    primary = result["colors"]["primary"].lstrip("#")
    if sum(int(primary[i:i + 2], 16) for i in (0, 2, 4)) > 330:
        result["colors"]["primary"] = default_brand(topic)["colors"]["primary"]
    return result


SUBJECT_ARCHITECTURE_PROMPT = """
SUBJECT-AWARE PRESENTATION ARCHITECTURE
Choose structure from the subject and the meaning of each slide, not a fixed template.
History: illustrated opening, chronological milestones, maps, evidence-led editorial
pages, causes/consequences, and a legacy/open-questions ending.
Civics/governance: institutions and roles, hierarchy (only for actual tiers), power
comparisons, constitutional principles, real civic examples and a discussion ending.
Economics: definitions, relationships, production/distribution flows, source data,
trade-offs, everyday examples and a decision/question ending.
Science/environment: mechanisms, diagrams, observed evidence, comparisons and applications.
Additional layouts: editorial (unboxed reading), hierarchy (actual tiers), image_focus
(a relevant source figure with explanation), bar_chart (comparable numeric metrics
with the same units, each supported by sourceQuote). Limit card_grid to genuinely parallel
ideas; do not alternate card_grid and two_column throughout the deck. Keep related
slides visually consistent, while selecting distinct structures for different content.
Opening: meaningful chapter title, audience/context, one short subtitle and at most
three concise points. End: synthesis and a relevant open question, not another lesson
page or a generic sales pitch. The closing should feel conclusive.
Use source images whose supplied caption/page context matches the slide. Uploaded
standalone images are available too. Never use QR codes, logos or fragments as
documentary illustrations. Include imageCaption only from supplied source context.
Writer: preserve each planned slideId, topic, purpose and sequence. Never move a
topic to another slide or restart the chapter within a batch. Retain all requested
topics. Put extended explanations in speakerNotes, not oversized content boxes.
"""
DECK_DESIGN_SYSTEM_PROMPT += SUBJECT_ARCHITECTURE_PROMPT


def _extract_topics_from_grounding(grounding: str, count: int) -> list[tuple[str, str, str]]:
    """Dynamically extract slide topics from source document text.

    Returns a list of (title, layout_hint, chapter_label) tuples derived entirely
    from headings, section titles, and key phrases found in the grounding text.
    No hardcoded content is used — every item comes from the document.
    """
    topics: list[tuple[str, str, str]] = []

    # --- Pattern 1: Numbered/lettered headings (e.g. "1. Introduction", "Chapter 3 – Markets") ---
    heading_re = re.compile(
        r"(?:^|\n)"
        r"(?:chapter|section|unit|part|topic|lesson|module|ch\.?)?\s*"
        r"(?:\d+[\.\-–—:)]?\s*)?"
        r"([A-Z][A-Za-z0-9 ,\''&:\-]{4,70})"
        r"(?:\n|\r|\.{2,}|\t|\s{3,}|$)",
        re.MULTILINE,
    )
    seen: set[str] = set()
    for m in heading_re.finditer(grounding[:8000]):
        raw = m.group(1).strip().rstrip(".")
        key = raw.casefold()
        if key in seen or len(raw) < 5:
            continue
        # Skip lines that are clearly body prose (long sentences)
        if raw.count(" ") > 10:
            continue
        seen.add(key)
        topics.append(raw)

    # --- Pattern 2: Bold/title-cased short phrases (**bold**, ALL CAPS short) ---
    bold_re = re.compile(r"\*\*([A-Za-z][A-Za-z0-9 &,:\-']{4,60})\*\*")
    caps_re = re.compile(r"\b([A-Z][A-Z0-9 &,:\-]{3,40}[A-Z])\b")
    for m in bold_re.finditer(grounding[:6000]):
        raw = m.group(1).strip()
        key = raw.casefold()
        if key not in seen and len(raw) >= 5:
            seen.add(key)
            topics.append(raw)
    for m in caps_re.finditer(grounding[:4000]):
        raw = m.group(1).strip().title()
        key = raw.casefold()
        if key not in seen and len(raw) >= 5 and raw.count(" ") <= 6:
            seen.add(key)
            topics.append(raw)

    # If we still have very few topics, split the first 3000 chars into sentences
    # and pick the shortest noun-phrase starters as candidate titles.
    if len(topics) < max(count, 3):
        sentences = re.split(r"(?<=[.!?])\s+", grounding[:3000])
        for sent in sentences:
            sent = sent.strip()
            # Take up to the first comma or colon as a short phrase
            phrase = re.split(r"[,;:\-–—]", sent)[0].strip()
            if 5 <= len(phrase) <= 70 and phrase.count(" ") <= 8:
                key = phrase.casefold()
                if key not in seen:
                    seen.add(key)
                    topics.append(phrase)
            if len(topics) >= count * 2:
                break

    # --- Assign layout hints based on content-type keywords ---
    LAYOUT_KEYWORDS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"\bcompare|contrast|versus|vs\b", re.I), "comparison"),
        (re.compile(r"\bstep[s]?|process|workflow|phase[s]?\b", re.I), "process_steps"),
        (re.compile(r"\btime(?:line|period)|century|decade|\bBCE\b|\bCE\b|\b\d{3,4}\b", re.I), "timeline"),
        (re.compile(r"\bstat[s]?|metric[s]?|number[s]?|percent|figure[s]?|data\b", re.I), "metrics_grid"),
        (re.compile(r"\bwhy|cause[s]?|reason[s]?|factor[s]?|impact[s]?|effect[s]?\b", re.I), "card_grid"),
        (re.compile(r"\blegacy|heritage|enduring|lasting|long.?term\b", re.I), "closing"),
        (re.compile(r"\bintroduction|overview|background|context|what is\b", re.I), "concept"),
        (re.compile(r"\bconclusion|summary|takeaway[s]?|lesson[s]?|key points\b", re.I), "takeaways"),
        (re.compile(r"\bchapter[s]?|agenda|outline|roadmap|plan\b", re.I), "roadmap"),
        (re.compile(r"\bcase study|example|scenario|story\b", re.I), "case_study"),
    ]

    def _layout_for(text: str) -> str:
        for pattern, hint in LAYOUT_KEYWORDS:
            if pattern.search(text):
                return hint
        return "two_column"

    # Build slide tuples
    result: list[tuple[str, str, str]] = []
    for i, topic in enumerate(topics[:count]):
        layout = "hero" if i == 0 else _layout_for(topic)
        chapter = f"Section {i + 1}"
        result.append((topic, layout, chapter))

    return result


def fallback_plan(prompt: str, count: int | None = None, title: str | None = None, grounding: str = "") -> dict[str, Any]:
    """Emergency offline outline used only when ALL LLM providers have failed.

    Every slide title and topic is extracted dynamically from the grounding
    (source document text).  No hardcoded content or invented facts are used.
    If the grounding is empty, generic numbered placeholders are produced so the
    slide_writer agent can still attempt to fill them using the user prompt.
    """
    match = re.search(r"\b(\d+)\s*[- ]?(?:slides?|pages?)\b", prompt, re.IGNORECASE)
    count = count or (int(match.group(1)) if match else 5)
    if not 1 <= count <= 60:
        count = max(1, min(count, 60))

    # --- Derive title from grounding or prompt, never hardcode a subject-specific string ---
    if not title or re.match(r"^(?:executive presentation|presentation|deck|slides?)$", title.strip(), re.I):
        # Try to get the first meaningful heading from the document
        heading_match = re.search(
            r"(?:^|\n)([A-Z][A-Za-z0-9 ,&:\-']{5,70})(?:\n|\r|\.{2,}|$)",
            grounding[:2000],
            re.MULTILINE,
        )
        if heading_match:
            title = heading_match.group(1).strip().rstrip(".")
        else:
            # Strip the generation verb from the user prompt to get the topic
            clean_p = re.sub(
                r"^(?:generate|create|make|build|prepare)\s+(?:a|an)?\s*"
                r"(?:\d+[- ]*(?:slides?|pages?)\s+)?(?:presentation|deck|ppt|pptx)?"
                r"\s*(?:on|about|for|from|of)?\s*",
                "",
                prompt.split("\n")[0],
                flags=re.I,
            ).strip()
            title = (clean_p[:60].strip() if clean_p else None) or "Presentation"

    # --- Check for explicit slide outline provided by user in prompt ---
    from app.agents.requirements_agent import RequirementsAgent
    explicit_slides = RequirementsAgent.extract_explicit_slides(prompt)
    if explicit_slides:
        return {
            "deckTitle": title,
            "slides": explicit_slides[:count] if count else explicit_slides,
            "generationMode": "user_explicit_outline",
        }

    # --- Extract topics dynamically from document grounding ---
    dynamic_topics = _extract_topics_from_grounding(grounding, count) if grounding.strip() else []

    slides: list[dict[str, Any]] = []
    for index in range(count):
        if index < len(dynamic_topics):
            s_title, s_layout, s_chapter = dynamic_topics[index]
        else:
            # Grounding exhausted: produce numbered stubs the slide_writer can fill
            s_title = f"{title}: Part {index + 1}"
            s_layout = "hero" if index == 0 else "closing" if index == count - 1 else "two_column"
            s_chapter = f"Section {index + 1}"

        slides.append({
            "slideId": f"s{index + 1:02d}",
            "chapter": s_chapter,
            "purpose": s_title,
            "headline": s_title,
            "message": s_title,
            "layoutHint": s_layout,
            "bullets": [],
            "speakerNotes": f"Source-grounded content for: {s_title}",
        })

    return {"deckTitle": title, "slides": slides, "generationMode": "offline_outline"}




def prepare_deck(spec: dict[str, Any], evidence: str) -> dict[str, Any]:
    """Normalize presentation text and admit only evidenced stats/quotes.

    Exact excerpt checks are provenance checks, not semantic fact verification.
    General prose grounding still depends on the writer and source review.
    """
    def clean(value: Any) -> Any:
        if isinstance(value, str):
            return clean_text(value)
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        return value

    result = clean(spec)
    result["designSystem"] = DESIGN_SYSTEM_VERSION
    subject = default_brand(str(result.get("deckTitle", "")))["subject"]
    result["designArchitecture"] = {"subject": subject, "version": "2.0",
                                    "density": "content_adaptive"}
    source = " ".join(clean_text(evidence).split()).casefold()
    previous = ""
    for slide in result.get("slides", []):
        layout = slide.get("layoutHint", "two_column")
        layout = {"chart": "metrics_grid", "metrics": "metrics_grid", "title": "hero"}.get(layout, layout)
        if layout not in LAYOUTS and not (isinstance(layout, str) and layout.upper().startswith("A") and layout[1:].isdigit()):
            layout = "two_column"
        metrics = slide.get("metrics", [])
        valid_metrics = []
        for metric in metrics if isinstance(metrics, list) else []:
            if not isinstance(metric, dict):
                continue
            excerpt = " ".join(str(metric.get("sourceQuote", "")).split()).casefold()
            value = str(metric.get("value", ""))
            label = str(metric.get("label", ""))
            if excerpt and excerpt in source and value and label and value.casefold() in excerpt and label.casefold() in excerpt:
                valid_metrics.append(metric)
        slide["metrics"] = valid_metrics[:4]
        quote = slide.get("quote")
        if isinstance(quote, dict):
            excerpt = " ".join(str(quote.get("sourceQuote", "")).split()).casefold()
            text = " ".join(str(quote.get("text", "")).split()).casefold()
            attribution = str(quote.get("attribution", "")).casefold()
            if not (excerpt and excerpt in source and text and text in excerpt and attribution and attribution in excerpt):
                slide.pop("quote", None)
        else:
            slide.pop("quote", None)
        if (layout in {"metrics_grid", "bar_chart"} and not valid_metrics) or (layout == "quote" and not slide.get("quote")):
            layout = "card_grid"
        if layout == 'timeline':
            dated_items = sum(bool(re.search(r'\b\d{3,4}\s*(?:BCE|BC|CE|AD)?\b', str(item), re.IGNORECASE))
                              for item in slide.get('bullets', []))
            if dated_items < 2:
                layout = 'editorial'
        if layout == previous and layout in {"two_column", "card_grid", "concept"}:
            layout = "editorial"
        slide["layoutHint"] = layout
        previous = layout
    slides = result.get("slides", [])
    if len(slides) >= 2:
        if not (isinstance(slides[0].get("layoutHint"), str) and slides[0]["layoutHint"].upper() in ("A1", "A2", "A3")):
            slides[0]["layoutHint"] = "hero"
        if not (isinstance(slides[-1].get("layoutHint"), str) and slides[-1]["layoutHint"].upper() in ("A17", "A18", "A27")):
            slides[-1]["layoutHint"] = "closing"
    return result
