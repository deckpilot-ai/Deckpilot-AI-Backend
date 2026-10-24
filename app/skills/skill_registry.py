"""Presentation skill registry and domain knowledge rules."""

from dataclasses import dataclass


@dataclass
class PresentationSkill:
    name: str
    description: str
    target_audiences: list[str]
    narrative_rules: list[str]
    visual_principles: list[str]
    recommended_layouts: list[str]
    chart_recommendations: list[str]
    color_palette_hint: tuple[str, str, str]  # (primary, accent, neutral)
    title_font_hint: str
    body_font_hint: str
    qa_checklist: list[str]


SKILL_CATALOG: dict[str, PresentationSkill] = {
    "executive_presentation": PresentationSkill(
        name="executive_presentation",
        description="Boardroom and senior leadership decks emphasizing strategic takeaway headlines, concise proof points, and KPI summaries.",
        target_audiences=["Board of Directors", "C-Suite Executives", "Steering Committees"],
        narrative_rules=[
            "Use Barbara Minto Pyramid Principle: Lead with the bottom-line takeaway on slide 1.",
            "Slide titles must state the strategic insight, not a category name.",
            "Maximum 3-4 high-impact bullets per slide.",
            "Include an explicit takeaway summary callout on every core slide.",
        ],
        visual_principles=[
            "Restrained corporate palette (Deep Navy, Slate, crisp white).",
            "High contrast and generous whitespace for effortless scanning.",
            "Big number KPI callouts for core financial and operational metrics.",
        ],
        recommended_layouts=["hero", "big_numbers", "two_column", "comparison", "roadmap", "closing"],
        chart_recommendations=["column", "bar", "line", "donut"],
        color_palette_hint=("#0F172A", "#2563EB", "#EEF2F8"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Every slide has an action headline", "No wall-of-text bullets", "All numbers have provenance"],
    ),
    "consulting_deck": PresentationSkill(
        name="consulting_deck",
        description="Structured, hypothesis-driven consulting presentations with rigorous comparative analysis, frameworks, and data backing.",
        target_audiences=["Client Leadership", "Strategy Teams", "Enterprise Stakeholders"],
        narrative_rules=[
            "Situation -> Complication -> Strategic Implication structure.",
            "Rigorous MECE (Mutually Exclusive, Collectively Exhaustive) structuring.",
            "Action titles summarizing the data proof points.",
        ],
        visual_principles=[
            "Structured comparison cards and quadrant matrices.",
            "Clean grid alignment with distinct card headers.",
            "Balanced information density with clear visual hierarchy.",
        ],
        recommended_layouts=["comparison", "matrix_quadrant", "process_steps", "card_grid", "two_column", "closing"],
        chart_recommendations=["waterfall", "stacked_bar", "stacked_column", "scatter"],
        color_palette_hint=("#132A52", "#0284C7", "#F0F4F8"),
        title_font_hint="Calibri",
        body_font_hint="Calibri",
        qa_checklist=["Hypothesis clearly stated", "Comparisons use parallel structure", "Frameworks have labels"],
    ),
    "technical_presentation": PresentationSkill(
        name="technical_presentation",
        description="Engineering, cloud architecture, and AI infrastructure decks featuring system diagrams, flow pipelines, and technical capability maps.",
        target_audiences=["Chief Technology Officers", "Engineers", "Architects", "Technical Evaluators"],
        narrative_rules=[
            "Problem in current architecture -> Solution architecture -> Capabilities & Benchmarks -> Deployment Roadmap.",
            "Avoid generic marketing fluff; focus on performance, scalability, security, and latency.",
        ],
        visual_principles=[
            "Modern technical aesthetic: Deep Charcoal/Indigo with Electric Blue or Cyan accents.",
            "Hub-and-spoke and linear sequence connectors.",
            "Capability matrices with clear category groupings.",
        ],
        recommended_layouts=["architecture_diagram", "process_steps", "two_column", "card_grid", "matrix_quadrant", "timeline"],
        chart_recommendations=["line", "column", "bar", "area"],
        color_palette_hint=("#18181B", "#06B6D4", "#F4F4F5"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Architecture flow is clear", "Technical terms spelled correctly", "Deployment sequence is logical"],
    ),
    "pitch_deck": PresentationSkill(
        name="pitch_deck",
        description="Venture capital and investor pitch presentations designed to communicate huge market opportunity, unique moat, traction, and unit economics.",
        target_audiences=["Venture Capitalists", "Angel Investors", "Investment Committees"],
        narrative_rules=[
            "Problem -> Solution -> Market Size (TAM/SAM/SOM) -> Product & Moat -> Traction -> Business Model -> Team -> The Ask.",
            "Compelling narrative momentum on every slide.",
        ],
        visual_principles=[
            "High visual energy, bold contrasting hero elements.",
            "Big growth charts and standout traction metrics.",
            "Visual product highlights and clean customer logos/proof.",
        ],
        recommended_layouts=["hero", "big_numbers", "chart_insight", "two_column", "card_grid", "closing"],
        chart_recommendations=["line", "column", "area", "donut"],
        color_palette_hint=("#1E1B4B", "#6366F1", "#EEF2FF"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Market size clearly quantified", "Traction growth rate visible", "The Ask and use of funds clear"],
    ),
    "financial_presentation": PresentationSkill(
        name="financial_presentation",
        description="Earnings reviews, financial audits, budget allocations, and M&A decks with exact numeric provenance and native charts.",
        target_audiences=["CFOs", "Financial Analysts", "Investors", "Audit Committees"],
        narrative_rules=[
            "Financial Highlights -> Revenue Drivers -> Margin Evolution -> Cash Flow & Balance Sheet -> Guidance.",
            "Every metric must have explicit units and provenance.",
        ],
        visual_principles=[
            "Precision data styling, clean tables with zebra striping and right-aligned numbers.",
            "Uncluttered native bar, column, and waterfall charts.",
            "Subdued corporate colors (Navy, Forest Green for positive delta).",
        ],
        recommended_layouts=["table_focus", "chart_focus", "metrics_grid", "two_column", "closing"],
        chart_recommendations=["waterfall", "column", "stacked_column", "line", "bar"],
        color_palette_hint=("#0F2922", "#059669", "#F0FDF4"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["All numbers cross-check", "Units and currency symbols specified", "Tables formatted correctly"],
    ),
    "research_education": PresentationSkill(
        name="research_education",
        description="Educational lectures, textbook chapter syntheses, historical narratives, and academic research presentations.",
        target_audiences=["Students", "Researchers", "Domain Specialists", "Educators"],
        narrative_rules=[
            "Foundational context -> Core concepts & mechanisms -> Evidence & Artifacts -> Chronological evolution -> Synthesis & Open questions.",
            "Preserve domain authenticity and factual grounding.",
        ],
        visual_principles=[
            "Warm editorial feel with illustrated source figures and documentary captions.",
            "Structured chronological timelines and institutional hierarchies.",
            "Calm, readable typography with generous card containers.",
        ],
        recommended_layouts=["hero", "image_focus", "timeline", "two_column", "card_grid", "closing"],
        chart_recommendations=["bar", "column", "pie"],
        color_palette_hint=("#3D2619", "#D97706", "#FDFBF7"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Figures have documentary captions", "Chronology is sequential", "Synthesis concludes deck"],
    ),
    # ── 10 Benchmark Presentation Purpose Skills from deck_training_dataset ──
    "compare_and_contrast_brief": PresentationSkill(
        name="compare_and_contrast_brief",
        description="Side-by-side comparative analysis of concepts, systems, periods, or competing frameworks.",
        target_audiences=["Strategy Leaders", "Evaluators", "Analysts", "Academic Committees"],
        narrative_rules=[
            "Balanced juxtaposition of dimensions across compared entities.",
            "Parallel bullet structure in column pairs for instant readability.",
            "Synthesize conclusive differentiating points and tradeoffs.",
        ],
        visual_principles=[
            "Two-column comparative containers with contrasting accents.",
            "Structured comparison tables and paired image highlights.",
            "Clear dimensional headers across columns.",
        ],
        recommended_layouts=["cover", "agenda", "two_column", "bullets_image", "gallery", "glossary", "stat", "closing"],
        chart_recommendations=["bar", "column", "radar"],
        color_palette_hint=("#1E229E", "#6F9545", "#F8F9FA"),
        title_font_hint="Cambria",
        body_font_hint="Calibri",
        qa_checklist=["Compared entities have parallel criteria", "Tradeoffs clearly articulated", "No uneven column heights"],
    ),
    "evidence_and_data_review": PresentationSkill(
        name="evidence_and_data_review",
        description="Data-heavy analytical review anchored in empirical proof points, statistical measurements, and verified facts.",
        target_audiences=["Research Directors", "Technical Evaluators", "Data Teams", "Audit Committees"],
        narrative_rules=[
            "Data provenance and methodology stated upfront.",
            "Numbered sequences for empirical proof points.",
            "Every statistic must be qualified with source and scope.",
        ],
        visual_principles=[
            "Prominent stat and stat_row metric callouts.",
            "Clean numbered cards with high contrast values.",
            "Balanced distribution of charts and verified tables.",
        ],
        recommended_layouts=["cover", "agenda", "stat_row", "stat", "bullets_numbered", "bullets_cards", "two_column", "summary", "closing"],
        chart_recommendations=["column", "line", "scatter", "bar"],
        color_palette_hint=("#141D1A", "#E245C5", "#F4F6F8"),
        title_font_hint="Calibri",
        body_font_hint="Calibri",
        qa_checklist=["All statistics have provenance", "Numbered evidence flows logically", "Data ranges explicitly labeled"],
    ),
    "exam_revision_pack": PresentationSkill(
        name="exam_revision_pack",
        description="High-yield educational study pack emphasizing core concepts, review questions, summary takeaways, and key terms.",
        target_audiences=["Students", "Instructors", "Certification Candidates", "Study Groups"],
        narrative_rules=[
            "Inquiry-first structure with explicit review question checkpoints.",
            "High-density bullet cards decomposing complex topics into memorable bites.",
            "Clear wrap-up summaries and self-testing triggers.",
        ],
        visual_principles=[
            "Question cards with distinct accent badge styling.",
            "Card-grid layouts for definition chunks and formulas.",
            "High contrast text on clean backgrounds (>= 9:1 ratio).",
        ],
        recommended_layouts=["cover", "agenda", "questions", "bullets_numbered", "bullets_cards", "two_column", "summary", "closing"],
        chart_recommendations=["column", "pie", "bar"],
        color_palette_hint=("#5A653D", "#779950", "#FFFFFF"),
        title_font_hint="Century Schoolbook",
        body_font_hint="Calibri",
        qa_checklist=["Question slides clearly delineated", "No answer leakage in questions slide", "Takeaways summarize all chapters"],
    ),
    "executive_briefing": PresentationSkill(
        name="executive_briefing",
        description="Boardroom and senior leadership deck delivering decisive findings, strategic context, and high-impact takeaways.",
        target_audiences=["Board of Directors", "C-Suite Executives", "Steering Committees"],
        narrative_rules=[
            "Lead with bottom-line conclusion on slide 1 (Pyramid Principle).",
            "Action-oriented headlines strictly 1 to 4 words conveying strategic insight.",
            "Maximum 3-5 proof bullets per slide with explicit takeaway callouts.",
        ],
        visual_principles=[
            "Restrained corporate palette with generous whitespace.",
            "Alternating layout rhythm: no consecutive identical layouts.",
            "High-contrast card containers with subtle dividing accents.",
        ],
        recommended_layouts=["cover", "agenda", "roadmap", "questions", "bullets_image", "bullets_cards", "two_column", "bullets_numbered", "stat_row", "quote", "summary", "closing"],
        chart_recommendations=["column", "bar", "line", "donut"],
        color_palette_hint=("#7E5033", "#9B983C", "#F3EAE4"),
        title_font_hint="Cambria",
        body_font_hint="Calibri",
        qa_checklist=["Action headline on every slide", "No wall-of-text bullets", "Speaker notes cite source"],
    ),
    "glossary_spotlight": PresentationSkill(
        name="glossary_spotlight",
        description="Term-focused taxonomy deck establishing precise definitions, key entities, and vocabulary mastery.",
        target_audiences=["Learners", "Domain Specialists", "Onboarding Teams", "Technical Writers"],
        narrative_rules=[
            "Precise canonical definitions with semantic grouping.",
            "Contextual real-world usage examples for each term.",
            "Review inquiry checkpoints testing comprehension.",
        ],
        visual_principles=[
            "Clean term cards and glossary grid layouts.",
            "Bold term headers paired with concise definitions.",
            "Consistent typography hierarchy between term and meaning.",
        ],
        recommended_layouts=["cover", "agenda", "terms_cards", "glossary", "bullets_cards", "two_column", "questions", "closing"],
        chart_recommendations=["column", "bar"],
        color_palette_hint=("#3A225A", "#9C5928", "#FFFFFF"),
        title_font_hint="Georgia",
        body_font_hint="Calibri",
        qa_checklist=["Every term has a concise definition", "Terms cards don't overflow", "Grouping is domain-coherent"],
    ),
    "keynote_style_talk": PresentationSkill(
        name="keynote_style_talk",
        description="High-energy, minimalist keynote presentation featuring bold statements, hero visual impact, and memorable quotes.",
        target_audiences=["Conference Audiences", "All-Hands Meetings", "Industry Summits", "Public Gatherings"],
        narrative_rules=[
            "One core idea per slide — extreme cognitive focus.",
            "Punchy inspirational statement slides paired with hero imagery.",
            "Memorable quotes and statistics as keynote anchor points.",
        ],
        visual_principles=[
            "Minimalist layout with maximum focal clarity.",
            "Large hero typography on high-contrast surfaces.",
            "High-impact statement containers with zero visual clutter.",
        ],
        recommended_layouts=["cover", "statement", "bullets_image", "quote", "stat", "gallery", "closing"],
        chart_recommendations=["column", "donut", "bar"],
        color_palette_hint=("#243850", "#6FA641", "#FFFFFF"),
        title_font_hint="Trebuchet MS",
        body_font_hint="Calibri",
        qa_checklist=["No dense bullet lists", "Statements are punchy and bold", "Hero images have high resolution"],
    ),
    "lesson_plan": PresentationSkill(
        name="lesson_plan",
        description="Pedagogical classroom presentation with learning objectives, concept decomposition, classroom activities, and inquiry prompts.",
        target_audiences=["Students", "Educators", "Classroom Groups", "Training Cohorts"],
        narrative_rules=[
            "Explicit learning objectives and chapter roadmap.",
            "Alternating instructional content, activities, and reflection.",
            "Reinforcement checkpoints and inquiry prompts.",
        ],
        visual_principles=[
            "Clear activity and fact containers with distinct badges.",
            "Documentary illustrations paired with explanatory notes.",
            "Engaging rhythm between cards, questions, and roadmaps.",
        ],
        recommended_layouts=["cover", "roadmap", "questions", "activities", "facts", "bullets_image", "bullets_cards", "summary", "closing"],
        chart_recommendations=["column", "pie", "bar"],
        color_palette_hint=("#511453", "#4F964D", "#FFFFFF"),
        title_font_hint="Arial",
        body_font_hint="Calibri",
        qa_checklist=["Lesson objectives clear", "Activities have instructional prompts", "Inquiry questions present"],
    ),
    "roadmap_narrative": PresentationSkill(
        name="roadmap_narrative",
        description="Procedural or chronological narrative tracking phases, milestones, architectural transitions, and strategic horizon.",
        target_audiences=["Program Managers", "Steering Committees", "Engineering Teams", "Stakeholders"],
        narrative_rules=[
            "Strict chronological or phase-based sequence.",
            "Clear milestone dividers marking major transition boundaries.",
            "Explicit dependencies, outputs, and horizon timelines.",
        ],
        visual_principles=[
            "Process flows, timeline steps, and phase break dividers.",
            "Sequential milestone markers with status or chronology tags.",
            "Documentary artifact figures illustrating historical or technical phases.",
        ],
        recommended_layouts=["cover", "roadmap", "divider", "bullets_numbered", "bullets_image", "bullets_cards", "image_focus", "closing"],
        chart_recommendations=["line", "column", "bar", "area"],
        color_palette_hint=("#6D5519", "#68744D", "#FFFFFF"),
        title_font_hint="Cambria",
        body_font_hint="Arial",
        qa_checklist=["Phases flow in logical order", "Dividers delineate major sections", "Milestones have dates/labels"],
    ),
    "study_guide": PresentationSkill(
        name="study_guide",
        description="Comprehensive reference guide decomposing large complex texts or domains into structured chapters and review points.",
        target_audiences=["Researchers", "Domain Specialists", "Students", "Educators"],
        narrative_rules=[
            "Structured section dividers breaking down chapter hierarchy.",
            "Extractive factual bullets preserving source page provenance.",
            "Integrated vocabulary, questions, and thematic takeaways.",
        ],
        visual_principles=[
            "Rich editorial feel with section dividers and kicker tags.",
            "Alternating card grids, bullet image pairings, and number lists.",
            "Substantive speaker notes citing chapter sections and page numbers.",
        ],
        recommended_layouts=["cover", "agenda", "roadmap", "divider", "bullets_image", "two_column", "bullets_numbered", "bullets_cards", "glossary", "questions", "closing"],
        chart_recommendations=["column", "bar", "pie"],
        color_palette_hint=("#783C30", "#317685", "#FFFFFF"),
        title_font_hint="Georgia",
        body_font_hint="Arial",
        qa_checklist=["Dividers separate major chapters", "Notes cite source pages", "No missing section kickers"],
    ),
    "visual_storybook": PresentationSkill(
        name="visual_storybook",
        description="Documentary visual narrative weaving authentic historical artifacts, maps, figures, and storytelling into high-impact slides.",
        target_audiences=["General Audiences", "Museum Visitors", "Culture Enthusiasts", "Executive Visual Reviews"],
        narrative_rules=[
            "Visual-first narrative momentum: every spread features documentary imagery.",
            "Clean descriptive captions for every image, coin, sculpture, or map.",
            "Concise accompanying narrative points (no cluttered text).",
        ],
        visual_principles=[
            "Documentary visual ratio >= 60% of content slides.",
            "Framed and matted figure layouts with elegant captions.",
            "Deep background or paper surfaces enhancing visual warmth.",
        ],
        recommended_layouts=["cover", "bullets_image", "image_focus", "gallery", "statement", "quote", "closing"],
        chart_recommendations=["bar", "column"],
        color_palette_hint=("#7D1525", "#46A99A", "#FFFFFF"),
        title_font_hint="Bookman Old Style",
        body_font_hint="Arial",
        qa_checklist=["Every visual has an authentic caption", "Visual pacing ratio >= 60%", "Image frames properly matted"],
    ),
}


def get_skill_for_request(topic: str, presentation_type: str = "") -> PresentationSkill:
    """Matches the most appropriate presentation skill based on topic semantics and requested type."""
    t_lower = topic.lower()
    pt_lower = presentation_type.lower()
    combined = f"{t_lower} {pt_lower}"

    # 1. Direct Benchmark Purpose Matches
    if any(w in combined for w in ("compare", "comparison", "contrast", "vs", "versus")):
        return SKILL_CATALOG["compare_and_contrast_brief"]
    if any(w in combined for w in ("evidence", "data review", "empirical", "metrics review")):
        return SKILL_CATALOG["evidence_and_data_review"]
    if any(w in combined for w in ("exam", "revision", "quiz", "test prep")):
        return SKILL_CATALOG["exam_revision_pack"]
    if any(w in combined for w in ("briefing", "executive brief", "boardroom", "c-suite", "board")):
        return SKILL_CATALOG["executive_briefing"]
    if any(w in combined for w in ("glossary", "vocabulary", "terms", "taxonomy", "dictionary")):
        return SKILL_CATALOG["glossary_spotlight"]
    if any(w in combined for w in ("keynote", "talk", "all-hands", "summit", "keynote-style")):
        return SKILL_CATALOG["keynote_style_talk"]
    if any(w in combined for w in ("lesson", "lesson plan", "curriculum", "lecture", "teach", "classroom")):
        return SKILL_CATALOG["lesson_plan"]
    if any(w in combined for w in ("roadmap", "narrative", "transition", "chronology", "journey")):
        return SKILL_CATALOG["roadmap_narrative"]
    if any(w in combined for w in ("study guide", "chapter study", "ncert", "textbook")):
        return SKILL_CATALOG["study_guide"]
    if any(w in combined for w in ("storybook", "visual story", "documentary", "gallery", "photo story")):
        return SKILL_CATALOG["visual_storybook"]

    # 2. Domain & Style Fallbacks
    if "pitch" in pt_lower or "investor" in pt_lower or "seed" in t_lower or "series" in t_lower:
        return SKILL_CATALOG["pitch_deck"]
    if "tech" in pt_lower or "architecture" in pt_lower or "cloud" in t_lower or "ai" in t_lower or "software" in t_lower or "saas" in t_lower:
        return SKILL_CATALOG["technical_presentation"]
    if "finance" in pt_lower or "financial" in pt_lower or "earning" in t_lower or "budget" in t_lower or "revenue" in t_lower:
        return SKILL_CATALOG["financial_presentation"]
    if "history" in t_lower or "chapter" in t_lower or "research" in pt_lower:
        return SKILL_CATALOG["study_guide"]
    if "consulting" in pt_lower or "strategy" in t_lower or "assessment" in t_lower or "transformation" in t_lower:
        return SKILL_CATALOG["consulting_deck"]

    return SKILL_CATALOG["executive_briefing"]
