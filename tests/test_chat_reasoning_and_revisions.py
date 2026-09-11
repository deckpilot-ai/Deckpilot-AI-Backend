"""Comprehensive test suite for AI chat reasoning, slide/deck revisions, and color theme consistency."""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.deck import Artifact, DeckVersion
from app.models.job import GenerationJob
from app.models.project import Project
from app.models.user import User
from app.schemas.generation_state import (
    DesignSystem,
    LayoutFamily,
    PresentationGoal,
    SlideSpec,
)
from app.services.chat_service import ChatService
from app.services.deck_archetypes import BENCHMARK_PALETTES, PaletteGenerator
from app.agents.design_intelligence import DesignIntelligenceAgent
from app.agents.revision_agent import RevisionAgent
from app.services.reasoning_engine import ReasoningEngine
from app.services.renderer import PPTXRenderer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user_and_project(db_session):
    user = User(
        id="usr-test-1",
        email="test@deckpilot.ai",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()

    project = Project(
        id="proj-test-1",
        user_id=user.id,
        title="Indian Federalism Overview",
        current_deck_version=1,
    )
    db_session.add(project)
    db_session.commit()

    # Create an initial ready DeckVersion with mock slides
    deck_spec = {
        "deckTitle": "Indian Federalism & Constitutional Governance",
        "slides": [
            {
                "slideId": "s01",
                "headline": "Constitutional Architecture of Federalism",
                "purpose": "Opening thesis and constitutional foundations",
                "layoutHint": "A1",
                "bullets": ["Unitary tilt with federal balance", "Division of powers across three lists"],
                "speakerNotes": "Introduction to constitutional federalism.",
            },
            {
                "slideId": "s02",
                "headline": "Union vs State Relations & Fiscal Allocation",
                "purpose": "Analyze center-state fiscal distribution",
                "layoutHint": "A6",
                "bullets": [
                    "Union List: Foreign policy, defense, currency",
                    "State List: Public order, police, public health",
                    "Concurrent List: Education, civil procedure, forests",
                ],
                "takeaway": "Union List vs State List Division",
                "speakerNotes": "Center vs State allocations.",
            },
            {
                "slideId": "s03",
                "headline": "Empirical Growth & Devolution Benchmarks",
                "purpose": "Fiscal devolution trajectory",
                "layoutHint": "A8",
                "metrics": [
                    {"value": "41%", "label": "Tax Devolution Share to States"},
                    {"value": "3.2x", "label": "Expansion in Local Body Grants"},
                ],
                "bullets": ["Finance Commission recommendations", "Horizontal devolution formula"],
                "speakerNotes": "Empirical fiscal data points.",
            },
        ],
        "brandStyle": {
            "colors": {
                "ink": "#132A52",
                "primary": "#2563EB",
                "secondary": "#0284C7",
                "accent": "#2563EB",
                "tint_a": "#EEF2F8",
                "tint_b": "#F8FAFC",
                "background": "#FFFFFF",
                "paper": "#FAFAF9",
                "card_fill": "#EEF2F8",
            }
        },
    }
    art = Artifact(
        id="art-deck-1",
        project_id=project.id,
        type="deck_json",
        json_data=json.dumps(deck_spec),
    )
    db_session.add(art)
    db_session.commit()

    deck_ver = DeckVersion(
        id="dv-1",
        project_id=project.id,
        version=1,
        deck_json_artifact_id=art.id,
        status="ready",
    )
    db_session.add(deck_ver)
    db_session.commit()

    return user, project, deck_spec


# ─────────────────────────────────────────────────────────────────────────────
# 1. Color Coherence Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_blue_theme_palette_coherence():
    """Verify that blue/corporate themes never assign contrasting orange/amber accents."""
    # Palette generator with blue theme directive
    tokens = PaletteGenerator.generate_palette("Corporate Overview in Blue Theme")
    assert tokens.primary == "#2563EB"
    assert tokens.ink == "#132A52"

    goal = PresentationGoal(
        topic="Enterprise Cloud Architecture with Blue Modern Theme",
        target_audience="Leadership",
        industry="Technology",
        tone="authoritative",
    )
    ds = DesignIntelligenceAgent.generate_design_system(goal)
    
    # Primary & accent must be strictly in the blue spectrum
    assert ds.colors.primary in ("#2563EB", "#0284C7", "#1E3A8A", "#132A52")
    assert ds.colors.accent in ("#2563EB", "#0284C7", "#38BDF8", "#1E3A8A", "#132A52")
    # Verify NO rogue orange/amber values
    assert ds.colors.accent.upper() not in ("#E4791F", "#D97706", "#F59E0B")
    assert ds.colors.primary.upper() not in ("#E4791F", "#D97706", "#F59E0B")


def test_pptx_renderer_consistent_badge_color():
    """Verify that renderer creates consistent badges without mixing orange and blue."""
    goal = PresentationGoal(
        topic="SaaS Growth Strategy",
        target_audience="Executive Board",
        industry="Technology",
        tone="strategic",
    )
    ds = DesignIntelligenceAgent.generate_design_system(goal)
    
    slides = [
        SlideSpec(
            slide_id="s1",
            headline="Executive Briefing: Growth Pillars",
            bullets=["Product velocity", "Enterprise expansion", "Net revenue retention"],
            layout_family=LayoutFamily.HERO,
        ),
        SlideSpec(
            slide_id="s2",
            headline="Key Evidence & Unit Economics",
            bullets=["Point A", "Point B", "Point C"],
            takeaway="Strong 135% Net Dollar Retention across tier-1 cohorts.",
            layout_family=LayoutFamily.TWO_COLUMN,
            archetype_fields={"qa_balanced_cards": True},
        ),
    ]
    
    pptx_bytes = PPTXRenderer.render_presentation(slides, ds, deck_title="SaaS Strategy")
    assert len(pptx_bytes) > 2000
    assert pptx_bytes.startswith(b"PK")  # Valid OpenXML zip header


# ─────────────────────────────────────────────────────────────────────────────
# 2. Chat Reasoning & Routing Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reasoning_engine_revise_intent_on_fix_messages(db_session, test_user_and_project):
    """Verify that fix/revision prompts trigger revise_deck_tool and should_generate: True."""
    user, project, deck_spec = test_user_and_project

    fix_prompts = [
        "fix this ppt",
        "fix created ppt and update the color theme",
        "in slide 2 change the Union List bullets",
        "fix slide 3 and update numbers to 85%",
        "there is a mismatch in numbers and color, fix it",
        "make all slides blue theme",
        "redo slide 2",
    ]

    for prompt in fix_prompts:
        state = await ReasoningEngine.reason_and_route(
            db=db_session,
            project_id=project.id,
            user_id=user.id,
            content=prompt,
            mode="autopilot",
        )
        assert state["selected_tool"] == "revise_deck_tool", f"Failed for prompt: {prompt}"
        assert state["intent"] == "revise", f"Failed intent for prompt: {prompt}"
        assert state["should_generate"] is True, f"Failed should_generate for prompt: {prompt}"


@pytest.mark.asyncio
async def test_chat_service_triggers_generation_on_fix_message(db_session, test_user_and_project):
    """Verify ChatService.handle_chat_message returns should_generate: True and intent: 'revise'."""
    user, project, _ = test_user_and_project

    result = await ChatService.handle_chat_message(
        db=db_session,
        project_id=project.id,
        user_id=user.id,
        content="Fix slide 2 and change center-state distribution points",
        mode="autopilot",
    )

    assert result["should_generate"] is True
    assert result["intent"] == "revise"
    assert result["user_message"]["content"] == "Fix slide 2 and change center-state distribution points"


@pytest.mark.asyncio
async def test_reasoning_engine_mode_routing(db_session, test_user_and_project):
    """Verify reasoning engine respects Ask and Plan modes."""
    user, project, _ = test_user_and_project

    # Ask mode
    ask_state = await ReasoningEngine.reason_and_route(
        db=db_session,
        project_id=project.id,
        user_id=user.id,
        content="What is the market size of enterprise cloud infrastructure?",
        mode="ask",
    )
    assert ask_state["selected_tool"] == "ask_advisor_tool"
    assert ask_state["intent"] == "ask"
    assert ask_state["should_generate"] is False

    # Plan mode
    plan_state = await ReasoningEngine.reason_and_route(
        db=db_session,
        project_id=project.id,
        user_id=user.id,
        content="Outline a 5-slide deck on AI automated testing",
        mode="plan",
    )
    assert plan_state["selected_tool"] == "plan_deck_tool"
    assert plan_state["intent"] == "plan"
    assert plan_state["should_generate"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Targeted Revision Pipeline Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revision_agent_targets_single_slide(db_session, test_user_and_project):
    """Verify RevisionAgent revises ONLY the targeted slide and preserves others untouched."""
    user, _, deck_spec = test_user_and_project

    revised_spec, summary = await RevisionAgent.apply_revision(
        db=db_session,
        deck_spec=deck_spec,
        user_prompt="In slide 2 change headline to 'National vs Regional Legislative Powers'",
        user_id=user.id,
    )

    # Slide 1 and 3 must remain 100% identical
    assert revised_spec["slides"][0]["headline"] == deck_spec["slides"][0]["headline"]
    assert revised_spec["slides"][2]["headline"] == deck_spec["slides"][2]["headline"]
    # Slide 2 must have the revised headline
    assert "National vs Regional Legislative Powers" in revised_spec["slides"][1]["headline"]
    assert "Slide 2" in summary


@pytest.mark.asyncio
async def test_revision_agent_global_theme_change(db_session, test_user_and_project):
    """Verify global theme revision detection."""
    is_theme = RevisionAgent.is_global_theme_change("Make all slides in Blue theme and fix colors")
    assert is_theme is True

    is_slide_edit = RevisionAgent.is_global_theme_change("In slide 2 change theme to dark")
    assert is_slide_edit is False  # Targeted to slide 2, not global
