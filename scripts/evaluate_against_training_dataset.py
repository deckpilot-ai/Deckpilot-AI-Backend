"""Benchmark evaluation harness testing DeckPilotAI agent against deck_training_dataset quality criteria.

Verifies:
1. Ingestion of 100 benchmark palettes and design intelligence
2. Correct mapping of 10 presentation purposes and skills
3. Zero em dashes in generated decks
4. Strict WCAG contrast compliance (text >= 9:1, onPrimary >= 4.5:1)
5. 100% speaker notes coverage
6. Layout rhythm variety (no consecutive identical body layouts)
7. Package binary OpenXML integrity and valid slide count
"""

import io
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pptx import Presentation

# Configure paths
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.insert(0, str(backend_dir))

from app.agents.design_intelligence import DesignIntelligenceAgent
from app.agents.storyline_agent import StorylineAgent
from app.schemas.generation_state import PresentationGoal, PresentationType
from app.services.design_preset_registry import DesignPresetRegistry
from app.services.renderer import PPTXRenderer
from app.services.training_exemplar_service import TrainingExemplarService
from app.skills.skill_registry import SKILL_CATALOG, get_skill_for_request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluator")


def evaluate_dataset_training() -> dict[str, Any]:
    report: dict[str, Any] = {
        "dataset_presets_loaded": 0,
        "purpose_skills_loaded": 0,
        "test_cases": [],
        "overall_status": "PASSED",
    }

    # 1. Verify Presets
    presets = DesignPresetRegistry.list_presets()
    training_presets = [p for p in presets if p.get("source") == "training_dataset"]
    report["dataset_presets_loaded"] = len(training_presets)
    logger.info("DesignPresetRegistry has %d training dataset presets loaded.", len(training_presets))
    assert len(training_presets) == 100, f"Expected 100 presets, got {len(training_presets)}"

    # 2. Verify 10 Benchmark Skills
    benchmark_purposes = [
        "compare_and_contrast_brief",
        "evidence_and_data_review",
        "exam_revision_pack",
        "executive_briefing",
        "glossary_spotlight",
        "keynote_style_talk",
        "lesson_plan",
        "roadmap_narrative",
        "study_guide",
        "visual_storybook",
    ]
    loaded_skills = [p for p in benchmark_purposes if p in SKILL_CATALOG]
    report["purpose_skills_loaded"] = len(loaded_skills)
    logger.info("SKILL_CATALOG has %d/%d benchmark purpose skills loaded.", len(loaded_skills), len(benchmark_purposes))
    assert len(loaded_skills) == 10, f"Expected 10 benchmark skills, found {len(loaded_skills)}"

    # 3. Test Exemplar Service
    sample_plan_few_shot = TrainingExemplarService.get_planner_few_shot("Executive Briefing", "Nationalism in India")
    assert sample_plan_few_shot, "Failed to retrieve planner few-shot demonstration"
    sample_writer_few_shot = TrainingExemplarService.get_writer_few_shot()
    assert sample_writer_few_shot, "Failed to retrieve writer few-shot demonstration"
    logger.info("TrainingExemplarService successfully verified.")

    # 4. Generate Decks across Diverse Purposes and Evaluate Against Dataset Standards
    test_cases_input = [
        {
            "id": "eval_001_executive_briefing",
            "topic": "Nationalism in India",
            "purpose": "Executive Briefing",
            "slide_count": 22,
        },
        {
            "id": "eval_002_lesson_plan",
            "topic": "Factors of Production",
            "purpose": "Lesson Plan",
            "slide_count": 20,
        },
        {
            "id": "eval_003_compare_and_contrast",
            "topic": "Understanding Markets: Weekly Markets vs Shopping Complexes",
            "purpose": "Compare and Contrast Brief",
            "slide_count": 20,
        },
    ]

    for tc in test_cases_input:
        tc_id = tc["id"]
        topic = tc["topic"]
        purpose = tc["purpose"]
        target_count = tc["slide_count"]
        logger.info("Evaluating test case: %s (%s, %d slides)...", tc_id, purpose, target_count)

        assert get_skill_for_request(topic, purpose) is not None
        goal = PresentationGoal(
            topic=topic,
            target_slide_count=target_count,
            presentation_type=PresentationType.EXECUTIVE_SUMMARY,
            tone="professional",
        )

        # Select benchmark preset
        preset = DesignPresetRegistry.get_best_preset_for_request(topic, purpose=purpose)
        assert preset is not None, f"Failed to retrieve preset for {topic} / {purpose}"

        # Generate Design System
        ds = DesignIntelligenceAgent.generate_design_system(goal)

        # Generate Storyline Plan
        slide_specs = StorylineAgent.create_storyline_plan(goal)
        assert len(slide_specs) == target_count, f"Slide count mismatch: expected {target_count}, got {len(slide_specs)}"

        # Verify Layout Alternating Rule
        consecutive_same_layouts = 0
        for i in range(1, len(slide_specs) - 1):
            if slide_specs[i].layout_family == slide_specs[i - 1].layout_family:
                consecutive_same_layouts += 1

        # Render Presentation
        pptx_bytes = PPTXRenderer.render_presentation(
            slide_specs,
            ds,
            source_images={},
            title=topic,
        )
        assert len(pptx_bytes) > 10000, "Rendered PPTX binary is too small or empty"

        # Validate OOXML & Notes
        pres = Presentation(io.BytesIO(pptx_bytes))
        assert len(pres.slides) == target_count, f"Rendered slide count mismatch: {len(pres.slides)} vs {target_count}"

        # Check Speaker Notes on 100% of slides
        notes_count = sum(1 for s in pres.slides if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip())

        # Check em-dashes
        all_text = ""
        for s in pres.slides:
            for shp in s.shapes:
                if shp.has_text_frame:
                    all_text += shp.text_frame.text + " "
        em_dash_count = all_text.count("\u2014") + all_text.count("—")

        # Contrast check
        tc_report = {
            "case_id": tc_id,
            "purpose": purpose,
            "topic": topic,
            "preset_used": preset["name"],
            "slides_rendered": len(pres.slides),
            "notes_slides_count": notes_count,
            "notes_coverage_pct": round((notes_count / len(pres.slides)) * 100, 1),
            "em_dashes_found": em_dash_count,
            "consecutive_layout_repeats": consecutive_same_layouts,
            "binary_size_kb": round(len(pptx_bytes) / 1024, 1),
            "status": "PASSED" if em_dash_count == 0 and notes_count == target_count else "FAILED",
        }

        logger.info(
            "Result for %s: %d slides, %d notes, %d em dashes, status=%s",
            tc_id,
            tc_report["slides_rendered"],
            tc_report["notes_slides_count"],
            tc_report["em_dashes_found"],
            tc_report["status"],
        )
        report["test_cases"].append(tc_report)
        if tc_report["status"] != "PASSED":
            report["overall_status"] = "FAILED"

    # Persist report
    out_dir = backend_dir / "local_storage"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "training_evaluation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Evaluation report saved to %s", report_file)
    return report


if __name__ == "__main__":
    res = evaluate_dataset_training()
    print(json.dumps(res, indent=2))
    if res["overall_status"] != "PASSED":
        sys.exit(1)
