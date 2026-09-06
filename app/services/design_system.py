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
    "governance": ("#0C3B39", "#E08A1E", "#E9F3F1"),
    "sustainability": ("#20302C", "#C28A2C", "#F1F6F4"),
    "markets": ("#132A52", "#C68A2E", "#EEF2F8"),
    "health": ("#164B50", "#D27950", "#EDF5F4"),
    "technology": ("#292447", "#D99448", "#F0EEF6"),
}


def clean_text(value: Any) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "").replace("\u2014", " - ").replace("**", "")).strip()


def default_brand(topic: str) -> dict[str, Any]:
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
    primary, accent, neutral = PALETTES[domain]
    return {
        "titleFont": {"name": "Cambria"}, "bodyFont": {"name": "Calibri"},
        "colors": {"primary": primary, "accent": accent, "background": "#FFFFFF",
                   "neutral": neutral, "secondary": primary},
        "designSystem": DESIGN_SYSTEM_VERSION, "subject": domain,
    }


def normalize_brand(brand: Any, topic: str) -> dict[str, Any]:
    result = default_brand(topic)
    colors = brand.get("colors", {}) if isinstance(brand, dict) else {}
    for key in ("primary", "accent", "neutral"):
        value = colors.get(key) if isinstance(colors, dict) else None
        if isinstance(value, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
            result["colors"][key] = "#" + value.lstrip("#")
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


def fallback_plan(prompt: str, count: int | None = None) -> dict[str, Any]:
    """Honest offline outline: source excerpts and questions, no invented facts."""
    match = re.search(r"\b(\d+)\s*[- ]?slides?\b", prompt, re.IGNORECASE)
    count = count or (int(match.group(1)) if match else 4)
    if not 1 <= count <= 60:
        raise ValueError("Request between 1 and 60 slides")
    title = " ".join(clean_text(prompt.split('\n')[0]).split()[:8])
    questions = (
        "What does the source establish?", "Which concepts need explanation?",
        "What evidence supports the argument?", "How do the alternatives compare?",
        "What questions remain open?", "What should the audience remember?",
    )
    slides = []
    for index in range(count):
        layout = "hero" if index == 0 else "closing" if index == count - 1 else ("roadmap", "concept", "card_grid", "comparison", "takeaways")[(index - 1) % 5]
        message = title if index == 0 else questions[(index - 1) % len(questions)]
        slides.append({"slideId": f"s{index + 1:02d}", "purpose": message,
                       "message": message, "layoutHint": layout,
                       "bullets": [], "speakerNotes": "Offline outline: add source-backed content before presenting."})
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
        if layout not in LAYOUTS:
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
        slides[0]["layoutHint"] = "hero"
        slides[-1]["layoutHint"] = "closing"
    return result
