import io

from pptx import Presentation
from pptx.util import Inches, Pt

from app.agents.qa_agent import PresentationQAAgent
from app.agents.qa_checkpoints import CHECKPOINTS, checkpoint_ids
from app.agents.repair_agent import RepairAgent
from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    LayoutFamily,
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)
from app.services.image_matcher import ImageMatcher
from app.services.renderer import PPTXRenderer


def test_checkpoint_catalog_has_120_stable_unique_checks():
    ids = checkpoint_ids()
    assert len(CHECKPOINTS) == 120
    assert len(ids) == len(set(ids))
    assert ids[0] == "QA-001"
    assert ids[-1] == "QA-120"
    assert all(item.repair_action for item in CHECKPOINTS)


def test_qa_detects_and_repairs_duplicate_copy_and_images():
    slides = [
        SlideSpec(slide_id="s01", slide_number=1, headline="Solar Energy", layout_family=LayoutFamily.HERO),
        SlideSpec(
            slide_id="s02",
            slide_number=2,
            headline="Solar Panel Economics",
            bullets=["Lower costs improve adoption", "Lower costs improve adoption"],
            image_artifact_id="solar-1",
            image_caption="Solar panels on a commercial rooftop",
            layout_family=LayoutFamily.TEXT_IMAGE,
        ),
        SlideSpec(
            slide_id="s03",
            slide_number=3,
            headline="Wind Farm Operations",
            bullets=["Turbine maintenance improves availability"],
            image_artifact_id="solar-1",
            image_caption="Solar panels on a commercial rooftop",
            layout_family=LayoutFamily.TEXT_IMAGE,
        ),
    ]
    assets = [
        AssetMetadata(asset_id="solar-1", caption="Solar panels on a commercial rooftop"),
        AssetMetadata(asset_id="wind-1", caption="Wind turbines at an operating wind farm"),
    ]

    report = PresentationQAAgent.evaluate_presentation(slides, DesignSystem(), available_assets=assets)
    failed = {issue.checkpoint_id for issue in report.issues}
    assert "QA-009" in failed
    assert "QA-061" in failed
    assert "QA-062" in failed
    assert report.checkpoints_total == 120
    assert report.repair_triggered is True

    repaired = RepairAgent.apply_corrections(slides, report, available_assets=assets)
    assert repaired[1].bullets == ["Lower costs improve adoption"]
    assert repaired[2].image_artifact_id == "wind-1"
    assert len({s.image_artifact_id for s in repaired if s.image_artifact_id}) == 2


def test_rendered_small_font_and_blank_space_are_detected_and_scaled():
    spec = SlideSpec(
        slide_id="s01",
        slide_number=1,
        headline="Readable typography",
        bullets=["A short but meaningful supporting point"],
        layout_family=LayoutFamily.TWO_COLUMN,
    )
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.6), Inches(1.0), Inches(2.0), Inches(0.4))
    box.text_frame.paragraphs[0].add_run().text = "Tiny body copy"
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(8)
    page = slide.shapes.add_textbox(Inches(12.1), Inches(6.9), Inches(0.5), Inches(0.3))
    page.text = "1"
    stream = io.BytesIO()
    prs.save(stream)

    report = PresentationQAAgent.evaluate_presentation([spec], DesignSystem(), pptx_bytes=stream.getvalue())
    failed = {issue.checkpoint_id for issue in report.issues}
    assert "QA-025" in failed
    assert "QA-049" in failed

    repaired = RepairAgent.apply_corrections([spec], report)
    assert repaired[0].archetype_fields["qa_font_scale"] >= 1.15
    assert repaired[0].archetype_fields["qa_expand_layout"] is True


def test_balanced_evidence_cards_use_readable_centered_typography():
    spec = SlideSpec(
        slide_id="s01",
        slide_number=1,
        headline="Guilds Organised Economic Life",
        takeaway="Traders and artisans shared resources and responsibility through guilds",
        bullets=[
            "Guild members shared knowledge about markets, supply, demand, and labour.",
            "Cultivators and artisans set practical rules for their occupations.",
            "Guild autonomy allowed commerce to flourish with limited royal interference.",
        ],
        layout_family=LayoutFamily.TWO_COLUMN,
        archetype_fields={"qa_balanced_cards": True},
    )
    payload = PPTXRenderer.render_presentation([spec], DesignSystem(), deck_title="The Rise of Empires")
    prs = Presentation(io.BytesIO(payload))
    slide = prs.slides[0]
    cards = {shape.name.rsplit("-", 1)[-1]: shape for shape in slide.shapes if shape.name.startswith("evidence-card-")}
    texts = [shape for shape in slide.shapes if shape.name.startswith("evidence-text-")]

    assert len(cards) == len(texts) == 3
    for shape in texts:
        sizes = [run.font.size.pt for paragraph in shape.text_frame.paragraphs for run in paragraph.runs]
        assert sizes and min(sizes) >= 17
        card = cards[shape.name.rsplit("-", 1)[-1]]
        assert shape.top > card.top + Inches(0.25)
        assert shape.top + shape.height < card.top + card.height - Inches(0.25)

    report = PresentationQAAgent.evaluate_presentation([spec], DesignSystem(), payload)
    assert "QA-057" not in {issue.checkpoint_id for issue in report.issues}


def test_repairs_use_stable_action_not_message_text():
    slide = SlideSpec(slide_id="s01", slide_number=1, headline="A title with far too many words for a clean readable presentation slide title")
    report = QAReport(
        issues=[ValidationIssue(
            checkpoint_id="QA-003",
            severity=ValidationSeverity.MEDIUM,
            category=ValidationCategory.CONTENT,
            slide_number=1,
            message="localized message that can change freely",
            repair_action="shorten_title",
        )]
    )
    repaired = RepairAgent.apply_corrections([slide], report)
    assert len(repaired[0].headline.split()) <= 10


def test_image_matcher_preserves_explicit_choices_and_skips_non_image_layouts():
    slides = [
        {"headline": "Solar generation", "layoutHint": "text_image", "imageArtifactId": "solar"},
        {"headline": "Wind generation", "layoutHint": "comparison"},
        {"headline": "Wind generation", "layoutHint": "text_image"},
    ]
    assets = [
        AssetMetadata(asset_id="solar", caption="Solar generation panels"),
        AssetMetadata(asset_id="wind", caption="Wind generation turbines"),
    ]
    ImageMatcher.assign_images_semantically(slides, assets)
    assert slides[0]["imageArtifactId"] == "solar"
    assert "imageArtifactId" not in slides[1]
    assert slides[2]["imageArtifactId"] == "wind"
