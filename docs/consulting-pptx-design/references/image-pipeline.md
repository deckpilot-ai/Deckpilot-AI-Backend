# Image and Icon Pipeline

Two separate pipelines feed every deck: **real photos/diagrams extracted from source
material** when a PDF or document is provided (never AI-generated substitutes for those),
and **generated icon PNGs** (react-icons, for UI chrome like circles and card headers, not
for depicting real content). Not every deck has source imagery to extract — a business
strategy deck built from notes or a topic brief may rely entirely on icons, charts, and
the decorative motif for visuals, and that's fine. Extract real images whenever a real
source exists; don't fabricate a "real" photo when one doesn't.

## Extracting real photos from a source PDF (when one is provided)

1. **Extract embedded images**: `pdfimages -all source.pdf extracted/img` (or `pdfimages -list` first to inventory what's on each page before pulling everything).
2. **Diagnose color space per file before using it.** Scanned or textbook-style PDFs frequently embed images as CMYK JPEG2000 (`.jp2`). These can come out with inverted colors after naive conversion — check each extracted image visually before placing it in a slide; don't assume the whole batch shares one fix. A file that looks like a color negative (or has an odd cyan/magenta cast) needs explicit CMYK-aware inversion, file by file, not a blanket script applied to every image in the source.
3. **Composite soft masks with Pillow** where an image has a separate alpha/soft-mask channel extracted as its own file — recombine mask + base image in Pillow rather than shipping the un-masked base (which usually shows a colored box behind what should be a transparent background).
4. **Never generate a replacement image** for a photo, diagram, or chart that exists in the source material, even if the extracted version needs cleanup work. The whole value of this pipeline is that every "real" image in the deck is traceable to an actual source. If an image is unsalvageable, drop that visual element and adjust the slide layout — don't paper over it with a generated stand-in.
5. Crop/compose extracted photos into the "hero strip" or case-study photo groups used in several archetypes (2-4 related photos side by side) using Pillow, keeping consistent aspect ratios across a strip.

## When there's no source imagery at all

For decks built from a topic brief, notes, or business content with no images to extract:
rely on icon circles, stat callouts, charts (native pptxgenjs charts, per the base pptx
skill), and the decorative-ellipse motif for visual interest. Don't generate a photorealistic
image and present it as though it depicts something real (a "photo" of a client, a
fabricated product screenshot, a fake data source). Illustrative/abstract generated
graphics are fine for pure decoration; anything that reads as documentary evidence should
either be real or absent.

## Generating icons (react-icons → sharp → PNG)

Used for: card header icons, icon circles, process-flow node icons, taxonomy pill icons.
Never used for: anything that should look like a real photograph or a real source figure.

```javascript
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const { FaLandmark } = require('react-icons/fa'); // pick the icon that matches the content

const svgString = ReactDOMServer.renderToStaticMarkup(
  React.createElement(FaLandmark, { size: 256, color: '#C68A2E' })
);

sharp(Buffer.from(svgString))
  .resize(256, 256)
  .png()
  .toBuffer()
  .then(buf => {
    // pass buf to addImage as: "image/png;base64," + buf.toString("base64")
  });
```

**The critical fix**: pass the full, unmodified SVG string straight from
`renderToStaticMarkup` into `sharp()`. Don't manually strip attributes, re-serialize, or
partially edit the SVG string before handing it to sharp — that's what causes silent
rendering failures (blank or malformed rasters). If you need a different color or size, set
it via the React props (`size`, `color`) before rendering to string, not by post-editing
the SVG markup.

Rasterize at **256x256 minimum** even if the icon will be placed small — this keeps it
crisp at 2x export scaling and avoids visible pixelation on the icon-circle archetype.

## Choosing icons that fit the content

Pick react-icons that map literally to the concept (a landmark icon for governance, a
seedling for sustainability, a handshake for trade) rather than defaulting to generic
arrows/checkmarks everywhere. Reuse the same icon for the same recurring concept across a
deck (e.g. if "quality/safety" gets a shield icon on one slide, use the same shield
elsewhere it recurs) so the icon vocabulary reads as a deliberate system, not random
clip-art.
