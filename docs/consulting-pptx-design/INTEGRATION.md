# Consulting deck generation

The backend integrates `consulting-pptx-design/1.0` in `app/services/design_system.py`.
The original supplied skill is archived alongside this file. Only presentation
planning, writing and brand selection receive the design contract; chat/Ask mode
retain their own prompts. Rendering remains deterministic Python/native PPTX.

## Implemented

- Cambria titles, Calibri body, widescreen canvas, reusable cards, eyebrows,
  footer breadcrumbs, page badges, dark title/closing and varied layouts.
- Topic-aware palettes; the app's blue UI does not dictate slide colors.
- Source-excerpt checks for explicit metric and quote objects, speaker notes,
  no em dashes, and no hard-coded demo statistics or timelines.
- Image artifact IDs resolve only against the current project's source assets.
  PDF images receive per-image RGB conversion and soft-mask composition.
- Full text grounding with duplicate reference removal, five-slide writer batches,
  requested slide-count checks, and failure for omitted writer content.
- File and geometry checks run before a ready deck version is published.
- Actual provider failures cannot silently become AI-generated offline outlines.

## Practical limits

Exact excerpt checks establish provenance for structured stats and quotes; they
are not semantic proof of every sentence. Review historical interpretation and
source citations before presenting. No documentary image is generated as a
substitute for missing evidence. Unavailable source images use text layouts.

Automated QA currently checks package reopening, slide count, canvas bounds and
placeholder/em-dash text; text boxes have a conservative fit budget. The saved
`qaReport.visualInspection` is `not_performed` unless a separate visual review is
conducted. It must never be presented as a complete visual inspection.

The supplied skill's pptxgenjs/React/sharp commands, sandbox paths, and delivery
commands are not run in this Python application. Native shapes replace icon PNG
chrome where applicable. Full slide-image rendering, automatic factual entailment,
and all of the reference skill's optional image/icon treatments are not claimed.

## Configuration

`GEMINI_MODEL` selects the Gemini OpenAI-compatible model (default:
`gemini-3.6-flash`, verified against the configured provider during the live test).
`LLM_READ_TIMEOUT_SECONDS` controls generation read timeouts (default 120).
Provider accounts still need valid credentials and sufficient quota.

## Subject-aware architecture (September 2026)

The renderer now supports unboxed editorial pages, compact roadmaps, real sequence
layouts, institutional tiers, image-led explanations and source-backed bar charts.
The AI selects these by subject and content rather than alternating two generic
card templates. History uses warm paper and dark illustrated openings; civics uses
teal institutional treatments; economics can use a light opening and data layouts.
Opening and closing roles are enforced without changing the requested slide count.
Closing pages use unboxed synthesis instead of repeating the opening's cards.

Cards size to their copy, with body text up to 16 pt and a 13 pt lower fit limit.
Default theme shadows and oversized corner radii are removed. Source bullet lead-ins
are emphasized. Oversized copy still fails validation rather than silently clipping.

PDF ingestion ignores full-page background assets, blank masks and QR codes.
Visible figure crops retain printed map labels and vector annotations, and nearby
source text supplies caption context. Standalone raster uploads are EXIF-oriented
and normalized to PNG. Figures retain their aspect ratio. Captions are source
context, not model-generated descriptions or claims of visual recognition.

Reference decks reviewed: The Rise of Empires, Development, The Rise of the Marathas,
Federalism and Understanding Markets. The two supplied Empires versions are duplicates.
Test PDFs: gees105 (1).pdf (34 pages), hees106 (1).pdf (24 pages), hees107.pdf (32 pages).

Re-export (`mode: export`) reuses the latest ready deck's written content and applies
current rendering rules, without calling the planner or writer. A single separately
uploaded image is used on the opening slide. Selected PDF figures are revalidated
against the original PDF so previously cached page backgrounds are excluded too.
Extracted asset storage keys now include the project and source-file hash.
