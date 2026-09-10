"""Generate and QA a 25-slide deck from ``source data.pdf``.

Every rendered revision is retained in ``C:/DeckPilotAI/test-output`` so visual
and QA regressions can be compared rather than overwritten.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from difflib import SequenceMatcher
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.agents.design_intelligence import DesignIntelligenceAgent
from app.agents.qa_agent import PresentationQAAgent
from app.agents.repair_agent import RepairAgent
from app.agents.storyline_agent import StorylineAgent
from app.schemas.generation_state import (
    AssetMetadata,
    PresentationGoal,
    PresentationType,
)
from app.services.extraction import DocumentExtractor
from app.services.renderer import PPTXRenderer
from app.tools.image_intelligence import ImageIntelligence

SOURCE_PDF = Path("C:/DeckPilotAI/source data.pdf")
OUTPUT_DIR = Path("C:/DeckPilotAI/test-output")
PREFIX = "source-data-25slides"


SLIDE_PLAN = [
    ("The Rise of Empires", "The transition from kingdoms to empires in ancient India", 1, "hero"),
    ("What Defines an Empire?", "A large territory brought smaller kingdoms and diverse communities under one authority", 6, "two_column"),
    ("Governing Diverse Territories", "Regional rulers often retained local authority in return for tribute and loyalty", 7, "comparison"),
    ("How Kingdoms Expanded", "Warfare, alliances, forts, rivers, and trade routes supported imperial expansion", 8, "text_image"),
    ("Trade Routes Connected the Subcontinent", "The Uttarapatha and Dakshinapatha linked cities, markets, and distant regions", 10, "text_image"),
    ("Guilds Organised Economic Life", "Traders and artisans shared resources, information, and responsibility through guilds", 11, "two_column"),
    ("Magadha Gained an Early Advantage", "Strong rulers and access to fertile land helped Magadha become a leading mahajanapada", 12, "card_grid"),
    ("Geography Strengthened Magadha", "The Ganga and Son rivers supported farming, transport, trade, and defensive planning", 13, "two_column"),
    ("Greek Campaigns Reached the Northwest", "Alexander entered the northwestern subcontinent after defeating the Persian Empire", 14, "text_image"),
    ("Porus Resisted at the Hydaspes", "The battle demonstrated the military strength of regional Indian kingdoms", 14, "comparison"),
    ("Alexander Met Indian Philosophers", "Greek accounts described exchanges with Indian sages known as Gymnosophists", 16, "comparison"),
    ("The Mauryas Replaced the Nandas", "Chandragupta Maurya established a new dynasty with guidance attributed to Kautilya", 16, "timeline"),
    ("Kautilya and the Fall of the Nandas", "Traditional accounts connect Kautilya's political strategy with Chandragupta's rise", 17, "text_image"),
    ("Chandragupta Built a Large Empire", "The Maurya realm expanded from Magadha across much of the subcontinent", 18, "text_image"),
    ("Megasthenes Observed Mauryan Rule", "The Greek ambassador described Pataliputra and Chandragupta's court", 19, "text_image"),
    ("The Arthashastra Explained Statecraft", "Kautilya discussed administration, justice, agriculture, cities, and public welfare", 19, "two_column"),
    ("The Seven Parts of a Kingdom", "The Saptanga model linked the ruler, ministers, territory, forts, treasury, forces, and allies", 20, "card_grid"),
    ("Ashoka Confronted the Cost of Kalinga", "The suffering caused by war contributed to a major change in Ashoka's policies", 22, "text_image"),
    ("The King Who Chose Peace", "Ashoka favoured welfare, restraint, and dhamma after the Kalinga war", 22, "comparison"),
    ("Edicts Carried Ashoka's Messages", "Rock and pillar inscriptions communicated policies across a geographically large empire", 23, "text_image"),
    ("Prakrit and Brahmi Reached Broad Audiences", "Many edicts used a widely understood language and script", 24, "text_image"),
    ("Dhamma Connected Ethics and Welfare", "Ashoka's messages encouraged kindness, restraint, and responsible conduct", 25, "two_column"),
    ("Life in the Mauryan Period", "Accounts describe protected agriculture, stocked granaries, skilled artisans, and active towns", 26, "card_grid"),
    ("Mauryan Art Shaped India's Heritage", "Pillars, stupas, sculpture, terracotta, and symbols left a lasting visual legacy", 29, "text_image"),
    ("Why Empires Decline", "Succession problems, regional independence, resource pressure, and repression weakened imperial unity", 31, "closing"),
]


# Deterministic, source-grounded evidence used by this regression fixture.
CURATED_BULLETS = {
    "What Defines an Empire?": ["An emperor exercised central authority over tributary territories and their rulers.", "Officials collected taxes, maintained law and order, and managed distant regions.", "Armies, roads, river routes, currency, and trade rules helped hold the realm together."],
    "Governing Diverse Territories": ["Empires included peoples with different languages, customs, and cultures.", "Regional kings or chiefs usually continued to govern after offering tribute and loyalty.", "This arrangement extended imperial control without replacing every local institution."],
    "How Kingdoms Expanded": ["Kingdoms fought neighbouring territories and built forts at strategic locations.", "Control of rivers and trade networks brought resources and tax revenue.", "Superior military power and surplus resources could turn one ruler into an overlord."],
    "Trade Routes Connected the Subcontinent": ["The Uttarapatha crossed northern India and linked major political and commercial centres.", "The Dakshinapatha connected central and southern regions with ports and inland markets.", "Merchants used these networks to move goods, information, and cultural ideas."],
    "Guilds Organised Economic Life": ["Guild members shared knowledge about markets, supply, demand, and labour.", "Cultivators, traders, herdsmen, moneylenders, and artisans set rules for their occupations.", "Guild autonomy allowed commerce to flourish with limited royal interference."],
    "Magadha Gained an Early Advantage": ["Fertile Ganga plains produced agricultural surpluses that supported cities and armies.", "Forests supplied timber and elephants, while nearby hills contained iron and minerals.", "Iron ploughs raised farm output and sharper weapons strengthened military capability."],
    "Geography Strengthened Magadha": ["The Ganga and Son rivers supported transport and long-distance trade.", "Surplus grain allowed more people to specialise in arts and crafts.", "Growing commerce increased state income and helped Magadha expand."],
    "Greek Campaigns Reached the Northwest": ["Alexander conquered the Persian Empire before advancing toward the Indian subcontinent.", "The northwest contained smaller kingdoms along routes linked to the Mediterranean world.", "Greek accounts identify the Pauravas and their ruler Porus among these kingdoms."],
    "Porus Resisted at the Hydaspes": ["Porus confronted Alexander near the Hydaspes River in the northwestern subcontinent.", "The campaign met organised regional resistance rather than an undefended frontier.", "Alexander soon turned back, while Greek political influence remained in the northwest."],
    "Alexander Met Indian Philosophers": ["Greek writers called a group of Indian sages Gymnosophists, or naked philosophers.", "The sages answered Alexander's riddles calmly despite his threats.", "Historians interpret the encounter as a meeting of Greek and Indian philosophical traditions."],
    "The Mauryas Replaced the Nandas": ["Around 321 BCE, Chandragupta Maurya founded a new empire in Magadha.", "The Mauryan rise followed the decline and unpopularity of the Nanda dynasty.", "Kautilya is traditionally credited with guiding Chandragupta's political strategy."],
    "Kautilya and the Fall of the Nandas": ["Buddhist accounts describe Kautilya as a teacher associated with Takshashila.", "He warned Dhana Nanda that oppressive rule would bring down the empire.", "After being expelled from court, Kautilya vowed to end Nanda rule."],
    "Chandragupta Built a Large Empire": ["Chandragupta overthrew the Nandas and made Pataliputra his capital.", "Magadha's geography, economy, and trade base supported further expansion.", "He defeated Greek satraps and extended Mauryan control toward the Deccan plateau."],
    "Megasthenes Observed Mauryan Rule": ["Chandragupta maintained diplomatic relations with Greek rulers after defeating their satraps.", "Megasthenes served as a Greek diplomat at the Mauryan court.", "His Indika described India and survives through quotations preserved by later authors."],
    "The Arthashastra Explained Statecraft": ["The Arthashastra presented governance and economics as practical fields of study.", "It addressed defence, administration, revenue, justice, agriculture, and cities.", "Kautilya linked a ruler's power with organised institutions and public welfare."],
    "The Seven Parts of a Kingdom": ["Swami represented the ruler, while amatya represented ministers and senior officials.", "Janapada, durga, and kosha covered territory, fortified centres, and the treasury.", "Danda and mitra represented coercive forces and dependable allies."],
    "Ashoka Confronted the Cost of Kalinga": ["Ashoka inherited a vast empire and initially pursued further expansion.", "His campaign in Kalinga caused extensive death and destruction.", "The suffering led him to renounce aggressive warfare and favour non-violence."],
    "The King Who Chose Peace": ["Ashoka embraced Buddhist teaching after reflecting on the Kalinga war.", "He sent emissaries to Sri Lanka, Central Asia, and other regions.", "His later rule emphasised welfare, restraint, and communication through edicts."],
    "Edicts Carried Ashoka's Messages": ["Ashoka issued inscriptions on rocks and pillars across many parts of his empire.", "The edicts encouraged people and officials to follow dharma.", "Their wide distribution allowed royal policy to reach distant communities."],
    "Prakrit and Brahmi Reached Broad Audiences": ["Most Ashokan edicts used Prakrit, a popular language in many parts of India.", "The messages were commonly written in Brahmi, an ancestor of regional Indian scripts.", "Accessible language and script strengthened Ashoka's role as a public communicator."],
    "Dhamma Connected Ethics and Welfare": ["Dhamma included moral duty, truthfulness, righteous conduct, and social responsibility.", "Ashoka asked officials to practise fairness, patience, and impartiality.", "He also promoted medical care, wells, rest houses, trees, and respect among sects."],
    "Life in the Mauryan Period": ["Pataliputra contained palaces, public buildings, planned streets, and busy markets.", "Officials, merchants, and artisans played central roles in urban life.", "Agriculture, taxation, trade, and emergency grain stores supported the wider economy."],
    "Mauryan Art Shaped India's Heritage": ["Ashoka is associated with pillars, stupas, chaityas, and viharas across the realm.", "The Great Stupa at Sanchi became a landmark of early Indian architecture.", "The Dhauli elephant sculpture joined Buddhist symbolism with an inscribed landscape."],
    "Why Empires Decline": ["Heavy tribute and long military campaigns could create resentment in distant regions.", "Weak succession encouraged local rulers to stop paying tribute and seek independence.", "Distance, droughts, floods, and economic crises made a large empire harder to hold together."],
}

CAPTION_FIXES = {
    "Fig. 5.1": "Fig. 5.1. Rock-cut cave in the Barabar Hills, Bihar.",
    "Fig. 5.3": "Fig. 5.3. A trained army with cavalry and war elephants.",
    "Fig. 5.4.3": "Fig. 5.4.3. A kingdom wages war to conquer neighbouring territory.",
    "Fig. 5.5": "Fig. 5.5. Major ancient trade routes and cities of the subcontinent.",
    "Fig. 5.9": "Fig. 5.9. Map of Alexander's empire and campaign route.",
    "Fig. 5.12": "Fig. 5.12. Map of the Nanda Empire.",
    "Fig. 5.13": "Fig. 5.13. Map of the Maurya Empire.",
    "Fig. 5.14": "Fig. 5.14. Megasthenes at the court of Chandragupta Maurya.",
    "Fig. 5.16": "Fig. 5.16. Ashoka visiting the Ramagrama stupa in Nepal.",
    "Fig. 5.18": "Fig. 5.18. Ashokan inscriptions at Girnar and Feroz Shah Kotla.",
    "Fig. 5.26": "Fig. 5.26. The Great Stupa at Sanchi.",
}


def _clean_page_text(text: str) -> str:
    text = re.sub(r"(?:Exploring Society: India and Beyond\s*\|\s*Grade 7 Part 1|Tapestry of the Past 5\s*[–—-]\s*The Rise of Empires)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bReprint 2026-27\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:LET[’']?S EXPLORE|DON[’']?T MISS OUT|THINK ABOUT IT)\b", " ", text, flags=re.IGNORECASE)
    text = text.replace("Æ", " ").replace("•", " ").replace("", " ")
    text = re.sub(r"(?m)^\s*\d{2,3}\s*$", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _source_bullets(page_text: str, title: str, takeaway: str) -> list[str]:
    if title in CURATED_BULLETS:
        return list(CURATED_BULLETS[title])
    sentences = re.split(r"(?<=[.!?])\s+", _clean_page_text(page_text))
    selected: list[str] = []
    title_terms = {word.lower() for word in re.findall(r"[A-Za-z]{4,}", f"{title} {takeaway}")}
    ranked: list[tuple[int, int, str]] = []
    for order, sentence in enumerate(sentences):
        sentence = sentence.strip(" Æ•\t")
        words = sentence.split()
        if not 7 <= len(words) <= 24 or sentence.endswith("?"):
            continue
        if re.search(r"\b(discuss|share|write|identify|revisit|observe|look at|notice|read the|can you|do you|what do you|let us see)\b", sentence, re.IGNORECASE):
            continue
        overlap = sum(word.lower().strip(".,;:()[]'\"") in title_terms for word in words)
        ranked.append((overlap, -order, sentence))
    ranked.sort(reverse=True)
    for _score, _order, sentence in ranked:
        concise = sentence.rstrip(" ,;:-")
        if not any(SequenceMatcher(None, concise.lower(), existing.lower()).ratio() > 0.82 for existing in selected):
            selected.append(concise)
        if len(selected) == 3:
            break
    return selected


def _build_assets(extraction, page_text: dict[int, str]):
    assets: list[AssetMetadata] = []
    image_bytes: dict[str, bytes] = {}
    for meta, payload in zip(extraction.extracted_images, extraction.image_payloads, strict=True):
        data = payload[1]
        sha256 = meta.get("sha256") or hashlib.sha256(data).hexdigest()
        asset_id = f"pdf_{sha256[:12]}"
        quality_ok, quality_score, _reason = ImageIntelligence.validate_image_quality(data)
        if not quality_ok:
            continue
        page = int(meta.get("page", 1))
        raw_caption = str(meta.get("caption", "")).strip()
        if raw_caption.startswith("Fig. 5.15"):
            # The extracted object is an empty parchment decoration, not an
            # informative figure, so it must never be matched to a slide.
            continue
        caption = next(
            (replacement for prefix, replacement in sorted(CAPTION_FIXES.items(), key=lambda item: len(item[0]), reverse=True) if raw_caption.startswith(prefix)),
            raw_caption,
        )
        asset = AssetMetadata(
            asset_id=asset_id,
            source_file=SOURCE_PDF.name,
            page_or_slide=page,
            width=int(meta.get("width", 0)),
            height=int(meta.get("height", 0)),
            aspect_ratio=float(meta.get("width", 1)) / max(1, float(meta.get("height", 1))),
            format=str(meta.get("format", "jpg")),
            sha256=sha256,
            perceptual_hash=ImageIntelligence.compute_dhash(data),
            caption=caption,
            nearby_text=page_text.get(page, "")[:900],
            semantic_summary=page_text.get(page, "")[:900],
            quality_score=quality_score,
            is_valid_figure=True,
            storage_key=str(meta.get("storage_key", "")),
        )
        assets.append(asset)
        image_bytes[asset_id] = data
    return assets, image_bytes


def _closest_unused_asset(page: int, title: str, assets: list[AssetMetadata], used: set[str]) -> AssetMetadata | None:
    candidates = [asset for asset in assets if asset.asset_id not in used and abs(asset.page_or_slide - page) <= 1]
    if not candidates:
        return None
    title_terms = {word.lower() for word in re.findall(r"[A-Za-z]{4,}", title)}
    candidates.sort(
        key=lambda asset: (
            -abs(asset.page_or_slide - page),
            sum(term in f"{asset.caption} {asset.semantic_summary}".lower() for term in title_terms),
            asset.width * asset.height,
        ),
        reverse=True,
    )
    return candidates[0]


def build_deck_spec(page_text: dict[int, str], assets: list[AssetMetadata]) -> dict:
    slides = []
    used: set[str] = set()
    for index, (title, takeaway, page, layout) in enumerate(SLIDE_PLAN, 1):
        image = _closest_unused_asset(page, title, assets, used) if layout in {"hero", "text_image"} else None
        if image:
            used.add(image.asset_id)
        bullets = [] if index == 1 else _source_bullets(page_text.get(page, ""), title, takeaway)
        slide = {
            "slideId": f"s{index:02d}",
            "purpose": takeaway,
            "headline": title,
            "takeaway": takeaway,
            "chapter": "THE RISE OF EMPIRES",
            "layoutHint": layout,
            "archetype_fields": {"qa_balanced_cards": True},
            "bullets": bullets,
            "speakerNotes": f"Source: {SOURCE_PDF.name}, PDF page {page} (printed page {page + 82}).",
        }
        if image:
            slide["imageArtifactId"] = image.asset_id
            slide["imageCaption"] = image.caption
        slides.append(slide)
    return {"deckTitle": "The Rise of Empires", "slides": slides}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prior_runs = [
        int(match.group(1))
        for path in OUTPUT_DIR.glob(f"{PREFIX}-run*-r0.pptx")
        if (match := re.search(r"-run(\d+)-r0$", path.stem))
    ]
    run_prefix = f"{PREFIX}-run{max(prior_runs, default=0) + 1}"
    extraction = DocumentExtractor.extract_pdf(SOURCE_PDF.read_bytes(), SOURCE_PDF.name)
    page_text = {int(block["page"]): str(block["content"]) for block in extraction.text_blocks if block.get("page")}
    assets, source_images = _build_assets(extraction, page_text)
    goal = PresentationGoal(
        topic="The Rise of Empires",
        objective="Explain the rise, governance, achievements, and decline of early Indian empires",
        audience="Grade 7 students and teachers",
        industry="History education",
        presentation_type=PresentationType.RESEARCH_EDUCATION,
        target_slide_count=25,
        visual_tone="scholarly editorial",
        has_reference_docs=True,
    )
    design_system = DesignIntelligenceAgent.generate_design_system(goal)
    deck_spec = build_deck_spec(page_text, assets)
    slides = StorylineAgent.create_storyline_plan(goal, deck_spec, assets, "\n\n".join(page_text.values()))
    for slide in slides:
        # This source-driven regression deck intentionally uses the balanced
        # three-card composition for concise text-only slides.
        slide.archetype_fields["qa_balanced_cards"] = True

    final_report = None
    for revision in range(4):
        pptx_bytes = PPTXRenderer.render_presentation(slides, design_system, source_images, deck_title=deck_spec["deckTitle"])
        pptx_path = OUTPUT_DIR / f"{run_prefix}-r{revision}.pptx"
        pptx_path.write_bytes(pptx_bytes)
        report = PresentationQAAgent.evaluate_presentation(slides, design_system, pptx_bytes, source_images, assets)
        report.repair_iterations = revision
        (OUTPUT_DIR / f"{run_prefix}-r{revision}-qa.json").write_text(json.dumps(report.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
        (OUTPUT_DIR / f"{run_prefix}-r{revision}-slides.json").write_text(json.dumps([slide.model_dump(mode="json") for slide in slides], indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"revision={revision} status={report.status} score={report.overall_quality_score} issues={len(report.issues)} pptx={pptx_path}")
        for issue in report.issues:
            print(f"  {issue.checkpoint_id} {issue.severity.value} slide={issue.slide_number}: {issue.message}")
        final_report = report
        if not report.repair_triggered:
            break
        slides = RepairAgent.apply_corrections(slides, report, goal.topic, source_images, assets, design_system)

    assert len(slides) == 25
    assert final_report is not None
    final_alias = OUTPUT_DIR / f"{PREFIX}-final.pptx"
    try:
        shutil.copyfile(pptx_path, final_alias)
    except PermissionError:
        # PowerPoint preview can hold the stable alias open on Windows. Never
        # fail or overwrite a revision; publish a run-specific final alias.
        shutil.copyfile(pptx_path, OUTPUT_DIR / f"{run_prefix}-final.pptx")
    return 0 if final_report.status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
