# Design System Analysis: Maratha Heritage Editorial Theme (`maratha-heritage-editorial-v1`)

## 1. Executive Summary & Deck Overview

- **Source Reference Presentation**: `The Rise of the Marathas (4).pptx`
- **Total Slides**: 24 slides
- **Dimensions**: `13.333" × 7.500"` (16:9 widescreen, 12,192,000 × 6,858,000 EMUs)
- **Theme ID**: `maratha-heritage-editorial-v1`
- **Theme Category**: `heritage-editorial`
- **Visual Character**: Historical, Civilizational, Museum-Grade, Educational, Documentary
- **Primary Domain Applicability**: History, Indian History, Civilisations, Biographies, Dynasties, Empires, Wars, Culture, Heritage, Geography, Political History, Social Science, Archaeology, Historical Research

The visual system pairs classical serif headings (`Cambria`) with clean humanist sans-serif body text (`Calibri`), grounded by warm parchment and cream cards, saffron-orange circular icon badges, and antique-gold kicker labels on both light backgrounds and deep heritage maroon canvases.

---

## 2. Palette & Exact DrawingML Colors

All colors are extracted directly from the reference PPTX DrawingML package and formalized into centralized tokens:

| Semantic Token | Hex Code | RGB | Reference Usage |
| :--- | :--- | :--- | :--- |
| `canvas` | `#FFFFFF` | `(255, 255, 255)` | Standard slide canvas background |
| `maroon` | `#6B221C` | `(107, 34, 28)` | Primary dark maroon: slide titles, dark cards, timeline headers, cover/dark slide backgrounds |
| `maroonAlt` | `#7E2C22` | `(126, 44, 34)` | Secondary maroon: decorative background geometry |
| `orange` | `#E4791F` | `(228, 121, 31)` | Saffron orange: icon circles, numbered badges, timeline dates, metrics, checkmarks |
| `gold` | `#B0771A` | `(176, 119, 26)` | Antique gold: kicker/eyebrow labels, metadata highlights |
| `body` | `#2A211C` | `(42, 33, 28)` | Primary ink for all readable paragraph text, card text, descriptions |
| `muted` | `#8A7A6C` | `(138, 122, 108)` | Figure captions, footers, source text, slide numbers |
| `parchment` | `#FBF6EF` | `(251, 246, 239)` | Main text panels, narrative cards, primary information panels |
| `cream` | `#F7EEE3` | `(247, 238, 227)` | Secondary cards, timeline bodies, metric cards, image frame containers |
| `borderWarm` | `#E9D8CB` | `(233, 216, 203)` | Subtle warm border on cards, image frames, and glossary containers |
| `textOnDark` | `#F5EAE0` | `(245, 234, 224)` | Light warm cream text on dark maroon backgrounds |
| `white` | `#FFFFFF` | `(255, 255, 255)` | Cover title, dark slide titles, icons inside orange badges |

---

## 3. Typography Hierarchy Matrix

Strictly uses `Cambria` for editorial display and `Calibri` for body/UI text:

| Text Role | Font Family | Size (pt) | Weight | Style | Color | Case / Tracking |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cover Title** | `Cambria` | 52 pt (40–58) | Bold | Regular | `#FFFFFF` | Title Case |
| **Slide Title** | `Cambria` | 27 pt (23–30) | Bold | Regular | `#6B221C` (or `#FFFFFF` on dark) | Title Case |
| **Kicker** | `Calibri` | 12 pt (11–13) | Bold | Regular | `#B0771A` | ALL CAPS, wide tracking |
| **Card Title** | `Cambria` | 15–18 pt (13–18)| Bold | Regular | `#6B221C` | Title Case |
| **Lead Body** | `Calibri` | 14.5–15.5 pt | Regular | Regular | `#2A211C` | Sentence Case, 1.15 line space |
| **Normal Body** | `Calibri` | 13–14 pt | Regular | Regular | `#2A211C` | Sentence Case |
| **Compact Body** | `Calibri` | 11.5–12.5 pt| Regular | Regular | `#2A211C` | Sentence Case |
| **Caption / Source** | `Calibri` | 10.5 pt (9–11) | Regular | Italic | `#8A7A6C` | Sentence Case |
| **Footer & Page No.** | `Calibri` | 9 pt (8–9.5) | Regular | Regular | `#8A7A6C` | Sentence Case |
| **Metric Value** | `Cambria` | 28–34 pt | Bold | Regular | `#E4791F` | Large Number |
| **Historical Quote** | `Cambria` | 20 pt (15–24) | Regular | Italic | `#FFFFFF` / `#6B221C` | Sentence Case |

---

## 4. Recurring Geometry & Grid System

- **Slide Dimensions**: `13.333" × 7.500"`
- **Safe Bounds**:
  - Left Margin: `0.55 in`
  - Right Margin: `12.783 in` (usable width `12.233 in`)
  - Header Top: `0.50 in`
  - Content Region: `y = 1.65 in` to `6.80 in` (usable height `5.15 in`)
  - Footer Top: `7.06 in`
- **Standard Header Coordinates**:
  - Icon Badge: `left = 0.55 in`, `top = 0.52 in`, `diameter = 0.66 in` (`#E4791F` fill)
  - Kicker: `left = 1.41 in`, `top = 0.50 in`, `height = 0.28 in` (`#B0771A`, Calibri 12pt Bold Uppercase)
  - Title: `left = 1.41 in`, `top = 0.75 in`, `height = 0.68 in` (`#6B221C`, Cambria 27pt Bold)
  - Header Text Left Offset: `1.41 in` (`0.55 + 0.66 + 0.20 in gap`)
- **Dark Slide Header Coordinates** (Slides 19 & 24):
  - Icon Badge: `left = 0.55 in`, `top = 0.60 in`
  - Kicker: `left = 1.41 in`, `top = 0.62 in`
  - Title: `left = 1.41 in`, `top = 0.86 in`
- **Footer Coordinates**:
  - Source / Context Line: `left = 0.55 in`, `top = 7.06 in`, `width = 9.0 in` (`#8A7A6C`, Calibri 9pt)
  - Page Number: `left = 12.183 in`, `top = 7.06 in`, `width = 0.60 in`, right-aligned
- **Card Internal Padding**:
  - Compact: `0.18 in`
  - Standard: `0.24–0.28 in`
  - Comfortable: `0.35 in`
  - Every text region subtracts horizontal and vertical padding from container bounds.
- **Alignment Tolerance**: `0.03 in`

---

## 5. All 24 Slide Archetypes (`M01`–`M24`)

| ID | Slide | Reference Title | Layout Archetype & Composition |
| :--- | :--- | :--- | :--- |
| **M01** | S01 | *The Rise of the Marathas* | **Maroon Cover + Hero Image**: `#6B221C` canvas, decorative circular geometry, gold kicker, 52pt Cambria title, orange accent line, italic subtitle, large framed coronation image right (`w=5.01`, `h=4.80`). |
| **M02** | S02 | *The Big Questions* | **Three / Four Big Questions**: Standard header + 3 large vertical parchment cards (`#FBF6EF`), orange sequence circles (`01`–`03`), prominent centered question text. |
| **M03** | S03 | *Who are the Marathas?* | **Origin Story + Two Visuals + Glossary**: Parchment narrative panel left (`w=8.20`), two historical portraits upper-right, dark maroon glossary card ("Maratha identity") lower-right. |
| **M04** | S04 | *Timeline of the Marathas* | **Three-Phase Chronology**: Three equal columns. Each has a dark maroon header with phase title & date range, and cream body with orange event dates and descriptions. |
| **M05** | S05 | *Rise of Chhatrapati Shivaji*| **Biography + Portrait + Key Term**: Narrative card left, hero portrait right, wide dark-maroon "Swarajya" glossary card below narrative. |
| **M06** | S06 | *The Maratha Navy* | **Explanation + Image + Two Metrics**: Narrative card left, two metric cards lower-left ("1657 Navy founded", "100+ ships"), Sindhudurg sea fort image right with caption. |
| **M07** | S07 | *Guerrilla Warfare* | **Explanation + Artefact + Did-You-Know**: Narrative card left, Waghnakh weapon artefact top-right, dark maroon Did-You-Know card bottom-right. |
| **M08** | S08 | *Bold Campaigns* | **Two Campaign Cards + Insight Strip**: Two equal parchment cards (Night Raid & Surat), orange icons, Cambria titles, full-width maroon insight strip beneath. |
| **M09** | S09 | *Purandar, Agra and Escape*| **Wide Story Panel + Centered Image**: Broad parchment narrative card across top, centered horizontal escape painting beneath (`w=5.73`, `h=2.00`), caption below. |
| **M10** | S10 | *Coronation and Conquest* | **Narrative + Map + Date Callout**: Narrative card left, tall territorial map right (`w=3.83`, `h=4.80`), embedded 1674 coronation date callout card. |
| **M11** | S11 | *A Legend in His Own Lifetime*| **Narrative + Dark Ethical Insight Panel**: Parchment narrative left, tall dark-maroon contextual panel right with orange icon, Cambria heading, and light warm body. |
| **M12** | S12 | *The Marathas after Shivaji* | **Narrative + Historical Painting**: Large narrative panel left, tall historical artwork/painting of Sambhaji right with museum caption. |
| **M13** | S13 | *The Peshwas and Expansion* | **Narrative + Image + Person Strip**: Narrative card left, Baji Rao portrait right, full-width maroon strip below with orange icon and Peshwa office description. |
| **M14** | S14 | *The Anglo-Maratha Wars* | **Three War Cards + Quote Strip**: Three equal period cards (First, Second, Third Anglo-Maratha Wars) with dates and descriptions, full-width dark quote strip beneath. |
| **M15** | S15 | *Civilian Administration* | **Administration + Coin + Insight**: Narrative card left, Hon gold coin image right, bottom cream insight strip on decentralized governance. |
| **M16** | S16 | *Ashta Pradhana Mandala* | **Governance Hub / Council**: 4 minister cards top row, central orange Chhatrapati core node, 4 minister cards bottom row, structured portfolio cards. |
| **M17** | S17 | *Chauth, Sardeshmukhi and Coins*| **Revenue + Coin + KPI Cards**: Narrative card left, historical rupee coin image right, two metric cards ("25% Chauth", "+10% Sardeshmukhi"). |
| **M18** | S18 | *Military Administration* | **Military System + Weapons Visual**: Large narrative panel left (fort garrisons, cavalry, infantry), historical sword and shield weapon visual right. |
| **M19** | S19 | *Forts: The Core of the State*| **Dark Quote + Three Supporting Points**: Full dark-maroon canvas (`#6B221C`), dark header, large historical quote left, three vertically stacked principle cards right. |
| **M20** | S20 | *Maritime Supremacy* | **Narrative + Maritime Battle Visual + Fact**: Narrative card left, naval battle visual right, dark contextual fact strip below image. |
| **M21** | S21 | *Justice, Trade & Culture* | **Three Pillars + Supporting Seal**: 3 vertical cream cards (Justice, Trade, Culture), each with orange icon and title, royal Sanskrit Rajmudra seal right. |
| **M22** | S22 | *The Mighty Maratha Women* | **Dual Historical Leaders**: Warrior queen portrait left (Tarabai), Leader 1 card, Leader 2 card (Ahilyabai Holkar), postage stamp right. |
| **M23** | S23 | *In Focus: Thanjavur* | **Feature Story + Three-Image Gallery**: Narrative card left, 1 hero Thanjavur painting right, 2 smaller supporting images below (Modi script & inscription). |
| **M24** | S24 | *The Maratha Legacy* | **Dark Legacy Summary**: Full dark-maroon canvas, 5 concise takeaway rows with saffron-orange check badges, orange divider line, final italic closing takeaway. |

---

## 6. Collision Prevention, Text Budgeting & Auto-Fit

To eliminate release-blocking defects:
1. **Unified Text Frames**: Complex cards with title and body use unified single-text-frame layouts with paragraph spacing, eliminating text-on-text overlap.
2. **Text Measurement & Clamping**: `fit_text_to_box()` calculates line count and bounding height using Cambria (`0.54` char ratio) and Calibri (`0.49` char ratio) font metrics. It steps down font sizes within approved budgets (`min_pt` to `preferred_pt`) before applying safe word-boundary truncation with ellipsis.
3. **Corner Radius Clamping**: All rounded rectangles clamp corner radius to `0.022–0.06`, preventing bulbous edges or adjacent cards from fusing.
4. **Z-Order Preservation**: Background decorative geometry is placed first, cards second, images and badges third, text frames fourth, and header/footer elements fifth.

---

## 7. Semantic Icon Resolution Engine

The `IconResolver` maps over 80 semantic concepts to verified icon assets extracted from the reference presentation.
- **Zero Empty Badges**: If an exact keyword is not found, nearest historical semantic fallback is used.
- **Optical Centering**: Badges compute optical center offsets (`x + (d - size)/2.0`) to center the icon inside the circular badge.
- **Responsive Sizing**: Sized to `0.52–0.55` ratio of the badge diameter.
