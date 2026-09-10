"""Executable QA checkpoint catalog for presentation generation.

Every checkpoint has a stable ID so repair logic never depends on human-readable
messages. The detector groups in :mod:`qa_agent` evaluate these checks against
the slide plan, source assets, and rendered OpenXML presentation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QACheckpoint:
    id: str
    category: str
    description: str
    repair_action: str
    scope: str = "slide"


_GROUPS: dict[str, list[tuple[str, str, str, str]]] = {
    "content": [
        ("001", "missing_title", "Slide has no meaningful title", "restore_title"),
        ("002", "duplicate_title", "Title duplicates another slide", "differentiate_title"),
        ("003", "title_too_long", "Title exceeds the layout reading budget", "shorten_title"),
        ("004", "title_too_short", "Title is too vague to identify the subject", "clarify_title"),
        ("005", "title_placeholder", "Title contains placeholder copy", "remove_placeholder"),
        ("006", "empty_body", "Content slide has no supporting content", "change_to_divider"),
        ("007", "too_many_bullets", "Bullet count exceeds the layout capacity", "trim_bullets"),
        ("008", "bullet_too_long", "A bullet exceeds the scan-friendly word budget", "shorten_bullets"),
        ("009", "duplicate_bullet", "A slide repeats the same bullet", "dedupe_text"),
        ("010", "near_duplicate_bullet", "A slide repeats substantially similar copy", "dedupe_text"),
        ("011", "duplicate_takeaway", "Takeaway repeats the title or a bullet", "dedupe_text"),
        ("012", "repeated_slide_copy", "Two slides carry substantially identical body copy", "dedupe_text"),
    ],
    "writing": [
        ("013", "placeholder_copy", "Body contains unresolved placeholder copy", "remove_placeholder"),
        ("014", "double_sentence", "A sentence or phrase appears twice in sequence", "dedupe_text"),
        ("015", "repeated_words", "Adjacent words are accidentally duplicated", "dedupe_text"),
        ("016", "excessive_caps", "Body copy uses excessive all-caps text", "normalize_case"),
        ("017", "excessive_punctuation", "Copy contains repeated punctuation", "normalize_punctuation"),
        ("018", "broken_spacing", "Copy contains doubled or malformed whitespace", "normalize_spacing"),
        ("019", "orphan_fragment", "A bullet is an unreadable sentence fragment", "remove_fragment"),
        ("020", "boilerplate_lead", "Lead-in wording repeats across too many slides", "vary_structure"),
        ("021", "speaker_note_leak", "Presenter instructions leaked onto the slide", "remove_note_leak"),
        ("022", "citation_incomplete", "A visible citation is incomplete", "move_citation_to_notes"),
        ("023", "unsupported_superlative", "Copy uses an unsupported absolute claim", "soften_claim"),
        ("024", "encoding_artifact", "Copy contains mojibake or replacement characters", "repair_encoding"),
    ],
    "typography": [
        ("025", "body_font_too_small", "Rendered body text is below the readable floor", "increase_font"),
        ("026", "title_font_too_small", "Rendered title text lacks sufficient scale", "increase_font"),
        ("027", "caption_font_too_small", "Caption text is below the caption floor", "increase_font"),
        ("028", "footer_font_too_small", "Footer text is below the footer floor", "increase_font"),
        ("029", "inconsistent_body_size", "Body font sizes vary without purpose", "normalize_font"),
        ("030", "inconsistent_title_size", "Title sizes vary without layout justification", "normalize_font"),
        ("031", "too_many_fonts", "Slide uses too many font families", "normalize_font_family"),
        ("032", "unsafe_font", "Slide uses a font without a reliable Office fallback", "normalize_font_family"),
        ("033", "missing_hierarchy", "Body copy has no visible information hierarchy", "add_hierarchy"),
        ("034", "overbold_body", "Too much body copy is bold", "reduce_bold"),
        ("035", "underemphasized_key_metric", "Key metric lacks visual emphasis", "emphasize_metric"),
        ("036", "line_density_high", "Text lines are too dense for presentation reading", "shorten_bullets"),
    ],
    "geometry": [
        ("037", "off_canvas", "A shape extends outside the slide canvas", "constrain_bounds"),
        ("038", "text_overflow", "Text exceeds its text box", "shorten_and_reflow"),
        ("039", "text_clipping", "Text is clipped at a box edge", "shorten_and_reflow"),
        ("040", "shape_overlap", "Unrelated shapes overlap", "resolve_overlap"),
        ("041", "text_image_overlap", "Text overlaps an image", "resolve_overlap"),
        ("042", "footer_collision", "Content collides with the footer zone", "constrain_bounds"),
        ("043", "page_number_collision", "Content collides with the page number", "constrain_bounds"),
        ("044", "margin_violation", "Content violates safe page margins", "constrain_bounds"),
        ("045", "misaligned_columns", "Columns do not share consistent guides", "align_columns"),
        ("046", "uneven_gutters", "Repeated elements use uneven spacing", "normalize_gutters"),
        ("047", "tiny_shape", "A meaningful object is too small to read", "enlarge_object"),
        ("048", "aspect_ratio_distortion", "Image geometry distorts its source ratio", "restore_aspect_ratio"),
    ],
    "whitespace": [
        ("049", "excessive_blank_space", "Content occupies too little of the usable canvas", "expand_layout"),
        ("050", "blank_left_half", "The left side is unintentionally empty", "rebalance_layout"),
        ("051", "blank_right_half", "The right side is unintentionally empty", "rebalance_layout"),
        ("052", "blank_top_band", "The upper content band is unintentionally empty", "rebalance_layout"),
        ("053", "blank_bottom_band", "The lower content band is unintentionally empty", "rebalance_layout"),
        ("054", "unbalanced_visual_weight", "Visual weight is strongly skewed", "rebalance_layout"),
        ("055", "content_clustered_corner", "Content is clustered into one corner", "expand_layout"),
        ("056", "orphan_object", "A single object is visually disconnected", "rebalance_layout"),
        ("057", "excessive_card_padding", "Cards contain disproportionate internal whitespace", "reduce_padding"),
        ("058", "excessive_title_gap", "Gap between title and content is too large", "rebalance_layout"),
        ("059", "sparse_slide", "A non-divider slide contains too little information", "use_compact_layout"),
        ("060", "crowded_slide", "Canvas density is too high", "simplify_layout"),
    ],
    "images": [
        ("061", "image_semantic_mismatch", "Image is not relevant to the slide subject", "rematch_image"),
        ("062", "duplicate_image_id", "The same source image is assigned more than once", "replace_duplicate_image"),
        ("063", "duplicate_image_pixels", "Rendered image pixels repeat across slides", "replace_duplicate_image"),
        ("064", "near_duplicate_image", "Visually near-identical images repeat", "replace_duplicate_image"),
        ("065", "unused_relevant_image", "A more relevant unused image is available", "rematch_image"),
        ("066", "missing_required_image", "Image-led layout has no renderable image", "change_layout"),
        ("067", "low_resolution_image", "Image resolution is insufficient for its display size", "replace_or_shrink_image"),
        ("068", "blurry_image", "Image sharpness is below the quality threshold", "replace_image"),
        ("069", "extreme_crop", "Crop removes too much of the source image", "restore_crop"),
        ("070", "stretched_image", "Image is stretched rather than cropped proportionally", "restore_aspect_ratio"),
        ("071", "missing_image_caption", "Documentary image lacks a meaningful caption", "add_caption"),
        ("072", "generic_image_caption", "Image caption is generic and cannot establish relevance", "improve_caption"),
    ],
    "visuals": [
        ("073", "no_visuals", "Deck has no supporting visual evidence", "assign_visuals"),
        ("074", "sparse_visual_pacing", "Visuals are too infrequent across the deck", "assign_visuals"),
        ("075", "visuals_overused", "Too many slides rely on image-led layouts", "change_layout"),
        ("076", "consecutive_image_layouts", "Image-led layouts repeat too many times", "vary_layout"),
        ("077", "consecutive_same_layout", "The same layout repeats too many times", "vary_layout"),
        ("078", "layout_content_mismatch", "Layout family does not match its content", "change_layout"),
        ("079", "chart_missing_for_numeric_story", "Numeric comparison lacks a suitable visual", "route_to_chart"),
        ("080", "table_missing_for_matrix", "Matrix-like evidence lacks a table", "route_to_table"),
        ("081", "diagram_missing_for_process", "Process content lacks a process layout", "route_to_process"),
        ("082", "decorative_overload", "Decoration competes with slide content", "reduce_decoration"),
        ("083", "inconsistent_icon_style", "Icon treatment changes without purpose", "normalize_icons"),
        ("084", "missing_page_number", "Slide lacks its page marker", "restore_page_number"),
    ],
    "color": [
        ("085", "low_text_contrast", "Text contrast is below accessibility guidance", "increase_contrast"),
        ("086", "low_icon_contrast", "Icon contrast is too low", "increase_contrast"),
        ("087", "low_chart_contrast", "Chart series are hard to distinguish", "increase_chart_contrast"),
        ("088", "color_overload", "Slide uses too many unrelated colors", "normalize_palette"),
        ("089", "background_inconsistency", "Background treatment breaks deck consistency", "normalize_background"),
        ("090", "dark_slide_readability", "Dark slide contains unreadable secondary text", "increase_contrast"),
        ("091", "accent_overuse", "Accent color is applied too broadly", "reduce_accent"),
        ("092", "alert_color_misuse", "Alert color is used without negative meaning", "normalize_palette"),
        ("093", "transparent_text", "Text transparency reduces legibility", "increase_contrast"),
        ("094", "chart_palette_repetition", "Adjacent series use indistinguishable colors", "increase_chart_contrast"),
        ("095", "link_color_inconsistency", "Links use inconsistent styling", "normalize_palette"),
        ("096", "grayscale_failure", "Meaning depends on color alone", "add_direct_labels"),
    ],
    "data": [
        ("097", "chart_missing_categories", "Chart has no categories", "remove_invalid_chart"),
        ("098", "chart_missing_series", "Chart has no data series", "remove_invalid_chart"),
        ("099", "chart_length_mismatch", "Chart series length differs from category count", "align_chart_data"),
        ("100", "chart_non_numeric_value", "Chart contains a non-numeric value", "remove_invalid_chart"),
        ("101", "chart_missing_source", "Chart lacks source provenance", "flag_source_needed"),
        ("102", "chart_missing_units", "Chart values lack units", "infer_or_flag_units"),
        ("103", "table_missing_headers", "Table has no column headers", "remove_invalid_table"),
        ("104", "table_ragged_rows", "Table rows have inconsistent column counts", "align_table_rows"),
        ("105", "table_too_wide", "Table has too many columns for the canvas", "simplify_table"),
        ("106", "table_too_long", "Table has too many rows for a slide", "simplify_table"),
        ("107", "metric_duplicate", "Metric is repeated on the same slide", "dedupe_metrics"),
        ("108", "metric_missing_label", "Metric value has no explanatory label", "remove_invalid_metric"),
    ],
    "technical": [
        ("109", "pptx_corrupt", "Presentation package cannot be reopened", "rerender_deck", "deck"),
        ("110", "slide_count_mismatch", "Rendered slide count differs from the plan", "rerender_deck", "deck"),
        ("111", "missing_media_relationship", "An image relationship is broken", "remove_broken_media"),
        ("112", "missing_notes", "Slide lacks speaker notes", "restore_notes"),
        ("113", "duplicate_slide_id", "Slide plan contains duplicate identifiers", "renumber_slides", "deck"),
        ("114", "slide_number_gap", "Slide numbers are not contiguous", "renumber_slides", "deck"),
        ("115", "invalid_layout_enum", "Slide references an unsupported layout", "change_layout"),
        ("116", "empty_shape", "Rendered slide contains an empty content shape", "remove_empty_shape"),
        ("117", "hidden_content", "A hidden object contains required content", "restore_hidden_content"),
        ("118", "unsupported_font", "Embedded font choice may substitute unpredictably", "normalize_font_family"),
        ("119", "missing_alt_caption", "Meaningful image lacks descriptive metadata", "add_caption"),
        ("120", "unresolved_repair", "A high-severity issue remains after repair", "fallback_safe_layout", "deck"),
    ],
}


CHECKPOINTS: tuple[QACheckpoint, ...] = tuple(
    QACheckpoint(f"QA-{number}", category, description, action, scope)
    for category, rows in _GROUPS.items()
    for number, _slug, description, action, *optional_scope in rows
    for scope in [optional_scope[0] if optional_scope else "slide"]
)

CHECKPOINT_BY_ID = {checkpoint.id: checkpoint for checkpoint in CHECKPOINTS}
CHECKPOINT_ID_BY_SLUG = {
    slug: f"QA-{number}"
    for rows in _GROUPS.values()
    for number, slug, _description, _action, *_scope in rows
}


def checkpoint_ids() -> list[str]:
    """Return the stable ordered list recorded in every QA report."""
    return [checkpoint.id for checkpoint in CHECKPOINTS]

