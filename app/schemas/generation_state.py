"""Structured data models and state contracts for DeckPilotAI presentation engine."""

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


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
    primary: str = "#132A52"
    secondary: str = "#0F172A"
    accent: str = "#2563EB"
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
    title_font: FontConfig = Field(default_factory=lambda: FontConfig(name="Segoe UI"))
    body_font: FontConfig = Field(default_factory=lambda: FontConfig(name="Segoe UI"))
    numeric_font: FontConfig = Field(default_factory=lambda: FontConfig(name="Segoe UI"))
    hero_title_size: int = 36
    slide_title_size: int = 24
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
    layout_hint: str = ""

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
            
            # Layout mapping
            lf = obj.get("layout_family")
            if isinstance(lf, str):
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
                }
                if lf in layout_map:
                    obj["layout_family"] = layout_map[lf]
                elif lf in [e.value for e in LayoutFamily]:
                    obj["layout_family"] = LayoutFamily(lf)
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
            }
            if lf in layout_map:
                data["layout_family"] = layout_map[lf]
            elif lf in [e.value for e in LayoutFamily]:
                data["layout_family"] = LayoutFamily(lf)

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
    severity: ValidationSeverity = ValidationSeverity.MEDIUM
    category: ValidationCategory = ValidationCategory.GEOMETRY
    slide_id: str = ""
    slide_number: int = 1
    message: str = ""
    suggested_fix: str = ""


class QAReport(BaseModel):
    status: str = "passed"  # passed | issues_detected | failed
    overall_quality_score: float = 100.0
    issues: list[ValidationIssue] = Field(default_factory=list)
    checks_performed: list[str] = Field(default_factory=list)
    slide_count: int = 0
    repair_triggered: bool = False
    repair_iterations: int = 0


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
