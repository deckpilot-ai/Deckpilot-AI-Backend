from app.agents.storyline_agent import StorylineAgent
from app.schemas.generation_state import AssetMetadata, PresentationGoal, SlideSpec
from app.services.image_matcher import ImageMatcher


def test_slide_spec_normalizes_structured_bullets() -> None:
    spec = SlideSpec(
        bullets=[
            {"label": "Nalanda", "value": "427 CE"},
            {"title": "Valabhi", "description": "480 CE"},
            {"text": "Vikramashila flourished from 783–820 CE"},
            1200,
            None,
            {},
        ]
    )

    assert spec.bullets == [
        "Nalanda: 427 CE",
        "Valabhi: 480 CE",
        "Vikramashila flourished from 783–820 CE",
        "1200",
    ]


def test_storyline_accepts_provider_structured_bullets() -> None:
    goal = PresentationGoal(topic="Ancient Indian universities", target_slide_count=1)
    plan = {
        "slides": [
            {
                "purpose": "Compare founding dates",
                "message": "Major centres of learning",
                "bullets": [
                    {"label": "Nalanda", "value": "427 CE"},
                    {"label": "Valabhi", "value": "480 CE"},
                    {"label": "Vikramashila", "value": "783–820 CE"},
                ],
            }
        ]
    }

    slides = StorylineAgent.create_storyline_plan(goal, llm_plan_spec=plan)

    assert slides[0].bullets == [
        "Nalanda: 427 CE",
        "Valabhi: 480 CE",
        "Vikramashila: 783–820 CE",
    ]


def test_image_matcher_normalizes_provider_bullets_before_joining() -> None:
    slides = [
        {
            "headline": "Major centres of learning",
            "purpose": "Compare founding dates",
            "layoutHint": "image_focus",
            "bullets": [{"label": "Nalanda", "value": "427 CE"}],
        }
    ]
    assets = [
        AssetMetadata(
            asset_id="nalanda-image",
            caption="Nalanda major centre of learning",
        )
    ]

    ImageMatcher.assign_images_semantically(slides, assets)

    assert slides[0]["bullets"] == ["Nalanda: 427 CE"]
    assert slides[0]["imageArtifactId"] == "nalanda-image"
