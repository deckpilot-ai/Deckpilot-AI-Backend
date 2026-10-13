"""Layout Archetype Library for Rise of Empires Editorial Theme (E01 - E23).

Fully implements all 23 reference layout builders with strict grid alignment,
zero text clipping, responsive typography, and authentic visual hierarchy.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from app.presentation.themes.rise_of_empires_editorial.tokens import COLORS, GEOMETRY, FONTS
from app.presentation.themes.rise_of_empires_editorial.components import (
    create_solid_shape, add_text_box, HistoricalSlideHeader, SlideFooter,
    IconBadge, NumberBadge, ParchmentCard, DarkInsightCard, GlossaryStrip,
    HistoricalImageFrame, HistoricalQuote, HubAndSpokeDiagram, HistoricalTimeline,
    TakeawayRow
)
from app.presentation.themes.rise_of_empires_editorial.icons import IconResolver

logger = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")


def get_image_asset(filename: str) -> str:
    path = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(path):
        return path
    # fallback check in icons
    ipath = os.path.join(ICONS_DIR, filename)
    if os.path.exists(ipath):
        return ipath
    return path


def set_slide_background(slide: Any, color: RGBColor):
    """Fills slide background solidly."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


# ====================================================================
# E01 — DARK COVER + QUOTE + IMAGE
# ====================================================================
def render_e01_dark_cover(
    slide: Any,
    kicker: str,
    title: str,
    quote: str,
    image_path: Optional[str] = None,
    caption: Optional[str] = None,
    slide_num: int = 1
):
    set_slide_background(slide, COLORS.rgb_canvas_dark)

    # Decorative dark teal circles in background
    create_solid_shape(slide, MSO_SHAPE.OVAL, 10.5, -1.0, 4.5, 4.5, fill_color=COLORS.rgb_dark_secondary)
    create_solid_shape(slide, MSO_SHAPE.OVAL, -1.5, 4.5, 4.0, 4.0, fill_color=COLORS.rgb_dark_secondary)

    # Kicker
    tb_k = add_text_box(slide, 0.55, 0.95, 11.0, 0.35)
    pk = tb_k.text_frame.paragraphs[0]
    pk.text = kicker.upper()
    pk.font.name = FONTS.body
    pk.font.size = Pt(12.0)
    pk.font.bold = True
    pk.font.color.rgb = COLORS.rgb_kicker

    # Cover Title
    tb_t = add_text_box(slide, 0.55, 1.45, 11.0, 1.20)
    pt = tb_t.text_frame.paragraphs[0]
    pt.text = title
    pt.font.name = FONTS.display
    pt.font.size = Pt(56.0)
    pt.font.bold = True
    pt.font.color.rgb = COLORS.rgb_white

    # Accent Divider Line
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(2.85), Inches(1.20), Inches(0.06))
    line.fill.solid()
    line.fill.fore_color.rgb = COLORS.rgb_accent
    line.line.fill.background()

    # Left Quote
    HistoricalQuote.render(
        slide,
        x=0.55,
        y=3.30,
        w=5.80,
        h=3.20,
        quote_text=quote,
        is_dark=True
    )

    # Right Historic Image
    img_file = image_path or get_image_asset("image-1-1.png")
    HistoricalImageFrame.render(
        slide,
        x=6.90,
        y=3.30,
        w=5.88,
        h=3.50,
        image_path=img_file,
        caption=caption or "Fig 5.1  Rock-cut cave in the Barabar Hills, Bihar (Mauryan period)",
        caption_h=0.45
    )

    SlideFooter.render(slide, slide_num=slide_num, is_dark=True)


# ====================================================================
# E02 — FOUR BIG QUESTIONS
# ====================================================================
def render_e02_big_questions(
    slide: Any,
    kicker: str,
    title: str,
    questions: List[str],  # 4 questions
    slide_num: int = 2
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=2)

    card_w = 2.85
    card_gap = 0.27
    card_h = 4.80
    start_x = 0.55
    start_y = 1.72

    for i in range(min(4, len(questions))):
        cx = start_x + i * (card_w + card_gap)
        # Parchment card
        ParchmentCard.render(slide, cx, start_y, card_w, card_h, fill_color=COLORS.rgb_parchment)

        # Number Badge
        NumberBadge.render(slide, cx + (card_w - 0.72) / 2.0, start_y + 0.50, str(i + 1), diameter=0.72, font_size_pt=16.0)

        # Centered Question Text
        tb = add_text_box(slide, cx + 0.20, start_y + 1.60, card_w - 0.40, card_h - 1.80)
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.text = questions[i]
        p.font.name = FONTS.display
        p.font.size = Pt(17.0)
        p.font.bold = True
        p.font.color.rgb = COLORS.rgb_heading
        p.line_spacing = 1.25

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E03 — EXPLANATION + IMAGE + GLOSSARY
# ====================================================================
def render_e03_explanation_image_glossary(
    slide: Any,
    kicker: str,
    title: str,
    body_paragraphs: List[str],
    image_path: Optional[str] = None,
    caption: Optional[str] = None,
    glossary_term: Optional[str] = None,
    glossary_def: Optional[str] = None,
    slide_num: int = 3
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=3)

    # Explanation card left
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=7.65,
        h=4.75,
        body_bullets=body_paragraphs,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=14.0
    )

    # Image right
    img_file = image_path or get_image_asset("image-3-3.png")
    HistoricalImageFrame.render(
        slide,
        x=8.55,
        y=1.72,
        w=4.23,
        h=3.60,
        image_path=img_file,
        caption=caption or "Fig 5.2  Silver punch-marked coin from the Mauryan period",
        caption_h=0.45
    )

    # Glossary strip below image
    if glossary_term and glossary_def:
        GlossaryStrip.render(
            slide,
            x=8.55,
            y=5.50,
            w=4.23,
            h=0.95,
            term=glossary_term,
            definition=glossary_def
        )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E04 — HUB + SIX FEATURES
# ====================================================================
def render_e04_hub_six_features(
    slide: Any,
    kicker: str,
    title: str,
    center_title: str,
    center_body: str,
    features: List[Tuple[str, str]],
    slide_num: int = 4
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=4)

    center_icon = os.path.join(ICONS_DIR, "image-4-2.png")
    HubAndSpokeDiagram.render(
        slide,
        center_title=center_title,
        center_body=center_body,
        features=features,
        center_icon_path=center_icon
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E05 — WHY / HOW + FOUR-IMAGE GALLERY
# ====================================================================
def render_e05_why_how_gallery(
    slide: Any,
    kicker: str,
    title: str,
    why_title: str,
    why_points: List[str],
    how_title: str,
    how_points: List[str],
    gallery_images: Optional[List[str]] = None,
    shared_caption: Optional[str] = None,
    slide_num: int = 5
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=5)

    # 1. Why Card (Top Left)
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=2.35,
        title=why_title,
        body_bullets=why_points,
        fill_color=COLORS.rgb_parchment,
        title_size_pt=16.0,
        body_size_pt=13.0
    )

    # 2. How Card (Bottom Left)
    ParchmentCard.render(
        slide,
        x=0.55,
        y=4.25,
        w=6.55,
        h=2.20,
        title=how_title,
        body_bullets=how_points,
        fill_color=COLORS.rgb_cream,
        title_size_pt=16.0,
        body_size_pt=13.0
    )

    # 3. 2x2 Gallery Right
    gw = 2.65
    gh = 2.15
    g_start_x = 7.45
    g_start_y = 1.72
    default_imgs = ["image-5-2.png", "image-5-3.png", "image-5-4.png", "image-5-5.png"]
    imgs = gallery_images or [get_image_asset(f) for f in default_imgs]

    coords = [
        (g_start_x, g_start_y),
        (g_start_x + gw + 0.15, g_start_y),
        (g_start_x, g_start_y + gh + 0.15),
        (g_start_x + gw + 0.15, g_start_y + gh + 0.15)
    ]

    for i in range(min(4, len(imgs))):
        ix, iy = coords[i]
        HistoricalImageFrame.render(
            slide,
            x=ix,
            y=iy,
            w=gw,
            h=gh,
            image_path=imgs[i]
        )

    # Shared Caption below gallery
    tb_c = add_text_box(slide, g_start_x, 6.25, gw * 2 + 0.15, 0.40)
    pc = tb_c.text_frame.paragraphs[0]
    pc.text = shared_caption or "Figs 5.4  Armies, warfare, fortified settlements and control of river networks"
    pc.font.name = FONTS.body
    pc.font.size = Pt(10.5)
    pc.font.italic = True
    pc.font.color.rgb = COLORS.rgb_muted

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E06 — BULLET EXPLANATION + HERO IMAGE + GLOSSARY
# ====================================================================
def render_e06_explanation_hero_glossary(
    slide: Any,
    kicker: str,
    title: str,
    bullet_points: List[str],
    hero_image: Optional[str] = None,
    caption: Optional[str] = None,
    glossary_term: Optional[str] = None,
    glossary_def: Optional[str] = None,
    slide_num: int = 6
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=6)

    # Narrative card left
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=7.65,
        h=4.75,
        body_bullets=bullet_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=14.0
    )

    # Hero image right
    img_file = hero_image or get_image_asset("image-6-2.png")
    HistoricalImageFrame.render(
        slide,
        x=8.55,
        y=1.72,
        w=4.23,
        h=3.55,
        image_path=img_file,
        caption=caption or "River and sea trade carried Indian goods to distant lands",
        caption_h=0.45
    )

    # Glossary strip below image
    term = glossary_term or "Shreni"
    definition = glossary_def or "an ancient Indian guild of traders or craftsmen with its own rules, assembly and treasury"
    GlossaryStrip.render(
        slide,
        x=8.55,
        y=5.50,
        w=4.23,
        h=0.95,
        term=term,
        definition=definition
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E07 — MAP + EXPLANATION
# ====================================================================
def render_e07_map_explanation(
    slide: Any,
    kicker: str,
    title: str,
    narrative_points: List[str],
    map_image: Optional[str] = None,
    caption: Optional[str] = None,
    slide_num: int = 7
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=7)

    # Text card left
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=4.40,
        h=4.75,
        body_bullets=narrative_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=14.0
    )

    # Dominant Map right
    map_file = map_image or get_image_asset("image-7-2.png")
    HistoricalImageFrame.render(
        slide,
        x=5.25,
        y=1.72,
        w=7.53,
        h=4.75,
        image_path=map_file,
        caption=caption or "Fig 5.5  Major trade routes and cities from the 6th century BCE onward",
        caption_h=0.45
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E08 — EXPLANATION + HISTORICAL IMAGE + INSIGHT
# ====================================================================
def render_e08_explanation_image_insight(
    slide: Any,
    kicker: str,
    title: str,
    narrative_points: List[str],
    image_path: Optional[str] = None,
    caption: Optional[str] = None,
    insight_title: Optional[str] = None,
    insight_body: Optional[str] = None,
    slide_num: int = 8
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=8)

    # Top Left Narrative Card
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=3.50,
        body_bullets=narrative_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    # Top Right Image
    img_file = image_path or get_image_asset("image-8-3.png")
    HistoricalImageFrame.render(
        slide,
        x=7.40,
        y=1.72,
        w=5.38,
        h=3.50,
        image_path=img_file,
        caption=caption or "Fig 5.6  Ancient Magadhan stone sculpture",
        caption_h=0.45
    )

    # Bottom Full-width Insight Strip
    DarkInsightCard.render(
        slide,
        x=0.55,
        y=5.45,
        w=12.23,
        h=1.15,
        title=insight_title or "Strategic Advantage of Magadha",
        body_text=insight_body or "Rich iron ore deposits around Rajgriha and dense elephant forests gave Magadha unmatched military power.",
        title_size_pt=14.0,
        body_size_pt=12.5
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E09 — NARRATIVE + ARTEFACT + MAP + INSIGHT
# ====================================================================
def render_e09_narrative_artefact_map(
    slide: Any,
    kicker: str,
    title: str,
    narrative: str,
    artefact_image: Optional[str] = None,
    map_image: Optional[str] = None,
    insight_text: Optional[str] = None,
    slide_num: int = 9
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=9)

    # 1. Narrative Card (Upper Left)
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=5.80,
        h=2.20,
        body_bullets=[narrative],
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    # 2. Artefact Frame (Lower Left)
    art_file = artefact_image or get_image_asset("image-9-2.png")
    HistoricalImageFrame.render(
        slide,
        x=0.55,
        y=4.15,
        w=2.75,
        h=2.30,
        image_path=art_file,
        caption="Punch-marked coin",
        caption_h=0.35
    )

    # 3. Dark Insight Card (Lower Middle)
    DarkInsightCard.render(
        slide,
        x=3.50,
        y=4.15,
        w=2.85,
        h=2.30,
        title="Standing Army",
        body_text=insight_text or "Greek sources report the Nandas maintained 200,000 infantry, 20,000 cavalry and 3,000 war elephants.",
        title_size_pt=14.0,
        body_size_pt=12.0
    )

    # 4. Map Right
    m_file = map_image or get_image_asset("image-9-3.png")
    HistoricalImageFrame.render(
        slide,
        x=6.65,
        y=1.72,
        w=6.13,
        h=4.75,
        image_path=m_file,
        caption="Fig 5.8  The Nanda Empire at its peak extent",
        caption_h=0.45
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E10 — TWO NARRATIVE PANELS + MULTIPLE MAPS
# ====================================================================
def render_e10_narrative_multiple_maps(
    slide: Any,
    kicker: str,
    title: str,
    panel1_title: str,
    panel1_points: List[str],
    panel2_title: str,
    panel2_points: List[str],
    bust_image: Optional[str] = None,
    route_map: Optional[str] = None,
    slide_num: int = 10
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=10)

    # Two stacked cards left
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=5.50,
        h=2.30,
        title=panel1_title,
        body_bullets=panel1_points,
        fill_color=COLORS.rgb_parchment,
        title_size_pt=15.0,
        body_size_pt=12.5
    )

    ParchmentCard.render(
        slide,
        x=0.55,
        y=4.20,
        w=5.50,
        h=2.25,
        title=panel2_title,
        body_bullets=panel2_points,
        fill_color=COLORS.rgb_cream,
        title_size_pt=15.0,
        body_size_pt=12.5
    )

    # Alexander bust upper right
    b_file = bust_image or get_image_asset("image-10-2.png")
    HistoricalImageFrame.render(
        slide,
        x=6.35,
        y=1.72,
        w=6.43,
        h=2.30,
        image_path=b_file,
        caption="Fig 5.10  Alexander of Macedonia",
        caption_h=0.35
    )

    # Route map lower right
    r_file = route_map or get_image_asset("image-10-3.png")
    HistoricalImageFrame.render(
        slide,
        x=6.35,
        y=4.20,
        w=6.43,
        h=2.25,
        image_path=r_file,
        caption="Fig 5.11  Alexander's campaign route into the Indus Valley",
        caption_h=0.35
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E11 — BODY + ARTEFACT + DID-YOU-KNOW
# ====================================================================
def render_e11_body_artefact_did_you_know(
    slide: Any,
    kicker: str,
    title: str,
    narrative_points: List[str],
    artefact_image: Optional[str] = None,
    caption: Optional[str] = None,
    dyk_title: Optional[str] = None,
    dyk_body: Optional[str] = None,
    slide_num: int = 11
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=11)

    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=3.50,
        body_bullets=narrative_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    art_file = artefact_image or get_image_asset("image-11-2.png")
    HistoricalImageFrame.render(
        slide,
        x=7.40,
        y=1.72,
        w=5.38,
        h=3.50,
        image_path=art_file,
        caption=caption or "Fig 5.12  Silver decadrachm commemorating the Battle of the Hydaspes",
        caption_h=0.45
    )

    DarkInsightCard.render(
        slide,
        x=0.55,
        y=5.45,
        w=12.23,
        h=1.15,
        title=dyk_title or "Did You Know?",
        body_text=dyk_body or "Alexander's soldiers mutinied at the River Hyphasis (Beas) after hearing of the immense military might of the Nanda Empire.",
        title_size_pt=14.0,
        body_size_pt=12.5
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E12 — BODY + DOMINANT MAP
# ====================================================================
def render_e12_body_dominant_map(
    slide: Any,
    kicker: str,
    title: str,
    narrative_points: List[str],
    map_image: Optional[str] = None,
    caption: Optional[str] = None,
    slide_num: int = 12
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=12)

    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=4.20,
        h=4.75,
        body_bullets=narrative_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    m_file = map_image or get_image_asset("image-12-2.png")
    HistoricalImageFrame.render(
        slide,
        x=5.05,
        y=1.72,
        w=7.73,
        h=4.75,
        image_path=m_file,
        caption=caption or "Fig 5.13  The Mauryan Empire at its peak under Ashoka (3rd century BCE)",
        caption_h=0.45
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E13 — BIOGRAPHY + PAINTING + DEFINITION
# ====================================================================
def render_e13_biography_painting_definition(
    slide: Any,
    kicker: str,
    title: str,
    biography_points: List[str],
    painting_image: Optional[str] = None,
    caption: Optional[str] = None,
    definition_term: Optional[str] = None,
    definition_text: Optional[str] = None,
    slide_num: int = 13
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=13)

    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=3.50,
        body_bullets=biography_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    p_file = painting_image or get_image_asset("image-13-2.png")
    HistoricalImageFrame.render(
        slide,
        x=7.40,
        y=1.72,
        w=5.38,
        h=3.50,
        image_path=p_file,
        caption=caption or "Fig 5.14  Kautilya (Chanakya), royal adviser to Chandragupta Maurya",
        caption_h=0.45
    )

    GlossaryStrip.render(
        slide,
        x=0.55,
        y=5.45,
        w=12.23,
        h=1.05,
        term=definition_term or "Arthashastra",
        definition=definition_text or "an ancient treatise on statecraft, economic policy, military strategy and administrative law authored by Kautilya"
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E14 — SEVEN-PART FRAMEWORK (THE SAPTANGA)
# ====================================================================
def render_e14_seven_part_framework(
    slide: Any,
    kicker: str,
    title: str,
    limbs: List[Tuple[str, str, str]],  # (sanskrit_name, english_role, desc) 7 items
    takeaway_text: Optional[str] = None,
    slide_num: int = 14
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=14)

    # Top row: 4 cards
    row1_w = 2.85
    row1_gap = 0.27
    y1 = 1.72
    h1 = 1.95

    for i in range(min(4, len(limbs))):
        sanskrit, role, desc = limbs[i]
        x = 0.55 + i * (row1_w + row1_gap)
        ParchmentCard.render(
            slide, x, y1, row1_w, h1,
            title=f"{sanskrit} ({role})",
            body_bullets=[desc],
            fill_color=COLORS.rgb_parchment,
            title_size_pt=13.5,
            body_size_pt=11.5
        )

    # Bottom row: 3 centered cards
    row2_w = 3.60
    row2_gap = 0.35
    row2_start_x = 0.55 + (12.233 - (3 * row2_w + 2 * row2_gap)) / 2.0
    y2 = 3.85
    h2 = 1.90

    for i in range(4, min(7, len(limbs))):
        idx = i - 4
        sanskrit, role, desc = limbs[i]
        x = row2_start_x + idx * (row2_w + row2_gap)
        ParchmentCard.render(
            slide, x, y2, row2_w, h2,
            title=f"{sanskrit} ({role})",
            body_bullets=[desc],
            fill_color=COLORS.rgb_cream,
            title_size_pt=13.5,
            body_size_pt=11.5
        )

    # Full width takeaway strip
    if takeaway_text:
        DarkInsightCard.render(
            slide,
            x=0.55,
            y=5.95,
            w=12.23,
            h=0.75,
            body_text=takeaway_text,
            body_size_pt=11.5
        )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E15 — DARK PHILOSOPHY / QUOTE
# ====================================================================
def render_e15_dark_quote(
    slide: Any,
    kicker: str,
    title: str,
    quote: str,
    attribution: str,
    principles: List[Tuple[str, str]],  # up to 3 (title, desc)
    slide_num: int = 15
):
    set_slide_background(slide, COLORS.rgb_canvas_dark)

    # Decorative circles
    create_solid_shape(slide, MSO_SHAPE.OVAL, 11.0, -1.0, 4.0, 4.0, fill_color=COLORS.rgb_dark_secondary)
    create_solid_shape(slide, MSO_SHAPE.OVAL, -1.0, 5.0, 3.5, 3.5, fill_color=COLORS.rgb_dark_secondary)

    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=15, is_dark=True)

    # Large Quote Left
    HistoricalQuote.render(
        slide,
        x=0.55,
        y=1.95,
        w=5.80,
        h=4.50,
        quote_text=quote,
        attribution=attribution,
        is_dark=True
    )

    # 3 Principle Cards Right
    p_start_y = 1.95
    p_h = 1.35
    p_gap = 0.22
    p_w = 5.88
    p_x = 6.90

    for i in range(min(3, len(principles))):
        p_title, p_desc = principles[i]
        py = p_start_y + i * (p_h + p_gap)

        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            p_x,
            py,
            p_w,
            p_h,
            fill_color=COLORS.rgb_dark_secondary,
            border_color=None,
            shadow=True
        )

        NumberBadge.render(slide, p_x + 0.25, py + 0.35, str(i + 1), diameter=0.55, font_size_pt=12.0)

        tb = add_text_box(slide, p_x + 1.05, py + 0.18, p_w - 1.25, p_h - 0.36)
        tf = tb.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = p_title
        p0.font.name = FONTS.display
        p0.font.size = Pt(15.0)
        p0.font.bold = True
        p0.font.color.rgb = COLORS.rgb_white
        p0.space_after = Pt(3)

        p1 = tf.add_paragraph()
        p1.text = p_desc
        p1.font.name = FONTS.body
        p1.font.size = Pt(12.0)
        p1.font.color.rgb = COLORS.rgb_text_on_dark

    SlideFooter.render(slide, slide_num=slide_num, is_dark=True)


# ====================================================================
# E16 — HISTORICAL EVENT + IMAGE + GLOSSARY
# ====================================================================
def render_e16_event_image_glossary(
    slide: Any,
    kicker: str,
    title: str,
    event_narrative: List[str],
    event_image: Optional[str] = None,
    caption: Optional[str] = None,
    glossary_term: Optional[str] = None,
    glossary_def: Optional[str] = None,
    slide_num: int = 16
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=16)

    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=3.50,
        body_bullets=event_narrative,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    img_file = event_image or get_image_asset("image-16-2.png")
    HistoricalImageFrame.render(
        slide,
        x=7.40,
        y=1.72,
        w=5.38,
        h=3.50,
        image_path=img_file,
        caption=caption or "Fig 5.16  Major Rock Edict XIII recording Ashoka's remorse over Kalinga",
        caption_h=0.45
    )

    GlossaryStrip.render(
        slide,
        x=0.55,
        y=5.45,
        w=12.23,
        h=1.05,
        term=glossary_term or "Dhamma",
        definition=glossary_def or "the Prakrit form of dharma; Ashoka's moral code emphasizing non-violence, truthfulness, religious tolerance and mutual respect"
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E17 — BODY + MAP + HISTORICAL DOCUMENT
# ====================================================================
def render_e17_body_map_document(
    slide: Any,
    kicker: str,
    title: str,
    narrative_points: List[str],
    map_image: Optional[str] = None,
    doc_image: Optional[str] = None,
    slide_num: int = 17
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=17)

    col_w = 3.90
    col_gap = 0.26

    # 1. Narrative Left
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=col_w,
        h=4.75,
        body_bullets=narrative_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.0
    )

    # 2. Map Center
    m_file = map_image or get_image_asset("image-17-2.png")
    HistoricalImageFrame.render(
        slide,
        x=0.55 + col_w + col_gap,
        y=1.72,
        w=col_w,
        h=4.75,
        image_path=m_file,
        caption="Fig 5.17  Distribution of Ashoka's edicts",
        caption_h=0.45
    )

    # 3. Rock Inscription Photo Right
    d_file = doc_image or get_image_asset("image-17-3.png")
    HistoricalImageFrame.render(
        slide,
        x=0.55 + 2 * (col_w + col_gap),
        y=1.72,
        w=col_w,
        h=4.75,
        image_path=d_file,
        caption="Fig 5.18  Brahmi rock edict inscription",
        caption_h=0.45
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E18 — DAILY LIFE + ARTEFACT + CONTEXT
# ====================================================================
def render_e18_daily_life_artefact(
    slide: Any,
    kicker: str,
    title: str,
    narrative_points: List[str],
    artefact_image: Optional[str] = None,
    caption: Optional[str] = None,
    context_text: Optional[str] = None,
    slide_num: int = 18
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=18)

    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=3.50,
        body_bullets=narrative_points,
        fill_color=COLORS.rgb_parchment,
        body_size_pt=13.5
    )

    art_file = artefact_image or get_image_asset("image-18-2.png")
    HistoricalImageFrame.render(
        slide,
        x=7.40,
        y=1.72,
        w=5.38,
        h=3.50,
        image_path=art_file,
        caption=caption or "Fig 5.19  Mauryan ring stone and terracotta pottery",
        caption_h=0.45
    )

    DarkInsightCard.render(
        slide,
        x=0.55,
        y=5.45,
        w=12.23,
        h=1.15,
        title="Urban Life at Pataliputra",
        body_text=context_text or "Megasthenes described Pataliputra as a grand city with 64 gates and 570 towers, governed by a board of thirty municipal officials.",
        title_size_pt=14.0,
        body_size_pt=12.5
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E19 — HERO ARTEFACT + EXPLANATION + SUPPORTING IMAGES
# ====================================================================
def render_e19_hero_artefact_showcase(
    slide: Any,
    kicker: str,
    title: str,
    explanation_title: str,
    explanation_points: List[str],
    hero_image: Optional[str] = None,
    hero_caption: Optional[str] = None,
    supporting_images: Optional[List[str]] = None,
    slide_num: int = 19
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=19)

    # 1. Hero Artefact Frame Left
    h_file = hero_image or get_image_asset("image-19-2.png")
    HistoricalImageFrame.render(
        slide,
        x=0.55,
        y=1.72,
        w=4.40,
        h=4.75,
        image_path=h_file,
        caption=hero_caption or "Fig 5.20  The Sarnath Lion Capital (adopted as India's National Emblem)",
        caption_h=0.50
    )

    # 2. Explanatory Card Upper Right
    ParchmentCard.render(
        slide,
        x=5.25,
        y=1.72,
        w=7.53,
        h=2.20,
        title=explanation_title,
        body_bullets=explanation_points,
        fill_color=COLORS.rgb_parchment,
        title_size_pt=15.0,
        body_size_pt=12.5
    )

    # 3. Two Supporting Images Lower Right
    s_imgs = supporting_images or [get_image_asset("image-19-3.png"), get_image_asset("image-19-4.png")]
    sw = 3.65
    sh = 2.25
    s_y = 4.22

    for i in range(min(2, len(s_imgs))):
        sx = 5.25 + i * (sw + 0.23)
        HistoricalImageFrame.render(
            slide,
            x=sx,
            y=s_y,
            w=sw,
            h=sh,
            image_path=s_imgs[i]
        )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E20 — MUSEUM GALLERY
# ====================================================================
def render_e20_museum_gallery(
    slide: Any,
    kicker: str,
    title: str,
    items: List[Tuple[str, str]],  # (image_path, caption) up to 4
    slide_num: int = 20
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=20)

    gw = 2.85
    gh = 4.75
    gap = 0.27
    start_x = 0.55
    start_y = 1.72

    default_artefacts = [
        ("image-20-2.png", "Fig 5.21  Dancing girl"),
        ("image-20-3.png", "Fig 5.22  Mother goddess figurine"),
        ("image-20-4.png", "Fig 5.23  Terracotta cart and bullock"),
        ("image-20-5.png", "Fig 5.24  Toy whistle from Ahichchhatra")
    ]

    gallery_data = items if items else [(get_image_asset(f), c) for f, c in default_artefacts]

    for i in range(min(4, len(gallery_data))):
        img_path, cap = gallery_data[i]
        gx = start_x + i * (gw + gap)
        HistoricalImageFrame.render(
            slide,
            x=gx,
            y=start_y,
            w=gw,
            h=gh,
            image_path=img_path,
            caption=cap,
            caption_h=0.55
        )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E21 — HISTORICAL ERA TIMELINE
# ====================================================================
def render_e21_historical_timeline(
    slide: Any,
    kicker: str,
    title: str,
    eras: List[Tuple[str, str, str]],  # (era_name, dates, description) 3 eras
    slide_num: int = 21
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=21)

    HistoricalTimeline.render(
        slide,
        x=0.55,
        y=1.95,
        w=12.233,
        eras=eras
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E22 — CAUSES + INTERPRETATION
# ====================================================================
def render_e22_causes_interpretation(
    slide: Any,
    kicker: str,
    title: str,
    causes_title: str,
    causes_points: List[str],
    interpretation_title: str,
    interpretation_points: List[str],
    slide_num: int = 22
):
    set_slide_background(slide, COLORS.rgb_canvas)
    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=22)

    # 1. Parchment Causes Panel Left
    ParchmentCard.render(
        slide,
        x=0.55,
        y=1.72,
        w=6.55,
        h=4.75,
        title=causes_title,
        body_bullets=causes_points,
        fill_color=COLORS.rgb_parchment,
        title_size_pt=16.0,
        body_size_pt=13.5
    )

    # 2. Dark Interpretation Panel Right
    DarkInsightCard.render(
        slide,
        x=7.40,
        y=1.72,
        w=5.38,
        h=4.75,
        title=interpretation_title,
        body_text="\n\n".join(interpretation_points),
        title_size_pt=16.0,
        body_size_pt=13.0
    )

    SlideFooter.render(slide, slide_num=slide_num)


# ====================================================================
# E23 — DARK LEGACY / SUMMARY
# ====================================================================
def render_e23_dark_summary(
    slide: Any,
    kicker: str,
    title: str,
    legacy_points: List[str],
    final_takeaway: Optional[str] = None,
    slide_num: int = 23
):
    set_slide_background(slide, COLORS.rgb_canvas_dark)

    # Decorative background circles
    create_solid_shape(slide, MSO_SHAPE.OVAL, 10.5, -1.0, 4.5, 4.5, fill_color=COLORS.rgb_dark_secondary)
    create_solid_shape(slide, MSO_SHAPE.OVAL, -1.5, 4.5, 4.0, 4.0, fill_color=COLORS.rgb_dark_secondary)

    HistoricalSlideHeader.render(slide, kicker=kicker, title=title, slide_idx=23, is_dark=True)

    # Takeaway points
    TakeawayRow.render(
        slide,
        x=0.55,
        y=1.85,
        w=12.233,
        h=3.60,
        items=legacy_points,
        is_dark=True
    )

    # Final Takeaway Card at bottom
    if final_takeaway:
        card = create_solid_shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            0.55,
            5.65,
            12.233,
            0.95,
            fill_color=COLORS.rgb_dark_secondary,
            border_color=None,
            shadow=True
        )
        tb = add_text_box(slide, 0.75, 5.75, 11.833, 0.75)
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = final_takeaway
        p.font.name = FONTS.display
        p.font.size = Pt(14.0)
        p.font.italic = True
        p.font.color.rgb = COLORS.rgb_white
        p.line_spacing = 1.15

    SlideFooter.render(slide, slide_num=slide_num, is_dark=True)
