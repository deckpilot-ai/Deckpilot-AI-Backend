"""In-Context Training Exemplar Service for DeckPilotAI Multi-Agent Engine.

Loads and serves few-shot training demonstrations from deck_training_dataset,
teaching the Deck Planner and Slide Writer agents to generate authentic,
publication-grade presentations with zero hallucinated fluff and strict visual structure.
"""

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class TrainingExemplarService:
    """Indexes benchmark training pairs and provides targeted few-shot exemplars to LLM agents."""

    _exemplars_by_purpose: ClassVar[dict[str, list[dict[str, Any]]]] = {}
    _exemplars_by_id: ClassVar[dict[str, dict[str, Any]]] = {}
    _initialized: ClassVar[bool] = False

    @classmethod
    def _find_dataset_file(cls) -> Path | None:
        """Locates training_pairs.jsonl in either sibling dataset dir or backend resources."""
        current_file = Path(__file__).resolve()
        candidates = [
            current_file.parent.parent.parent.parent / "deck_training_dataset" / "dataset" / "training_pairs.jsonl",
            current_file.parent.parent / "resources" / "training_pairs_index.json",
            Path("C:/DeckPilotAI/deck_training_dataset/dataset/training_pairs.jsonl"),
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    @classmethod
    def _ensure_init(cls) -> None:
        if cls._initialized:
            return

        dataset_path = cls._find_dataset_file()
        if not dataset_path:
            logger.info("Training pairs dataset not found; using embedded representative exemplars.")
            cls._load_embedded_defaults()
            cls._initialized = True
            return

        try:
            if dataset_path.suffix == ".jsonl":
                with open(dataset_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        record = json.loads(line)
                        rec_id = record.get("id")
                        inp = record.get("input", {})
                        purp = inp.get("purpose", "").lower().strip()
                        if rec_id:
                            cls._exemplars_by_id[rec_id] = record
                        if purp:
                            cls._exemplars_by_purpose.setdefault(purp, []).append(record)
            elif dataset_path.suffix == ".json":
                with open(dataset_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for record in data:
                        rec_id = record.get("id")
                        inp = record.get("input", {})
                        purp = inp.get("purpose", "").lower().strip()
                        if rec_id:
                            cls._exemplars_by_id[rec_id] = record
                        if purp:
                            cls._exemplars_by_purpose.setdefault(purp, []).append(record)

            logger.info(
                "Indexed %d training pairs across %d presentation purposes.",
                len(cls._exemplars_by_id),
                len(cls._exemplars_by_purpose),
            )
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Error reading training pairs from %s: %s", dataset_path, e)
            cls._load_embedded_defaults()

        cls._initialized = True

    @classmethod
    def _load_embedded_defaults(cls) -> None:
        """Embedded high-fidelity exemplar from benchmark dataset (Nationalism in India / Executive Briefing)."""
        cls._exemplars_by_purpose["executive briefing"] = [
            {
                "id": "deck001",
                "input": {
                    "source_title": "Nationalism in India",
                    "subject": "History",
                    "purpose": "Executive Briefing",
                },
                "output": {
                    "design": {
                        "name": "Vermilion Haze",
                        "palette": {"mode": "tint", "scheme": "analogous"},
                        "typography": {"heading": "Cambria", "body": "Calibri"},
                    },
                    "slide_plan": [
                        {"n": 1, "layout": "cover", "title": "Nationalism in India", "section": None},
                        {"n": 2, "layout": "agenda", "title": "Executive agenda", "section": "Overview"},
                        {"n": 3, "layout": "roadmap", "title": "Chapter at a glance", "section": "Overview"},
                        {"n": 4, "layout": "questions", "title": "Questions this briefing answers", "section": "Overview"},
                        {"n": 5, "layout": "bullets_cards", "title": "Overview", "section": "Overview"},
                        {"n": 6, "layout": "bullets_image", "title": "Movements and Strands", "section": "Movement"},
                        {"n": 7, "layout": "two_column", "title": "Diverse Perspectives", "section": "Movement"},
                        {"n": 8, "layout": "stat_row", "title": "Critical Benchmarks", "section": "Evidence"},
                        {"n": 9, "layout": "summary", "title": "Executive summary", "section": "Summary"},
                        {"n": 10, "layout": "closing", "title": "Nationalism in India", "section": None},
                    ],
                },
            }
        ]

    @classmethod
    def get_best_exemplar(cls, purpose: str = "", topic: str = "") -> dict[str, Any] | None:
        cls._ensure_init()
        p_clean = purpose.lower().replace("-", " ").replace("_", " ").strip()

        # 1. Match by purpose
        if p_clean in cls._exemplars_by_purpose:
            candidates = cls._exemplars_by_purpose[p_clean]
            if topic:
                t_lower = topic.lower()
                for c in candidates:
                    subj = str(c.get("input", {}).get("subject", "")).lower()
                    title = str(c.get("input", {}).get("source_title", "")).lower()
                    if (subj and subj in t_lower) or (title and title in t_lower):
                        return c
            return candidates[0]

        # 2. Fuzzy purpose match
        for purp, candidates in cls._exemplars_by_purpose.items():
            if purp in p_clean or p_clean in purp:
                return candidates[0]

        # 3. Fallback to first available
        if cls._exemplars_by_id:
            return next(iter(cls._exemplars_by_id.values()))
        return None

    @classmethod
    def get_planner_few_shot(cls, purpose: str = "", topic: str = "") -> str:
        """Returns a formatted few-shot training block for the Deck Planner agent."""
        exemplar = cls.get_best_exemplar(purpose=purpose, topic=topic)
        if not exemplar:
            return ""

        inp = exemplar.get("input", {})
        out = exemplar.get("output", {})
        slide_plan = out.get("slide_plan", [])
        if not slide_plan:
            return ""

        # Take first 6-8 representative slides as demonstration
        sample_slides = []
        for s in slide_plan[:8]:
            sample_slides.append({
                "slideId": f"s{s.get('n', 1):02d}",
                "chapter": s.get("section") or "Core Thesis",
                "purpose": f"Establish {s.get('title', 'topic')} with source-grounded evidence.",
                "headline": s.get("title", "Insight Headline")[:25],
                "layoutHint": s.get("layout", "two_column"),
            })

        exemplar_json = json.dumps({
            "deckTitle": inp.get("source_title", "Benchmark Presentation"),
            "objective": f"Comprehensive {inp.get('purpose', 'Executive Briefing')} on {inp.get('source_title', 'Core Subject')}",
            "slides": sample_slides,
        }, indent=2)

        return (
            "\n[BENCHMARK DATASET TRAINING DEMONSTRATION — EMULATE THIS STRUCTURAL EXCELLENCE]:\n"
            f"Input Request: Purpose='{inp.get('purpose', 'Executive Briefing')}', Topic='{inp.get('source_title', 'Subject')}'\n"
            f"Optimal Output Deck Plan:\n{exemplar_json}\n"
        )

    @classmethod
    def get_writer_few_shot(cls) -> str:
        """Returns a high-quality demonstration showing dense evidence points, punchy headline, and speaker notes."""
        sample = {
            "slideId": "s03",
            "headline": "Economic Pressures",
            "eyebrow": "History | Nationalism in India",
            "bullets": [
                "Customs Duties Doubled: War financing led to a huge increase in defense expenditure between 1913 and 1918.",
                "Extreme Price Spikes: Prices doubled across essential commodities, creating severe hardship for common people.",
                "Forced Rural Conscription: Villages were called upon to supply soldiers, causing widespread rural outrage.",
                "Widespread Crop Failure: Acute food shortages in 1918–19 and 1920–21 accompanied by a catastrophic influenza epidemic.",
            ],
            "takeaway": "Post-war distress created fertile social conditions for a unified national non-cooperation struggle.",
            "speakerNotes": "Slide 3 Presenter Guide: Highlight the twin pressures of wartime inflation and forced recruitment. Cites NCERT Chapter 3, page 4.",
        }
        return (
            "\n[BENCHMARK WRITING TRAINING DEMONSTRATION — EMULATE THIS DENSE FACTUAL REPUTATION]:\n"
            f"{json.dumps(sample, indent=2)}\n"
        )
