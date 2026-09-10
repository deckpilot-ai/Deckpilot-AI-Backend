from app.services.grounding_chunker import GroundingChunker


def _source(page: int, content: str) -> str:
    filler = f" Background material for page {page}." * 35
    return f'[Source textbook.pdf#page={page}]:\n{{"content": "{content}{filler}"}}'


def test_retrieve_for_slides_finds_later_source_instead_of_first_page() -> None:
    grounding = "\n\n".join(
        [
            _source(1, "Early kingdoms and village life."),
            _source(2, "Agriculture and forest resources."),
            _source(12, "Satrap governors administered imperial provinces."),
        ]
    )

    result = GroundingChunker.retrieve_for_slides(
        grounding,
        ["Satraps govern provinces under imperial oversight"],
        max_chars_total=900,
        max_chars_per_topic=900,
    )

    assert "Satrap governors" in result
    assert "page=12" in result
    assert "page=1]:" not in result


def test_retrieve_for_slides_represents_each_topic_in_a_batch() -> None:
    grounding = "\n\n".join(
        [
            _source(1, "Guild leaders managed trade and market resources."),
            _source(8, "Greek forces encouraged cultural exchange."),
            _source(20, "Arthashastra addressed defence economy and justice."),
        ]
    )

    result = GroundingChunker.retrieve_for_slides(
        grounding,
        ["guild leaders and markets", "Greek cultural exchange", "Arthashastra justice"],
        max_chars_total=1500,
        max_chars_per_topic=500,
    )

    assert "Guild leaders" in result
    assert "Greek forces" in result
    assert "Arthashastra" in result


def test_extract_evidence_points_creates_source_based_fallback_copy() -> None:
    excerpt = (
        "[Source textbook.pdf#page=8]:\n"
        "90\nExploring Society: India and Beyond | Grade 7 Part 1\n"
        "Fig. 5.4.3. To expand into an empire, a kingdom might first wage war "
        "against neighbouring territories so as to conquer them.\n"
        "Fig. 5.4.4. Rulers endeavoured to control rivers and trade networks "
        "to gain precious resources and tax revenue.\nReprint 2026-27"
    )

    points = GroundingChunker.extract_evidence_points(
        excerpt,
        "Conquest resources and trade drive empire growth",
    )

    assert any("wage war" in point for point in points)
    assert any("trade networks" in point for point in points)
    assert all("Exploring Society" not in point for point in points)
