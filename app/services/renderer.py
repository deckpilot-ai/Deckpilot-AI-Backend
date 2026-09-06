"""Consulting-style native PowerPoint rendering with shared, bounded components."""

import io
import math
import re
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from app.services.design_system import clean_text, normalize_brand


def hex_to_rgb(value: str) -> RGBColor:
    value = value.lstrip('#')
    try:
        return RGBColor.from_string(value.upper())
    except ValueError:
        return RGBColor(19, 42, 82)


def tint(color: RGBColor, amount: float) -> RGBColor:
    return RGBColor(*(round(c + (255 - c) * amount) for c in color))


class PPTXRenderer:
    SLIDE_WIDTH = Inches(13.333)
    SLIDE_HEIGHT = Inches(7.5)

    @staticmethod
    def _fits(text, w, h, size=13, bullet_list=False):
        return PPTXRenderer._height(text, w, size, bullet_list) - .02 <= h

    @staticmethod
    def _shape(slide, kind, x, y, w, h, color, name='card'):
        shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.name = name
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        shape.shadow.inherit = False
        if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
            shape.adjustments[0] = .08
        return shape

    @staticmethod
    def _height(text, width, size=16, bullet_list=False):
        capacity = max(1, int((width - .04 - (.23 if bullet_list else 0)) * 72 / (size * .56)))
        paragraphs = clean_text(text).split('\n')
        lines = sum(max(1, math.ceil(len(line) / capacity)) for line in paragraphs)
        spacing = max(0, len(paragraphs) - 1) * 5 if bullet_list else 0
        return (lines * size * 1.25 + spacing) / 72 + .06

    @staticmethod
    def _picture(slide, payload, x, y, w, h):
        from PIL import Image
        with Image.open(io.BytesIO(payload)) as source:
            ratio = min(w / source.width, h / source.height)
            pw, ph = source.width * ratio, source.height * ratio
        slide.shapes.add_picture(io.BytesIO(payload), Inches(x + (w - pw) / 2),
                                 Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))

    @staticmethod
    def _text(slide, text, x, y, w, h, color, size=14, title=False, bold=False, center=False, italic=False,
              bullet_list=False):
        text = clean_text(text)
        if bullet_list:
            text = '\n'.join(re.sub(r'^\s*[•●▪]\s*', '', line) for line in text.split('\n'))
        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        shape.name = 'content-text'
        frame = shape.text_frame
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = Inches(0.02)
        frame.margin_top = frame.margin_bottom = Inches(0.02)
        # Conservative width/line budgeting. Fail instead of clipping oversized copy.
        floor = 28 if title and size >= 28 else min(size, 13)
        while True:
            if PPTXRenderer._fits(text, w, h, size, bullet_list):
                break
            if size <= floor:
                raise ValueError('Slide text exceeds its layout budget; shorten the source copy and regenerate')
            size -= 1
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE if center else MSO_ANCHOR.TOP
        for i, line in enumerate(text.split('\n')):
            p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            p.text = line
            p.font.name = 'Cambria' if title else 'Calibri'
            p.font.size = Pt(size)
            p.font.bold = bold or title
            p.font.italic = italic
            p.font.color.rgb = color
            p.alignment = PP_ALIGN.CENTER if center else PP_ALIGN.LEFT
            if bullet_list:
                # Native bullets keep wrapped lines aligned with their point's text.
                properties = p._p.get_or_add_pPr()
                properties.set('marL', str(Inches(.23)))
                properties.set('indent', str(-Inches(.18)))
                marker = OxmlElement('a:buChar')
                marker.set('char', '•')
                properties.append(marker)
                p.space_after = Pt(5 if i < len(text.split('\n')) - 1 else 0)
                p.line_spacing = 1.15
            if not title and not center and ':' in line and len(line.split(':', 1)[0]) < 55:
                lead, remainder = line.split(':', 1)
                p.clear()
                p.add_run().text = lead + ':'
                p.runs[0].font.bold = True
                p.add_run().text = remainder
        return shape

    @classmethod
    def _card(cls, slide, text, x, y, w, h, fill, foreground, accent, number=None):
        bullet_list = '\n' in text
        text_x, text_w = x + .25, w - .5
        if number is not None:
            text_x, text_w = x + .8, w - 1.05
        size = 16
        while size > 13 and not cls._fits(text, text_w, h - .4, size, bullet_list):
            size -= 1
        h = min(h, max(.85, cls._height(text, text_w, size, bullet_list) + .4))
        cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill)
        if number is not None:
            cls._shape(slide, MSO_SHAPE.OVAL, x + .2, y + .25, .4, .4, accent)
            cls._text(slide, str(number), x + .2, y + .25, .4, .4, RGBColor(255, 255, 255), 11, bold=True, center=True)
            text_x, text_w = x + .8, w - 1.05
        cls._text(slide, text, text_x, y + .2, text_w, h - .4, foreground, size, bullet_list=bullet_list)

    @classmethod
    def render_deck(cls, deck_spec: dict[str, Any], brand_style: dict[str, Any] | None = None,
                    source_images: dict[str, bytes] | None = None) -> bytes:
        prs = Presentation()
        prs.slide_width, prs.slide_height = cls.SLIDE_WIDTH, cls.SLIDE_HEIGHT
        brand = normalize_brand(brand_style or deck_spec.get('brandStyle'), deck_spec.get('deckTitle', ''))
        subject = brand['subject']
        primary = hex_to_rgb(brand['colors']['primary'])
        accent = hex_to_rgb(brand['colors']['accent'])
        neutral = tint(primary, 0.94)
        white = RGBColor(255, 255, 255)
        paper = RGBColor(252, 249, 244) if subject == 'history' else white
        slides = deck_spec.get('slides', [])
        if not slides:
            raise ValueError('A presentation must contain at least one slide')
        for index, data in enumerate(slides):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            layout = data.get('layoutHint', 'two_column')
            dark = layout in ('closing', 'dark_panel', 'legacy', 'dark_quote') or (layout in ('hero', 'title') and subject != 'markets')
            foreground = white if dark else primary
            body = tint(primary, 0.84) if dark else primary
            fill = tint(primary, 0.14) if dark else neutral
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = primary if dark else paper
            image = (source_images or {}).get(data.get('imageArtifactId', ''))
            purpose = clean_text(data.get('purpose', ''))
            title = clean_text(data.get('headline') or data.get('message') or purpose)
            bullets = [clean_text(b) for b in data.get('bullets', []) if isinstance(b, str) and b.strip()]
            limit = 8 if layout in ('diagram_hierarchy', 'saptanga', 'hierarchy') else 6
            if len(bullets) > limit:
                raise ValueError(f'Use at most {limit} concise content items per slide')
            if (layout in ('editorial', 'roadmap', 'takeaways', 'hierarchy', 'timeline', 'process_steps')
                    and sum(cls._height(b, 10.8, 13) + .18 for b in bullets) > 3.85):
                layout = 'comparison'
            subject_label = {'history': 'HISTORY', 'governance': 'CIVICS & GOVERNANCE',
                             'markets': 'ECONOMICS', 'sustainability': 'ENVIRONMENT'}.get(subject, subject.upper())
            eyebrow = clean_text(data.get('eyebrow') or data.get('chapter') or subject_label).upper()
            if layout not in ('hero', 'title'):
                cls._text(slide, eyebrow, .6, .5, 12.1, .32, body, 12.5)
            footer = f"{deck_spec.get('deckTitle', 'Presentation')} - {data.get('chapter') or subject_label}".upper()
            # Footer can be long without losing the full source context in notes.
            cls._text(slide, footer[:140], .6, 6.62, 11.15, .28, body, 9)
            cls._shape(slide, MSO_SHAPE.OVAL, 12.3, 6.52, .4, .4, white if dark else primary, 'page-badge')
            cls._text(slide, str(index + 1), 12.3, 6.52, .4, .4, primary if dark else white, 10, bold=True, center=True)
            if layout in ('hero', 'title'):
                if image:
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, .6, 1.1, 4.2, .38, tint(primary, 0.25), 'kicker-pill')
                    cls._text(slide, eyebrow, .7, 1.13, 4.0, .32, accent, 11.5, bold=True)
                    cls._text(slide, title, .6, 1.65, 5.9, 1.85, foreground, 34, title=True)
                    cls._shape(slide, MSO_SHAPE.RECTANGLE, .6, 3.62, 1.8, .07, accent, 'accent-rule')
                    cls._text(slide, data.get('takeaway') or '', .6, 3.82, 5.9, .85, body, 15)
                    if bullets:
                        cls._text(slide, '\n'.join(bullets), .6, 4.75, 5.9, 1.7, body, 13, bullet_list=True)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.85, 1.1, 5.85, 5.35, white, 'hero-frame')
                    cls._picture(slide, image, 7.0, 1.25, 5.55, 4.35)
                    caption = clean_text(data.get('imageCaption') or 'Source document illustration')
                    if len(caption) > 85:
                        caption = caption[:82].rsplit(' ', 1)[0] + '…'
                    cls._text(slide, caption, 7.0, 5.75, 5.55, .55, primary, 10, italic=True, center=True)
                else:
                    cls._text(slide, title, .6, 1.1, 12.1, 1.65, foreground, 36, title=True)
                    cls._text(slide, data.get('takeaway') or '', .6, 2.95, 12.1, .65, body, 16)
                    midpoint = max(1, math.ceil(len(bullets) / 2))
                    for j, group in enumerate((bullets[:midpoint], bullets[midpoint:])):
                        if group:
                            cls._card(slide, '\n'.join(group), .6 + j * 6.225, 3.75, 5.875, 2.55, fill, body, accent)
            elif layout in ('closing', 'legacy'):
                cls._text(slide, title, .6, 1.05, 12.1, 1.1, foreground, 32, title=True)
                takeaway = data.get('takeaway') or ''
                if takeaway:
                    cls._text(slide, takeaway, .6, 1.95, 12.1, .65, body, 14)
                cls._text(slide, '\n'.join(bullets), .6, 2.7, 7.0, 3.65, body, 14, bullet_list=True)
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.95, 2.7, 4.75, 3.65, tint(primary, 0.22), 'card')
                cls._shape(slide, MSO_SHAPE.OVAL, 9.8, 2.95, 1.0, 1.0, accent, 'emblem-disc')
                cls._text(slide, "★", 9.8, 2.95, 1.0, 1.0, white, 22, bold=True, center=True)
                quote_text = data.get('quote', {}).get('text') if isinstance(data.get('quote'), dict) else None
                motto = quote_text or "Satyameva Jayate\nTruth Alone Triumphs"
                cls._text(slide, motto, 8.15, 4.15, 4.35, 1.9, white, 16, bold=True, center=True, italic=True)
            elif layout == 'big_questions':
                cls._text(slide, title, .6, 1.02, 12.1, 1.1, foreground, 30, title=True)
                count = min(len(bullets), 4) or 1
                card_w = (12.1 - .35 * (count - 1)) / count
                for j, item in enumerate(bullets[:count]):
                    x_card = .6 + j * (card_w + .35)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x_card, 2.25, card_w, 4.15, fill, 'card')
                    cls._shape(slide, MSO_SHAPE.OVAL, x_card + .25, 2.45, .55, .55, accent, 'badge')
                    cls._text(slide, f"{j+1:02d}", x_card + .25, 2.45, .55, .55, white, 13, bold=True, center=True)
                    cls._text(slide, item, x_card + .25, 3.15, card_w - .5, 3.1, foreground, 14, bullet_list=('\n' in item))
            elif layout == 'timeline_columns':
                cls._text(slide, title, .6, 1.02, 12.1, 1.1, foreground, 30, title=True)
                col_count = min(len(bullets), 3) or 1
                col_width = (12.1 - .35 * (col_count - 1)) / col_count
                for j, item in enumerate(bullets[:col_count]):
                    x_col = .6 + j * (col_width + .35)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x_col, 2.25, col_width, 4.15, fill, 'card')
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x_col, 2.25, col_width, .75, primary if not dark else tint(primary, 0.25), 'card-header')
                    lines = item.split('\n')
                    header_line = lines[0] if lines else f"Era {j+1}"
                    body_lines = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                    cls._text(slide, header_line, x_col + .15, 2.35, col_width - .3, .55, white, 14, bold=True, center=True)
                    if body_lines:
                        cls._text(slide, body_lines, x_col + .2, 3.15, col_width - .4, 3.1, foreground, 13, bullet_list=True)
                    else:
                        cls._text(slide, item, x_col + .2, 3.15, col_width - .4, 3.1, foreground, 13)
            elif layout in ('diagram_hierarchy', 'saptanga'):
                cls._text(slide, title, .6, 1.02, 12.1, 1.1, foreground, 30, title=True)
                cx, cy, cw, ch = 4.85, 3.4, 3.6, 1.5
                cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, cx, cy, cw, ch, accent, 'center-hub')
                center_label = bullets[0] if bullets else "Sovereign State Core"
                cls._text(slide, center_label, cx + .1, cy + .1, cw - .2, ch - .2, white, 13, bold=True, center=True)
                flank_items = bullets[1:] if len(bullets) > 1 else bullets
                left_items = flank_items[:3]
                right_items = flank_items[3:6]
                for j, item in enumerate(left_items):
                    y_card = 2.25 + j * 1.4
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, .6, y_card, 3.9, 1.2, fill, 'card')
                    cls._text(slide, item, .75, y_card + .12, 3.6, .96, foreground, 12.5)
                    cls._shape(slide, MSO_SHAPE.RECTANGLE, 4.5, y_card + .58, .35, .025, accent, 'connector')
                for j, item in enumerate(right_items):
                    y_card = 2.25 + j * 1.4
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 8.8, y_card, 3.9, 1.2, fill, 'card')
                    cls._text(slide, item, 8.95, y_card + .12, 3.6, .96, foreground, 12.5)
                    cls._shape(slide, MSO_SHAPE.RECTANGLE, 8.45, y_card + .58, .35, .025, accent, 'connector')
            else:
                cls._text(slide, title, .6, 1.02, 12.1, 1.1, foreground, 30, title=True)
                metrics = data.get('metrics') or []
                quote = data.get('quote')
                chart_matches = [re.fullmatch(r'(\d[\d,]*(?:\.\d+)?)(%?)', str(m.get('value', ''))) for m in metrics]
                if layout == 'bar_chart' and (not metrics or not all(chart_matches)
                                             or len({m.group(2) for m in chart_matches if m}) != 1):
                    layout = 'metrics_grid'
                if layout == 'bar_chart':
                    values = [float(m.group(1).replace(',', '')) for m in chart_matches if m]
                    maximum = max(values) or 1
                    for j, (metric, value) in enumerate(zip(metrics, values)):
                        y = 2.45 + j * .82
                        cls._text(slide, metric['label'], .6, y, 3.2, .65, body, 15)
                        cls._shape(slide, MSO_SHAPE.RECTANGLE, 4.05, y + .05, max(.015, value / maximum * 6.6), .4, accent, 'data-bar')
                        cls._text(slide, metric['value'], 10.95, y, 1.75, .65, foreground, 16, bold=True)
                elif layout in ('metrics_grid', 'chart', 'metrics') and metrics:
                    width = (12.1 - .35 * (len(metrics) - 1)) / len(metrics)
                    for j, metric in enumerate(metrics[:4]):
                        x = .6 + j * (width + .35)
                        cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.4, width, 3.0, fill)
                        cls._text(slide, metric['value'], x + .2, 2.85, width - .4, 1.15, foreground, 40, bold=True, center=True)
                        cls._text(slide, metric['label'], x + .2, 4.3, width - .4, .75, body, 13, center=True)
                elif layout == 'dark_quote' or (layout == 'quote' and (dark or isinstance(quote, dict))):
                    quote_dict = quote if isinstance(quote, dict) else {}
                    q_text = quote_dict.get('text', '') or (bullets[0] if bullets else '')
                    q_attr = quote_dict.get('attribution', '') or (bullets[1] if len(bullets) > 1 else '')
                    if dark or layout == 'dark_quote':
                        cls._text(slide, "“", .6, 2.1, 1.2, .8, accent, 44, bold=True)
                        cls._text(slide, f'"{clean_text(q_text)}"', .6, 2.75, 6.2, 2.5, foreground, 19, title=True, italic=True)
                        if q_attr:
                            cls._text(slide, f"— {clean_text(q_attr)}", .6, 5.35, 6.2, .45, accent, 13.5, bold=True)
                        other_bullets = bullets[2:] if not isinstance(quote, dict) else bullets
                        if other_bullets:
                            cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.15, 2.25, 5.55, 4.0, fill, 'card')
                            cls._text(slide, "Historical Context & Philosophy", 7.4, 2.45, 5.0, .4, foreground, 16, bold=True)
                            cls._text(slide, '\n'.join(other_bullets), 7.4, 2.95, 5.0, 3.1, body, 14, bullet_list=True)
                    else:
                        cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, .6, 2.35, 12.1, 3.5, fill)
                        cls._text(slide, q_text, 1, 2.8, 11.3, 2, foreground, 18, title=True, italic=True)
                        cls._text(slide, q_attr, 1, 5.2, 11.3, .4, body, 13)
                elif image:
                    cls._text(slide, '\n'.join(bullets), .6, 2.25, 5.85, 4.15, body, 15, bullet_list=True)
                    cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.75, 2.2, 5.95, 4.25, white, 'image-frame')
                    cls._picture(slide, image, 6.85, 2.3, 5.75, 3.45)
                    caption = clean_text(data.get('imageCaption') or 'Source document image')
                    if not re.match(r'^(?:Fig|Figure|Map)\b', caption, re.IGNORECASE):
                        caption = f"Fig. {index + 1} - {caption}"
                    if len(caption) > 95:
                        caption = caption[:92].rsplit(' ', 1)[0] + '…'
                    cls._text(slide, caption, 6.85, 5.85, 5.75, .5, primary, 10.5, italic=True, center=True)
                elif layout in ('editorial', 'roadmap', 'takeaways', 'hierarchy'):
                    y = 2.35
                    size = 16
                    while size > 13 and sum(cls._height(b, 10.9, size) + .15 for b in bullets) > 3.85:
                        size -= 1
                    for j, item in enumerate(bullets):
                        if layout != 'editorial':
                            item = re.sub(r'^\s*\d+[.)]\s*', '', item)
                        h = cls._height(item, 10.9, size)
                        if layout == 'hierarchy':
                            cls._shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, .6, y, 12.1, h + .1, fill)
                        cls._text(slide, f'{j+1:02}' if layout != 'editorial' else '•', .7, y, .65, .4, accent, 16, bold=True)
                        cls._text(slide, item, 1.6, y, 10.9, h, body, size)
                        y += h + .15
                elif layout in ('timeline', 'process_steps'):
                    # Timeline dates and process labels stay in their source text;
                    # connectors convey sequence without fabricated milestones.
                    y = 2.35
                    size = 16
                    while size > 13 and sum(cls._height(b, 10.8, size) + .18 for b in bullets) > 3.85:
                        size -= 1
                    for j, item in enumerate(bullets):
                        h = cls._height(item, 10.8, size)
                        cls._shape(slide, MSO_SHAPE.OVAL, .75, y + .03, .28, .28, accent, 'sequence-node')
                        if j < len(bullets) - 1:
                            cls._shape(slide, MSO_SHAPE.RECTANGLE, .875, y + .31, .025, max(.05, h - .13), accent, 'sequence-link')
                        cls._text(slide, item, 1.6, y, 10.8, h, body, size)
                        y += h + .18
                elif layout in ('two_column', 'concept', 'case_study', 'comparison'):
                    if layout == 'comparison':
                        midpoint = max(1, math.ceil(len(bullets) / 2))
                        groups = [bullets[:midpoint], bullets[midpoint:]]
                    else:
                        midpoint = max(1, math.ceil(len(bullets) / 2))
                        groups = [bullets[:midpoint], bullets[midpoint:]]
                    for j, group in enumerate(groups):
                        cls._card(slide, '\n'.join(group), .6 + j * 6.225, 2.25, 5.875, 4.0, fill, body, accent)
                else:
                    items = bullets or ([data['takeaway']] if data.get('takeaway') else [])
                    count = len(items)
                    columns = (2 if count == 4 else min(count, 3)) or 1
                    rows = math.ceil(count / columns) or 1
                    height = (3.65 - .35 * (rows - 1)) / rows
                    width = (12.1 - .35 * (columns - 1)) / columns
                    numbered = layout in ('roadmap', 'timeline', 'process_steps')
                    if any(not cls._fits(item, width - (1.05 if numbered else .5), height - .5) for item in items):
                        # Reflow dense source copy into two tall panels without
                        # truncating it or reducing body text below 13 points.
                        midpoint = min(range(1, count), key=lambda n: abs(sum(map(len, items[:n])) - sum(map(len, items[n:])))) if count > 1 else 1
                        groups = [items[:midpoint], items[midpoint:]]
                        for j, group in enumerate(groups):
                            cls._card(slide, '\n'.join(group), .6 + j * 6.225, 2.25, 5.875, 4.0, fill, body, accent)
                        items = []
                    for j, item in enumerate(items):
                        x, y = .6 + (j % columns) * (width + .35), 2.4 + (j // columns) * (height + .35)
                        numbered = layout in ('roadmap', 'timeline', 'process_steps')
                        cls._card(slide, item, x, y, width, height, fill, body, primary, j + 1 if numbered else None)
                        if layout == 'process_steps' and j % columns < columns - 1 and j + 1 < count:
                            cls._shape(slide, MSO_SHAPE.CHEVRON, x + width + .07, y + height / 2, .21, .25, accent, 'connector')
            notes = clean_text(data.get('speakerNotes') or data.get('speaker_notes'))
            sources = [m.get('sourceQuote', '') for m in data.get('metrics', [])]
            if isinstance(data.get('quote'), dict):
                sources.append(data['quote'].get('sourceQuote', ''))
            slide.notes_slide.notes_text_frame.text = '\n'.join([notes, *sources]).strip()
        output = io.BytesIO()
        prs.save(output)
        return output.getvalue()

    @classmethod
    def validate_deck(cls, payload: bytes, expected_slides: int) -> dict[str, Any]:
        prs = Presentation(io.BytesIO(payload))
        errors = []
        if len(prs.slides) != expected_slides:
            errors.append('Unexpected slide count')
        for index, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                if shape.left < 0 or shape.top < 0 or shape.left + shape.width > prs.slide_width or shape.top + shape.height > prs.slide_height:
                    errors.append(f'Slide {index + 1}: shape outside canvas')
                text = shape.text if shape.has_text_frame else ''
                if '\u2014' in text or any(marker in text.lower() for marker in ('lorem ipsum', '[insert', 'todo:')):
                    errors.append(f'Slide {index + 1}: prohibited text')
        if errors:
            raise ValueError('; '.join(errors))
        return {'status': 'passed', 'checks': ['pptx_reopen', 'slide_count', 'canvas_bounds', 'text_markers'],
                'visualInspection': 'not_performed', 'slides': len(prs.slides)}

