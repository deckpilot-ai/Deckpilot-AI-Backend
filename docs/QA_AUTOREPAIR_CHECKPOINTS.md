# PowerPoint QA and auto-repair checkpoints

DeckPilot runs all 120 stable checkpoint IDs on each generated deck. A checkpoint
can inspect the slide specification, the source assets, the rendered PPTX, or all
three. Medium, high, and critical findings with a safe repair action enter a
three-pass repair, render, and recheck loop. The machine-readable definitions and
repair actions live in `app/agents/qa_checkpoints.py`.

## Content (QA-001 to QA-012)

1. QA-001 missing title
2. QA-002 duplicate title
3. QA-003 title too long
4. QA-004 title too short
5. QA-005 title placeholder
6. QA-006 empty body
7. QA-007 too many bullets
8. QA-008 bullet too long
9. QA-009 duplicate bullet
10. QA-010 near-duplicate bullet
11. QA-011 duplicate takeaway
12. QA-012 repeated slide copy

## Writing quality (QA-013 to QA-024)

13. QA-013 placeholder copy
14. QA-014 doubled sentence or phrase
15. QA-015 adjacent repeated words
16. QA-016 excessive all-caps copy
17. QA-017 excessive punctuation
18. QA-018 broken spacing
19. QA-019 orphan fragment
20. QA-020 repeated boilerplate lead
21. QA-021 speaker-note leak
22. QA-022 incomplete citation
23. QA-023 unsupported superlative
24. QA-024 encoding artifact

## Typography (QA-025 to QA-036)

25. QA-025 body font too small
26. QA-026 title font too small
27. QA-027 caption font too small
28. QA-028 footer font too small
29. QA-029 inconsistent body size
30. QA-030 inconsistent title size
31. QA-031 too many font families
32. QA-032 unsafe font
33. QA-033 missing typographic hierarchy
34. QA-034 over-bold body copy
35. QA-035 underemphasized key metric
36. QA-036 excessive line density

## Geometry (QA-037 to QA-048)

37. QA-037 object outside canvas
38. QA-038 text overflow
39. QA-039 text clipping
40. QA-040 unrelated shape overlap
41. QA-041 text/image overlap
42. QA-042 footer collision
43. QA-043 page-number collision
44. QA-044 safe-margin violation
45. QA-045 misaligned columns
46. QA-046 uneven gutters
47. QA-047 tiny meaningful object
48. QA-048 distorted aspect ratio

## Whitespace and balance (QA-049 to QA-060)

49. QA-049 excessive blank space
50. QA-050 blank left half
51. QA-051 blank right half
52. QA-052 blank top band
53. QA-053 blank bottom band
54. QA-054 unbalanced visual weight
55. QA-055 content clustered in one corner
56. QA-056 orphan visual object
57. QA-057 excessive card padding
58. QA-058 excessive title-to-content gap
59. QA-059 sparse non-divider slide
60. QA-060 crowded slide

## Images (QA-061 to QA-072)

61. QA-061 semantic image mismatch
62. QA-062 duplicate image assignment
63. QA-063 duplicate image pixels
64. QA-064 near-duplicate image
65. QA-065 unused image is more relevant
66. QA-066 image-led layout has no image
67. QA-067 low-resolution image
68. QA-068 blurry image
69. QA-069 extreme crop
70. QA-070 stretched image
71. QA-071 missing image caption
72. QA-072 generic image caption

## Visual selection and rhythm (QA-073 to QA-084)

73. QA-073 no supporting visuals
74. QA-074 sparse visual pacing
75. QA-075 image-led layouts overused
76. QA-076 consecutive image layouts
77. QA-077 same layout repeated consecutively
78. QA-078 layout/content mismatch
79. QA-079 numeric story missing a chart
80. QA-080 matrix evidence missing a table
81. QA-081 process content missing a process layout
82. QA-082 decorative overload
83. QA-083 inconsistent icon style
84. QA-084 missing page number

## Color and accessibility (QA-085 to QA-096)

85. QA-085 low text contrast
86. QA-086 low icon contrast
87. QA-087 low chart contrast
88. QA-088 too many unrelated colors
89. QA-089 inconsistent backgrounds
90. QA-090 unreadable text on a dark slide
91. QA-091 accent color overuse
92. QA-092 alert color used without negative meaning
93. QA-093 transparent text
94. QA-094 indistinguishable chart series colors
95. QA-095 inconsistent link color
96. QA-096 meaning depends on color alone

## Data integrity (QA-097 to QA-108)

97. QA-097 chart missing categories
98. QA-098 chart missing series
99. QA-099 chart category/series length mismatch
100. QA-100 non-numeric chart value
101. QA-101 chart missing source
102. QA-102 chart missing units
103. QA-103 table missing headers
104. QA-104 inconsistent table row width
105. QA-105 table too wide
106. QA-106 table too long
107. QA-107 duplicate metric
108. QA-108 metric missing a label

## Technical and packaging (QA-109 to QA-120)

109. QA-109 corrupt PPTX package
110. QA-110 slide-count mismatch
111. QA-111 broken media relationship
112. QA-112 missing speaker notes
113. QA-113 duplicate slide ID
114. QA-114 non-contiguous slide numbers
115. QA-115 invalid layout identifier
116. QA-116 empty content shape
117. QA-117 hidden required content
118. QA-118 unsupported font
119. QA-119 image missing descriptive metadata
120. QA-120 unresolved high-severity finding after repair

## Automatic resolution rules

- Repeated images are replaced with the highest-scoring relevant unused asset.
  If no relevant unique image exists, the image is removed and the slide is
  rerouted to a non-image layout.
- Image relevance uses the caption, nearby source text, and semantic summary.
- Exact and near-duplicate bullets are removed. Repeated words, punctuation,
  malformed spacing, and encoding artifacts are normalized.
- Small rendered text triggers a per-slide font scale increase. The renderer
  enforces an 11 pt minimum for ordinary text and data labels.
- Sparse or unbalanced slides switch to a content-appropriate layout and receive
  a legibility scale boost.
- Invalid chart data is never invented. Incomplete charts are removed or aligned
  to the valid category/series intersection.
- Oversized tables are capped to six columns and ten rows for slide readability.
- Geometry findings trigger safe-layout routing. The repaired deck is rendered
  again and checked again for up to three passes.
