"""Structured data models and state contracts for DeckPilotAI presentation engine."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def normalize_bullet_items(value: Any) -> list[str]:
    """Convert common LLM bullet shapes into renderer-safe display strings.

    Planning providers occasionally return semantic objects (for example,
    ``{"label": "Nalanda", "value": "427 CE"}``) even though the rendering
    contract uses strings.  Preserve that useful content instead of allowing a
    provider formatting variation to fail the whole generation job.
    """
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    normalized: list[str] = []

    for item in items:
        text = ""
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            label = item.get("label") or item.get("title") or item.get("name") or item.get("heading")
            detail = (
                item.get("value")
                or item.get("text")
                or item.get("description")
                or item.get("detail")
                or item.get("content")
            )
            if label and detail and str(label).strip() != str(detail).strip():
                text = f"{label}: {detail}"
            elif detail or label:
                text = str(detail or label)
            else:
                scalar_values = [str(v).strip() for v in item.values() if isinstance(v, (str, int, float)) and str(v).strip()]
                text = ": ".join(scalar_values)
        elif isinstance(item, (int, float)):
            text = str(item)

        text = " ".join(text.split())
        if text:
            normalized.append(text)

    return normalized


class PresentationType(str, Enum):
    BUSINESS_STRATEGY = "business_strategy"
    EXECUTIVE_SUMMARY = "executive_summary"
    PITCH_DECK = "pitch_deck"
    INVESTOR_DECK = "investor_deck"
    SALES_PRESENTATION = "sales_presentation"
    TECHNICAL_ARCHITECTURE = "technical_architecture"
    PRODUCT_LAUNCH = "product_launch"
    RESEARCH_EDUCATION = "research_education"
    FINANCIAL_REVIEW = "financial_review"
    CONSULTING_DECK = "consulting_deck"
    MARKETING_PLAN = "marketing_plan"
    PROJECT_KICKOFF = "project_kickoff"


class LayoutFamily(str, Enum):
    HERO = "hero"
    TITLE_SUBTITLE = "title_subtitle"
    TWO_COLUMN = "two_column"
    THREE_COLUMN = "three_column"
    CARD_GRID = "card_grid"
    METRICS_GRID = "metrics_grid"
    BIG_NUMBERS = "big_numbers"
    PROCESS_STEPS = "process_steps"
    TIMELINE = "timeline"
    ROADMAP = "roadmap"
    COMPARISON = "comparison"
    BEFORE_AFTER = "before_after"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    MATRIX_QUADRANT = "matrix_quadrant"
    PYRAMID = "pyramid"
    FUNNEL = "funnel"
    CHART_FOCUS = "chart_focus"
    CHART_INSIGHT = "chart_insight"
    TABLE_FOCUS = "table_focus"
    QUOTE = "quote"
    DARK_QUOTE = "dark_quote"
    IMAGE_FOCUS = "image_focus"
    TEXT_IMAGE = "text_image"
    SECTION_DIVIDER = "section_divider"
    CLOSING = "closing"
    # Consulting Archetype Identifiers (A1-A30)
    A1_TITLE_BLOB = "A1"
    A2_TITLE_SPLIT = "A2"
    A3_DIVIDER_HERO = "A3"
    A4_ROADMAP_AGENDA = "A4"
    A5_DEFINITION = "A5"
    A6_TWO_ENTITY_COMPARISON = "A6"
    A7_TWO_COLUMN_CONTRAST = "A7"
    A8_STAT_IMAGE_HIGHLIGHT = "A8"
    A9_PROCESS_CHAIN = "A9"
    A10_NUMBERED_PROCESS = "A10"
    A11_STAGE_COLUMNS = "A11"
    A12_BEFORE_AFTER = "A12"
    A13_ICON_GRID = "A13"
    A14_CHART_INSIGHT = "A14"
    A15_DUAL_STAT_COMPARISON = "A15"
    A16_NATIVE_TABLE = "A16"
    A17_CLOSING_TAKEAWAYS = "A17"
    A18_RECAP_CHECKLIST = "A18"
    A19_GLOSSARY_GRID = "A19"
    A20_ORG_HIERARCHY = "A20"
    A21_KPI_CLUSTER = "A21"
    A22_HUB_SPOKE = "A22"
    A23_VERTICAL_PIPELINE = "A23"
    A24_TIMELINE_BAND = "A24"
    A25_COUNCIL_EIGHT = "A25"
    A26_TWO_HIGHWAYS = "A26"
    A27_FORTS_QUOTE_EMBLEM = "A27"
    A28_CONCEPT_DEFINITION_IMAGE = "A28"
    A29_BIG_QUESTIONS = "A29"
    A30_STEPPED_VALUE_CHAIN = "A30"
    # Specific semantic family patterns
    BIG_QUESTIONS = "big_questions"
    TIMELINE_BAND = "timeline_band"
    COUNCIL_EIGHT = "council_eight"
    TWO_HIGHWAYS = "two_highways"
    FORTS_QUOTE_EMBLEM = "forts_quote_emblem"
    CONCEPT_DEFINITION_IMAGE = "concept_definition_image"
    STEPPED_VALUE_CHAIN = "stepped_value_chain"


class ChartType(str, Enum):
    BAR = "bar"
    COLUMN = "column"
    STACKED_BAR = "stacked_bar"
    STACKED_COLUMN = "stacked_column"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    WATERFALL = "waterfall"


class ImagePlacementMode(str, Enum):
    CONTAIN = "contain"
    COVER = "cover"
    SIDE_VISUAL = "side_visual"
    HERO_VISUAL = "hero_visual"
    FRAME_INSET = "frame_inset"
    ROUNDED_CARD = "rounded_card"


class ChartSpec(BaseModel):
    chart_type: ChartType = ChartType.COLUMN
    title: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[dict[str, Any]] = Field(default_factory=list)  # list of {"name": str, "values": list[float]}
    units: str = ""
    number_format: str = "number"  # number | currency | percentage
    source_provenance: str = ""
    insight_takeaway: str = ""


class TableSpec(BaseModel):
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    column_alignments: list[Literal["left", "center", "right"]] = Field(default_factory=list)
    highlight_rows: list[int] = Field(default_factory=list)
    zebra_striping: bool = True
    title: str = ""


class DiagramNode(BaseModel):
    id: str = ""
    label: str = ""
    subtext: str = ""
    category: str = ""
    level: int = 1


class DiagramSpec(BaseModel):
    diagram_type: str = "process"  # process | timeline | matrix | quadrant | pyramid | hierarchy | capability
    nodes: list[DiagramNode] = Field(default_factory=list)
    connections: list[tuple[str, str]] = Field(default_factory=list)
    center_hub: str | None = None
    matrix_quadrants: dict[str, list[str]] = Field(default_factory=dict)  # {"Q1": [...], "Q2": [...]}


class FontConfig(BaseModel):
    name: str = "Calibri"
    fallback: str = "Arial"
    weight_bold: bool = False


class ColorPalette(BaseModel):
    ink: str = "#0C3B39"
    primary: str = "#0E7C7B"
    secondary: str = "#16A085"
    accent: str = "#0E7C7B"
    tint_a: str = "#E9F3F1"
    tint_b: str = "#F6EFE2"
    alert: str = "#C63A28"
    neutral: str = "#EEF2F8"
    background: str = "#FFFFFF"
    paper: str = "#FAFAF9"
    card_fill: str = "#F8FAFC"
    text_primary: str = "#0F172A"
    text_secondary: str = "#475569"
    text_on_dark: str = "#FFFFFF"
    chart_colors: list[str] = Field(default_factory=lambda: [
        "#2563EB", "#38BDF8", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#6366F1"
    ])


class TypographyHierarchy(BaseModel):
    title_font: FontConfig = Field(default_factory=lambda: FontConfig(name="Cambria"))
    body_font: FontConfig = Field(default_factory=lambda: FontConfig(name="Calibri"))
    numeric_font: FontConfig = Field(default_factory=lambda: FontConfig(name="Cambria"))
    hero_title_size: int = 36
    slide_title_size: int = 28
    subtitle_size: int = 14
    body_size: int = 13
    caption_size: int = 10
    kpi_number_size: int = 38


class DesignSystem(BaseModel):
    version: str = "2.0.0"
    subject_domain: str = "business"
    visual_tone: str = "executive"  # executive | modern_tech | clean_analytical | editorial | trustworthy
    colors: ColorPalette = Field(default_factory=ColorPalette)
    typography: TypographyHierarchy = Field(default_factory=TypographyHierarchy)
    card_corner_radius: float = 0.08  # inches / ratio
    card_stroke: bool = False
    slide_width_inches: float = 13.333
    slide_height_inches: float = 7.5
    margin_left_inches: float = 0.6
    margin_top_inches: float = 0.5
    margin_right_inches: float = 0.6
    margin_bottom_inches: float = 0.6
    visual_density: str = "balanced"  # compact | balanced | generous_whitespace


class SlideSpec(BaseModel):
    slide_id: str = "s01"
    slide_number: int = 1
    section: str = ""
    slide_type: str = "content"
    layout_family: LayoutFamily = LayoutFamily.TWO_COLUMN
    objective: str = ""
    key_message: str = ""
    headline: str = ""
    subtitle: str = ""
    eyebrow: str = ""
    bullets: list[str] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)  # [{"label": ..., "value": ..., "delta": ...}]
    takeaway: str = ""
    speaker_notes: str = ""
    
    # Archetype fields (A1-A23)
    archetype_id: str | None = None
    archetype_fields: dict[str, Any] = Field(default_factory=dict)
    
    # Visual elements
    image_artifact_id: str | None = None
    image_caption: str = ""
    image_placement: ImagePlacementMode = ImagePlacementMode.SIDE_VISUAL
    
    # Native charts, tables, diagrams
    chart_spec: ChartSpec | None = None
    table_spec: TableSpec | None = None
    diagram_spec: DiagramSpec | None = None
    quote: dict[str, str] | None = None  # {"text": ..., "attribution": ..., "source": ...}
    
    # Rendering metadata
    dark_background: bool = False
    background_override: str | None = None
    layout_hint: str = ""

    @field_validator("bullets", mode="before")
    @classmethod
    def normalize_bullets(cls, value: Any) -> list[str]:
        return normalize_bullet_items(value)

    @classmethod
    def model_validate(cls, obj: Any, **kwargs):
        if isinstance(obj, dict):
            # Aliases
            if "title" in obj and "headline" not in obj:
                obj["headline"] = obj["title"]
            if "key_takeaway" in obj and "takeaway" not in obj:
                obj["takeaway"] = obj["key_takeaway"]
            if "category" in obj and "eyebrow" not in obj:
                obj["eyebrow"] = obj["category"]
            if "chart" in obj and "chart_spec" not in obj:
                obj["chart_spec"] = obj["chart"]
            if "table" in obj and "table_spec" not in obj:
                obj["table_spec"] = obj["table"]
            if "diagram" in obj and "diagram_spec" not in obj:
                obj["diagram_spec"] = obj["diagram"]
            if "archetype" in obj and "archetype_id" not in obj:
                obj["archetype_id"] = obj["archetype"]
            
            # Layout mapping
            lf = obj.get("layout_family") or obj.get("archetype_id") or obj.get("layoutHint") or obj.get("layout_hint")
            if isinstance(lf, str):
                lf_norm = lf.upper().replace("-", "_").strip()
                layout_map = {
                    "HERO_TITLE": LayoutFamily.HERO,
                    "KPI_GRID": LayoutFamily.METRICS_GRID,
                    "METRICS_FOCUS": LayoutFamily.METRICS_GRID,
                    "PROCESS_FLOW": LayoutFamily.PROCESS_STEPS,
                    "MATRIX": LayoutFamily.MATRIX_QUADRANT,
                    "QUADRANT_MATRIX": LayoutFamily.MATRIX_QUADRANT,
                    "TEXT_AND_IMAGE": LayoutFamily.TEXT_IMAGE,
                    "IMAGE_AND_TEXT": LayoutFamily.TEXT_IMAGE,
                    "TABLE": LayoutFamily.TABLE_FOCUS,
                    "CHART": LayoutFamily.CHART_FOCUS,
                    "BIG_QUESTIONS": LayoutFamily.BIG_QUESTIONS,
                    "FOUR_CARD_NUMBERED_GRID": LayoutFamily.BIG_QUESTIONS,
                    "TIMELINE_BAND": LayoutFamily.TIMELINE_BAND,
                    "CHRONOLOGY_HORIZONTAL": LayoutFamily.TIMELINE_BAND,
                    "COUNCIL_EIGHT": LayoutFamily.COUNCIL_EIGHT,
                    "ASHTA_PRADHANA": LayoutFamily.COUNCIL_EIGHT,
                    "FEATURE_GRID_EIGHT": LayoutFamily.COUNCIL_EIGHT,
                    "TWO_HIGHWAYS": LayoutFamily.TWO_HIGHWAYS,
                    "TWO_ROUTES": LayoutFamily.TWO_HIGHWAYS,
                    "FORTS_QUOTE_EMBLEM": LayoutFamily.FORTS_QUOTE_EMBLEM,
                    "CORE_STATE_QUOTE": LayoutFamily.FORTS_QUOTE_EMBLEM,
                    "CONCEPT_DEFINITION_IMAGE": LayoutFamily.CONCEPT_DEFINITION_IMAGE,
                    "VOCAB_CALLOUT_IMAGE": LayoutFamily.CONCEPT_DEFINITION_IMAGE,
                    "STEPPED_VALUE_CHAIN": LayoutFamily.STEPPED_VALUE_CHAIN,
                    "MARKET_CHAIN": LayoutFamily.STEPPED_VALUE_CHAIN,
                }
                for i in range(1, 31):
                    suffix = (
                        'TITLE_BLOB' if i==1 else 'TITLE_SPLIT' if i==2 else 'DIVIDER_HERO' if i==3 else
                        'ROADMAP_AGENDA' if i==4 else 'DEFINITION' if i==5 else 'TWO_ENTITY_COMPARISON' if i==6 else
                        'TWO_COLUMN_CONTRAST' if i==7 else 'STAT_IMAGE_HIGHLIGHT' if i==8 else 'PROCESS_CHAIN' if i==9 else
                        'NUMBERED_PROCESS' if i==10 else 'STAGE_COLUMNS' if i==11 else 'BEFORE_AFTER' if i==12 else
                        'ICON_GRID' if i==13 else 'CHART_INSIGHT' if i==14 else 'DUAL_STAT_COMPARISON' if i==15 else
                        'NATIVE_TABLE' if i==16 else 'CLOSING_TAKEAWAYS' if i==17 else 'RECAP_CHECKLIST' if i==18 else
                        'GLOSSARY_GRID' if i==19 else 'ORG_HIERARCHY' if i==20 else 'KPI_CLUSTER' if i==21 else
                        'HUB_SPOKE' if i==22 else 'VERTICAL_PIPELINE' if i==23 else 'TIMELINE_BAND' if i==24 else
                        'COUNCIL_EIGHT' if i==25 else 'TWO_HIGHWAYS' if i==26 else 'FORTS_QUOTE_EMBLEM' if i==27 else
                        'CONCEPT_DEFINITION_IMAGE' if i==28 else 'BIG_QUESTIONS' if i==29 else 'STEPPED_VALUE_CHAIN'
                    )
                    layout_map[f"A{i}"] = getattr(LayoutFamily, f"A{i}_{suffix}")
                if lf in layout_map:
                    obj["layout_family"] = layout_map[lf]
                elif lf_norm in layout_map:
                    obj["layout_family"] = layout_map[lf_norm]
                elif lf.lower() in [e.value for e in LayoutFamily]:
                    obj["layout_family"] = LayoutFamily(lf.lower())
        return super().model_validate(obj, **kwargs)

    def __init__(self, **data: Any):
        # Allow passing alias kwargs
        if "title" in data and "headline" not in data:
            data["headline"] = data.pop("title")
        elif "title" in data:
            data.pop("title")
            
        if "key_takeaway" in data and "takeaway" not in data:
            data["takeaway"] = data.pop("key_takeaway")
        elif "key_takeaway" in data:
            data.pop("key_takeaway")

        if "category" in data and "eyebrow" not in data:
            data["eyebrow"] = data.pop("category")
        elif "category" in data:
            data.pop("category")

        if "chart" in data and "chart_spec" not in data:
            data["chart_spec"] = data.pop("chart")
        elif "chart" in data:
            data.pop("chart")

        if "table" in data and "table_spec" not in data:
            data["table_spec"] = data.pop("table")
        elif "table" in data:
            data.pop("table")

        if "diagram" in data and "diagram_spec" not in data:
            data["diagram_spec"] = data.pop("diagram")
        elif "diagram" in data:
            data.pop("diagram")

        lf = data.get("layout_family")
        if isinstance(lf, str):
            lf_norm = lf.upper().replace("-", "_").strip()
            layout_map = {
                "hero_title": LayoutFamily.HERO,
                "kpi_grid": LayoutFamily.METRICS_GRID,
                "metrics_focus": LayoutFamily.METRICS_GRID,
                "process_flow": LayoutFamily.PROCESS_STEPS,
                "matrix": LayoutFamily.MATRIX_QUADRANT,
                "quadrant_matrix": LayoutFamily.MATRIX_QUADRANT,
                "text_and_image": LayoutFamily.TEXT_IMAGE,
                "image_and_text": LayoutFamily.TEXT_IMAGE,
                "table": LayoutFamily.TABLE_FOCUS,
                "chart": LayoutFamily.CHART_FOCUS,
                "big_questions": LayoutFamily.BIG_QUESTIONS,
                "four_card_numbered_grid": LayoutFamily.BIG_QUESTIONS,
                "timeline_band": LayoutFamily.TIMELINE_BAND,
                "chronology_horizontal": LayoutFamily.TIMELINE_BAND,
                "council_eight": LayoutFamily.COUNCIL_EIGHT,
                "ashta_pradhana": LayoutFamily.COUNCIL_EIGHT,
                "two_highways": LayoutFamily.TWO_HIGHWAYS,
                "two_routes": LayoutFamily.TWO_HIGHWAYS,
                "forts_quote_emblem": LayoutFamily.FORTS_QUOTE_EMBLEM,
                "core_state_quote": LayoutFamily.FORTS_QUOTE_EMBLEM,
                "concept_definition_image": LayoutFamily.CONCEPT_DEFINITION_IMAGE,
                "vocab_callout_image": LayoutFamily.CONCEPT_DEFINITION_IMAGE,
                "stepped_value_chain": LayoutFamily.STEPPED_VALUE_CHAIN,
                "market_chain": LayoutFamily.STEPPED_VALUE_CHAIN,
            }
            for i in range(1, 31):
                suffix = (
                    'TITLE_BLOB' if i==1 else 'TITLE_SPLIT' if i==2 else 'DIVIDER_HERO' if i==3 else
                    'ROADMAP_AGENDA' if i==4 else 'DEFINITION' if i==5 else 'TWO_ENTITY_COMPARISON' if i==6 else
                    'TWO_COLUMN_CONTRAST' if i==7 else 'STAT_IMAGE_HIGHLIGHT' if i==8 else 'PROCESS_CHAIN' if i==9 else
                    'NUMBERED_PROCESS' if i==10 else 'STAGE_COLUMNS' if i==11 else 'BEFORE_AFTER' if i==12 else
                    'ICON_GRID' if i==13 else 'CHART_INSIGHT' if i==14 else 'DUAL_STAT_COMPARISON' if i==15 else
                    'NATIVE_TABLE' if i==16 else 'CLOSING_TAKEAWAYS' if i==17 else 'RECAP_CHECKLIST' if i==18 else
                    'GLOSSARY_GRID' if i==19 else 'ORG_HIERARCHY' if i==20 else 'KPI_CLUSTER' if i==21 else
                    'HUB_SPOKE' if i==22 else 'VERTICAL_PIPELINE' if i==23 else 'TIMELINE_BAND' if i==24 else
                    'COUNCIL_EIGHT' if i==25 else 'TWO_HIGHWAYS' if i==26 else 'FORTS_QUOTE_EMBLEM' if i==27 else
                    'CONCEPT_DEFINITION_IMAGE' if i==28 else 'BIG_QUESTIONS' if i==29 else 'STEPPED_VALUE_CHAIN'
                )
                layout_map[f"A{i}"] = getattr(LayoutFamily, f"A{i}_{suffix}")
            if lf in layout_map:
                data["layout_family"] = layout_map[lf]
            elif lf_norm in layout_map:
                data["layout_family"] = layout_map[lf_norm]
            elif lf.lower() in [e.value for e in LayoutFamily]:
                data["layout_family"] = LayoutFamily(lf.lower())

        super().__init__(**data)


class PresentationGoal(BaseModel):
    topic: str = ""
    objective: str = ""
    audience: str = "Executive Leadership"
    industry: str = "General"
    presentation_type: PresentationType | str = PresentationType.BUSINESS_STRATEGY
    target_slide_count: int = 8
    tone: str = "executive"
    visual_tone: str = "executive"
    narrative_arc: str = "pyramid"
    has_reference_docs: bool = False
    has_reference_ppt: bool = False
    required_charts: list[str] = Field(default_factory=list)
    required_tables: list[str] = Field(default_factory=list)
    # Explicit instructions from the user prompt (colors, themes, slide structure, sections, etc.)
    # that MUST be honoured by all downstream LLM agents.
    user_directives: str = ""
    # Structured slide-by-slide specifications extracted directly from user prompt
    explicit_slides: list[dict[str, Any]] = Field(default_factory=list)


class AssetMetadata(BaseModel):
    asset_id: str = ""
    source_file: str = ""
    page_or_slide: int = 1
    width: int = 0
    height: int = 0
    aspect_ratio: float = 1.0
    format: str = "png"
    sha256: str = ""
    perceptual_hash: str = ""
    caption: str = ""
    nearby_text: str = ""
    semantic_summary: str = ""
    relevance_score: float = 0.0
    quality_score: float = 1.0
    is_valid_figure: bool = True
    storage_key: str = ""


class ValidationSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ValidationCategory(str, Enum):
    GEOMETRY = "GEOMETRY"
    CONTENT = "CONTENT"
    DATA = "DATA"
    DESIGN = "DESIGN"
    TECHNICAL = "TECHNICAL"


class ValidationIssue(BaseModel):
    checkpoint_id: str = ""
    severity: ValidationSeverity = ValidationSeverity.MEDIUM
    category: ValidationCategory = ValidationCategory.GEOMETRY
    slide_id: str = ""
    slide_number: int = 1
    message: str = ""
    suggested_fix: str = ""
    auto_fixable: bool = True
    repair_action: str = ""


class QAReport(BaseModel):
    status: str = "passed"  # passed | issues_detected | failed
    overall_quality_score: float = 100.0
    issues: list[ValidationIssue] = Field(default_factory=list)
    checks_performed: list[str] = Field(default_factory=list)
    slide_count: int = 0
    repair_triggered: bool = False
    repair_iterations: int = 0
    checkpoints_total: int = 0
    checkpoints_passed: int = 0
    checkpoints_failed: int = 0


class GenerationState(BaseModel):
    job_id: str = ""
    project_id: str = ""
    user_prompt: str = ""
    presentation_goal: PresentationGoal = Field(default_factory=PresentationGoal)
    design_system: DesignSystem = Field(default_factory=DesignSystem)
    reference_assets: list[AssetMetadata] = Field(default_factory=list)
    reference_ppt_profile: dict[str, Any] = Field(default_factory=dict)
    grounded_context: str = ""
    slide_specs: list[SlideSpec] = Field(default_factory=list)
    deck_title: str = "Executive Presentation"
    qa_report: QAReport = Field(default_factory=QAReport)
    current_iteration: int = 0
    max_iterations: int = 2
    rendered_pptx_bytes: bytes | None = None
    storage_key: str = ""
