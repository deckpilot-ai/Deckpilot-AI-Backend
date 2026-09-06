---
name: consulting-pptx-design
description: "Build McKinsey/BCG-style consulting PowerPoint decks for ANY subject matter — business strategy, education/textbook content, product pitches, research summaries, training material, or any topic that needs a polished, professional .pptx. Use this any time the user wants a consulting-grade deck: a topic-tuned dark/gold-style color system, real extracted photos or diagrams where source material exists, icon-driven cards, and a consistent premium layout. Trigger whenever the user asks for a deck, slides, or presentation 'in the usual style' / 'like last time' / 'professional' / 'consulting-style' for this project, or references a prior deck built this way — even if they don't repeat the full spec. This skill defines the visual design system, slide archetypes, image/icon pipeline, and QA bar for every deck in this project, independent of topic. Always read this alongside the base pptx skill, which this skill assumes."
license: Proprietary
---

# Consulting-Style PPTX Design System

Turns any source material — a textbook chapter, a business document, a research summary,
raw notes, or just a topic brief — into a 15-30 slide, consulting-firm-quality `.pptx`. The
visual language stays fixed across every deck in this project; only the color palette
re-tunes per topic. This skill is the accumulated design system from prior decks (spanning
history, civics, and economics educational content so far, but the system itself is
topic-agnostic — the same rules apply to a business strategy deck, a product pitch, or a
training module). It is a companion to, not a replacement for, the base `pptx` skill — read
that one first for pptxgenjs mechanics, then this one for what to actually build.

## Before starting

1. Read `/mnt/skills/public/pptx/SKILL.md` (pptxgenjs gotchas, validate.py, QA loop) if not already in context.
2. Read `references/design-system.md` — the color/type/spacing/component rules every slide must follow, regardless of subject.
3. Read `references/slide-archetypes.md` — the ~12 recurring slide layouts and when to use each.
4. If source material includes a PDF, images, or diagrams worth extracting, read `references/image-pipeline.md` before touching images.
5. Skim `references/qa-checklist.md` so the QA pass at the end isn't a surprise.

Do this even if the request looks like "just make me a deck on X" — the whole point of this
skill is that every deck in the project looks and feels identical in structure while
adapting color and content to whatever the topic is.

## Workflow

1. **Read the source.** Extract the key sections, terms, case studies/examples, figures/tables, and any stats from whatever material was provided (PDF, doc, notes, or a plain topic brief). If a PDF or image source was provided, pull real photos/diagrams per `references/image-pipeline.md` — never substitute AI-generated images for real source photos when real ones exist.
2. **Pick the palette.** Choose one primary (dark, 60-70% weight), one accent (used sparingly for numbers/icons/emphasis), and neutrals, following the rules in `references/design-system.md`. Pick colors that fit *this* deck's subject and tone — do not default to the same palette (e.g. navy/gold) across unrelated decks; see the worked examples in that file for how the same formula produces different palettes per topic.
3. **Outline the deck** as a slide list before writing any code: title → roadmap/agenda/big-questions → the bulk of content slides varying the archetypes in `references/slide-archetypes.md` → key-takeaways/summary → closing. Don't put two consecutive slides on the same archetype (e.g. two icon-grids in a row).
4. **Build with pptxgenjs**, one script, following `references/design-system.md` for every recurring component (eyebrow label, footer breadcrumb, page-number badge, cards, pills, icon circles, image captions, quote blocks, stat callouts). Reuse small helper functions for these — don't hand-roll each slide's footer/eyebrow/page-number from scratch.
5. **Icons**: react-icons → sharp → 256px PNG, per the base pptx skill and `references/image-pipeline.md`'s specific fix for the sharp SVG-string gotcha.
6. **Run the full QA loop** in `references/qa-checklist.md` before delivering: validate.py, markitdown content check (including the em-dash and fabrication checks), and full visual render inspection of every slide.
7. **Deliver** to `/mnt/user-data/outputs` and call `present_files`. Don't ask for confirmation mid-pipeline — this project's established preference is fully autonomous execution end to end.

## Non-negotiable content rules

These have held across every deck built in this project so far — violating any of them is a regression, not a style choice:

- **No em dashes anywhere**, in any text on any slide.
- **No fabricated content** — every fact, figure, quote, and caption must trace back to the source material actually provided. Do not invent stats, examples, or attributions to fill a layout; if a slide needs a number you don't have, ask or leave it out.
- **Real photos/diagrams only when a real source exists** — extract actual images from source material (see `references/image-pipeline.md`) rather than generating a substitute. If no source imagery exists for a topic, generated icons/illustrations are fine for chrome (icon circles, decorative motifs) — just don't fake a "real" photo or figure.
- **Precision over filler** — no AI-sounding hedge phrases, no restating the obvious, no filler transition slides that don't carry content.

## Quick reference: what's in this skill

| File | Read it for |
|---|---|
| `references/design-system.md` | Colors, typography, spacing, and every recurring component's exact spec (positions, fills, sizes) |
| `references/slide-archetypes.md` | The ~12 slide layouts (title, roadmap, two-column, icon-grid, stat callout, comparison, timeline, case study, quote, process flow, dark-panel, closing) and when each fits |
| `references/image-pipeline.md` | Extracting real images from source PDFs when available, plus react-icons+sharp icon generation for UI chrome |
| `references/qa-checklist.md` | The validate.py / markitdown / visual-render loop and the specific defects to check for in this deck style |
