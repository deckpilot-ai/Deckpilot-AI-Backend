# Design System

Extracted from four production decks (History: The Rise of the Marathas; Civics:
Federalism; Economics: Understanding Markets; Economics: Development) — all educational
content so far, but the system below is topic-agnostic. The same rules apply whether the
deck is a textbook chapter, a business strategy review, a product pitch, or a research
summary. The four source decks use four different palettes but the *same* structural DNA.
That's the pattern to replicate on any new deck: fixed structure, topic-tuned color.

## Canvas

- **13.333in × 7.5in widescreen** (`LAYOUT_WIDE` in pptxgenjs — set `pres.layout` before adding any slide).
- **0.6in left/right margins** on content slides (`x = 0.6in` for the primary content column start).
- Fonts: **Cambria** for headers/titles, **Calibri** for everything else (body, labels, captions, numbers). Both are on the pptx skill's safe list — true-to-width in QA and shipped with Office. Don't substitute Georgia/Trebuchet/Aptos.

## Color strategy: one primary, one accent, per topic

Every deck picks exactly one dark primary color and one warm accent, then builds neutrals
(tints of the primary, near-white backgrounds, a muted gray for secondary text) around
that pair. The primary carries 60-70% of the visual weight (backgrounds, headline text on
dark slides, footer breadcrumbs). The accent is used sparingly — icon fills, badge numbers,
underlines on selected pills — never as a large background.

Four worked examples from this project, so you can see how the *same formula* produces
different palettes:

| Deck topic | Primary (dark) | Accent (warm) | Light neutral | Body/caption gray |
|---|---|---|---|---|
| History — The Rise of the Marathas | `6B221C` maroon | `E4791F` burnt orange | `F7EEE3` cream | `8A7A6C` warm taupe |
| Civics — Federalism | `0C3B39` deep teal | `E08A1E` amber | `E9F3F1` mint white | `6B7A78` slate gray |
| Economics — Understanding Markets | `132A52` navy | `C68A2E` gold | `EEF2F8` ice blue | `737B87` cool gray |
| Economics — Development | `20302C` charcoal green | `C28A2C` gold | `F1F6F4` pale green | `5E726B` sage gray |

These four are worked examples from educational decks, not the only valid domain. The same
formula applies to any subject — a fintech pitch might land on deep navy/electric blue, a
sustainability report on forest green/warm gold, a healthcare deck on clinical teal/coral.
When starting a new deck, do **not** default to navy/gold just because it's the most recent
one built — pick a primary/accent pair that fits *this* deck's subject matter and tone (a
maroon/orange for a medieval-empire history topic reads very differently from the
navy/gold of a markets-and-prices economics topic, on purpose, and a deck for a fintech
client should look different again). Reuse the *ratios and roles* above, not the literal
hex values, unless the topic genuinely calls for the same mood.

Backgrounds are near-white or near-black — never default cream/beige unless, as above, the
palette specifically calls for a cream neutral. Content slides are light by default; a
handful of slides per deck (roughly 1 in 6) go full-dark for a "sandwich" rhythm: the title
slide, one or two conceptual/synthesis slides mid-deck, and the closing slide.

## Recurring components (exact specs)

These are the pieces that appear on nearly every slide. Build them once as helper
functions in your pptxgenjs script and reuse — don't hand-write each slide's footer.

### Eyebrow label (category tag above the title)

- Small all-caps text, ~12.5pt, accent or muted-primary color, e.g. `FOUNDATIONS`, `CASE STUDY · Q3 PILOT MARKET`, `GOVERNANCE AND MARKETS` — a short category tag naming the section, not the deck's title again.
- Positioned at roughly `x=0.6in, y=0.45in`, directly above the title.
- On section-opener style slides this becomes a small colored rect "chip" (e.g. `CHAPTER 2`) instead of bare text — see slide-archetypes.md's title slide spec.

### Title

- Cambria bold, 28-30pt on content slides (36-44pt only on the title/closing slides).
- Positioned directly under the eyebrow, `x=0.6in, y≈0.72in`, full content width.

### Footer breadcrumb

- Bottom-left, small (~9-10pt), muted gray (the "body/caption gray" from the palette table), format: `SERIES/PROGRAM NAME  ·  SECTION N: SECTION TITLE` in caps — e.g. `EXPLORING SOCIETY: INDIA AND BEYOND · CHAPTER 12: UNDERSTANDING MARKETS` for an educational deck, or `Q3 STRATEGY REVIEW · SECTION 2: MARKET SIZING` for a business deck. Adapt the two-part structure (context · this section) to whatever the deck's own framing is.
- On dark slides this flips to a lighter tint of the primary (e.g. `9FB0CC` on a `132A52` background) so it stays legible without competing with headline text.

### Page number badge

- Bottom-right corner: a small filled circle (primary color, ~0.38in diameter) with the page number in white, centered, on top of a plain white square behind it for contrast, OR the inverse (white circle + primary text) on dark slides.
- Consistent position across every slide: roughly `x≈12.55in, y≈7.05in`.

### Cards (the workhorse container)

- `roundRect`, light neutral fill (e.g. `EEF2F8`), no border, generous internal padding.
- Card header: bold text, sometimes preceded by an icon in a small colored circle (accent fill, ~25% alpha for a soft look, icon centered inside at full opacity).
- Card body: regular weight, the caption-gray color, 13-14pt.
- On dark slides, cards become a lighter tint of the primary (e.g. `16305C` on a `132A52` bg) with white headline text and a light tint of primary for body text (e.g. `C9D6EA`) — never gray-on-dark, it loses contrast.

### Pills / chips (small labeled tags)

- `roundRect`, compact (~0.5in tall), used for taxonomy labels on the title slide (topic tags), section badges, or inline emphasis words ("NEEDS" / "WANTS").
- Often layered: a white or near-white `roundRect` at low alpha (~12%) sits directly behind a solid-fill `rect` of the same size — this produces a soft embossed edge rather than a hard border. Reproduce this layering; don't just add a stroke.

### Icon circles

- `ellipse`, accent-colored fill, often at reduced alpha (20-25%) for a tinted-glass look, with the icon PNG (see image-pipeline.md) centered on top at full opacity.
- Consistent diameter within a deck, typically ~0.6in.

### Stat callouts

- Large number (36-48pt bold, Cambria or Calibri depending on deck — check sibling slides for consistency within one deck), small caption label beneath (10-12pt, caption gray, often all-caps).
- Usually 2-4 side by side in a row, equal width, inside light cards.

### Image captions ("Fig. X.X")

- Two adjacent rects directly under the image: a small dark tag on the left (`Fig. 12.4`) and a wider white/light bar to its right with the caption sentence.
- Never float a caption without this two-part tag+caption bar structure.

### Quote blocks

- Full-width or half-width card, background is either the accent-tinted cream or the dark primary (matches the "sandwich" rhythm of the slide it's on), with the quote in bold italic Cambria, larger than body (16-18pt), and an attribution line below in caption gray.

### Decorative motif (title and closing slides only)

- 2-3 large `ellipse` shapes at very low alpha (14-18%), oversized and bleeding off the slide edges (negative or >canvas offsets), in the primary/accent colors. This is the *one* decorative flourish this system permits — do not add it to content slides, and do not add any other decorative stripes/bars (see the base pptx skill's "Avoid" list — accent stripes and edge borders are explicitly banned across this whole project).

## Spacing

- 0.5-0.6in outer margins throughout.
- 0.3-0.4in gaps between cards in a grid; keep this consistent within a deck (don't mix 0.3in and 0.5in gaps on the same slide).
- Leave visible breathing room around every card — this system reads as "airy," not dense; if content doesn't fit, split across two slides rather than shrinking padding.
