# QA Checklist

Run this full loop before delivering any deck. This mirrors the base pptx skill's QA
section, plus the checks specific to this project's content rules and recurring
components.

## 1. File QA

```bash
python scripts/office/validate.py output.pptx
```

(paths relative to `/mnt/skills/public/pptx/`). Fix every reported issue in the generator
script and rebuild — never hand-edit the packed XML to patch around a validator failure.

## 2. Content QA

```bash
markitdown output.pptx
```

Read the full text dump and check:

- **No em dashes anywhere** — `grep -P '\u2014'` across the dump as a hard check, not just a visual skim.
- **No fabricated content** — every stat, quote, case study, and figure caption should be traceable to the source material actually provided. If you can't point to where a number came from, it shouldn't be on a slide.
- Missing content, typos, wrong section order.
- No leftover placeholder text (`TODO`, `[insert`, `Lorem ipsum`).

## 3. Visual QA (render every slide)

```bash
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
rm -f slide-*.jpg
pdftoppm -jpeg -r 150 output.pdf slide
```

View every rendered slide. In addition to the general defects listed in the base pptx
skill (overflow, overlap, low contrast, uneven gaps), check these project-specific points:

- **Palette discipline**: does this deck's primary/accent pair actually differ from the last deck's, and does it suit *this* deck's subject? A deck that defaulted back to navy/gold without a reason is a regression.
- **Dark-slide contrast**: on any full-dark or dark-panel slide, body text must be a light tint of the primary (e.g. `C9D6EA`-style), never the same muted gray used for body text on light slides — gray-on-dark reads as low-contrast and is a common miss.
- **Footer breadcrumb** present and correctly flipped to a light tint on dark slides.
- **Page-number badge** present, consistent position, correct contrast direction (dark badge/light text on light slides, the inverse on dark slides).
- **Image captions** use the two-part Fig-tag + caption-bar structure, not a floating caption.
- **Real photos, not generated ones** — wherever a slide claims to show something real (a source photo, a diagram, a chart from actual data), spot check that it traces to the source material, not an image-generation call. Purely decorative icons/illustrations are fine and don't need this check.
- **No two consecutive slides share the same archetype** from slide-archetypes.md.
- **Icon consistency** — same concept uses the same icon across the deck.

## 4. Final delivery

Copy the finished `.pptx` to `/mnt/user-data/outputs` and call `present_files`. Don't pause
for confirmation between QA steps — run the full loop autonomously and only surface
genuine ambiguities (e.g. a source image that's unsalvageable and needs a layout decision).
