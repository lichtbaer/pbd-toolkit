"""Tests for statistics aggregator."""

from matches import PiiMatch
from core.statistics_aggregator import StatisticsAggregator


def create_test_match(
    text: str, file: str, type: str, engine: str = "regex", score: float = None
) -> PiiMatch:
    """Helper to create test PiiMatch objects."""
    return PiiMatch(text=text, file=file, type=type, ner_score=score, engine=engine)


def test_aggregator_initialization():
    """Test that aggregator initializes correctly."""
    agg = StatisticsAggregator()
    stats = agg.get_statistics()

    assert "statistics_by_dimension" in stats
    assert "statistics_by_module" in stats
    assert "statistics_by_file_type" in stats
    assert "summary" in stats


def test_aggregator_add_match():
    """Test adding matches to aggregator."""
    agg = StatisticsAggregator()

    match1 = create_test_match(
        "test@example.com", "/path/file1.pdf", "REGEX_EMAIL", "regex"
    )
    match2 = create_test_match(
        "John Doe", "/path/file2.docx", "NER_PERSON", "gliner", 0.95
    )

    agg.add_match(match1)
    agg.add_match(match2)

    stats = agg.get_statistics()

    # Check dimension statistics
    assert "contact_information" in stats["statistics_by_dimension"]
    assert stats["statistics_by_dimension"]["contact_information"]["total_count"] == 1
    assert (
        stats["statistics_by_dimension"]["contact_information"]["by_type"][
            "REGEX_EMAIL"
        ]
        == 1
    )

    assert "identity" in stats["statistics_by_dimension"]
    assert stats["statistics_by_dimension"]["identity"]["total_count"] == 1
    assert stats["statistics_by_dimension"]["identity"]["by_type"]["NER_PERSON"] == 1

    # Check module statistics
    assert "regex" in stats["statistics_by_module"]
    assert stats["statistics_by_module"]["regex"]["total_matches"] == 1

    assert "gliner" in stats["statistics_by_module"]
    assert stats["statistics_by_module"]["gliner"]["total_matches"] == 1
    assert stats["statistics_by_module"]["gliner"]["avg_confidence"] == 0.95


def test_aggregator_file_tracking():
    """Test that files are tracked correctly."""
    agg = StatisticsAggregator()

    match1 = create_test_match(
        "test@example.com", "/path/file1.pdf", "REGEX_EMAIL", "regex"
    )
    match2 = create_test_match(
        "test2@example.com", "/path/file1.pdf", "REGEX_EMAIL", "regex"
    )
    match3 = create_test_match("John Doe", "/path/file2.docx", "NER_PERSON", "gliner")

    agg.add_match(match1)
    agg.add_match(match2)
    agg.add_match(match3)

    stats = agg.get_statistics()

    # Check that files_affected counts unique files
    assert (
        stats["statistics_by_dimension"]["contact_information"]["files_affected"] == 1
    )
    assert stats["statistics_by_dimension"]["identity"]["files_affected"] == 1

    # Check file type statistics
    assert ".pdf" in stats["statistics_by_file_type"]
    assert stats["statistics_by_file_type"][".pdf"]["matches_found"] == 2

    assert ".docx" in stats["statistics_by_file_type"]
    assert stats["statistics_by_file_type"][".docx"]["matches_found"] == 1


def test_aggregator_summary():
    """Test summary generation."""
    agg = StatisticsAggregator()

    # Add matches from different dimensions
    agg.add_match(
        create_test_match("test@example.com", "/path/file1.pdf", "REGEX_EMAIL", "regex")
    )
    agg.add_match(
        create_test_match("John Doe", "/path/file2.docx", "NER_PERSON", "gliner")
    )
    agg.add_match(
        create_test_match("123456789", "/path/file3.pdf", "REGEX_IBAN", "regex")
    )
    agg.add_match(
        create_test_match(
            "Health data", "/path/file4.txt", "NER_HEALTH", "gliner", 0.88
        )
    )

    stats = agg.get_statistics()
    summary = stats["summary"]

    assert summary["total_matches"] == 4
    assert summary["unique_files_with_matches"] == 4
    assert (
        summary["dimensions_detected"] == 3
    )  # contact_information, identity, financial, health
    assert summary["modules_used"] == 2  # regex, gliner

    # Check risk assessment
    assert "risk_assessment" in summary
    assert summary["risk_assessment"]["very_high_risk_count"] == 1  # health
    assert summary["risk_assessment"]["high_risk_count"] == 1  # identity or financial
    assert summary["highest_risk_dimension"] == "health"


def test_aggregator_confidence_distribution():
    """Test confidence score distribution calculation."""
    agg = StatisticsAggregator()

    # Add matches with different confidence scores
    agg.add_match(
        create_test_match("Match1", "/path/file1.pdf", "NER_PERSON", "gliner", 0.3)
    )
    agg.add_match(
        create_test_match("Match2", "/path/file1.pdf", "NER_PERSON", "gliner", 0.6)
    )
    agg.add_match(
        create_test_match("Match3", "/path/file1.pdf", "NER_PERSON", "gliner", 0.8)
    )
    agg.add_match(
        create_test_match("Match4", "/path/file1.pdf", "NER_PERSON", "gliner", 0.95)
    )

    stats = agg.get_statistics()
    module_stats = stats["statistics_by_module"]["gliner"]

    assert "confidence_distribution" in module_stats
    dist = module_stats["confidence_distribution"]
    assert dist["0.0-0.5"] == 1
    assert dist["0.5-0.7"] == 1
    assert dist["0.7-0.9"] == 1
    assert dist["0.9-1.0"] == 1


def test_aggregator_file_scanned():
    """Test file scanning tracking."""
    agg = StatisticsAggregator()

    agg.add_file_scanned("/path/file1.pdf", was_analyzed=True)
    agg.add_file_scanned("/path/file2.pdf", was_analyzed=False)
    agg.add_file_scanned("/path/file3.docx", was_analyzed=True)

    stats = agg.get_statistics()

    assert stats["statistics_by_file_type"][".pdf"]["files_scanned"] == 2
    assert stats["statistics_by_file_type"][".pdf"]["files_analyzed"] == 1
    assert stats["statistics_by_file_type"][".docx"]["files_scanned"] == 1
    assert stats["statistics_by_file_type"][".docx"]["files_analyzed"] == 1
