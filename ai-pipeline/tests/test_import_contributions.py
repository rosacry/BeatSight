"""Tests for contribution import utility."""

import json
import tempfile
from pathlib import Path

import pytest

from training.import_contributions import (
    ContributionImporter,
    ContributionSample,
    import_contributions,
)


@pytest.fixture
def sample_manifest():
    """Create a sample manifest for testing."""
    return {
        "version": "1.0",
        "batch_id": "test-batch-001",
        "generated_at": "2025-12-03T12:00:00Z",
        "sample_count": 3,
        "source": "beatsight_community_contributions",
        "samples": [
            {
                "id": "sample-1",
                "map_version_id": "map-001",
                "onset_time_ms": 1000,
                "correction_type": "component_change",
                "original": {
                    "component": "snare",
                    "confidence": 0.95,
                },
                "corrected": {
                    "component": "hi-hat",
                    "time_ms": 1005,
                },
                "weight": 1.8,
            },
            {
                "id": "sample-2",
                "map_version_id": "map-001",
                "onset_time_ms": 2000,
                "correction_type": "note_addition",
                "original": {
                    "component": None,
                    "confidence": None,
                },
                "corrected": {
                    "component": "kick",
                    "time_ms": 2000,
                },
                "weight": 1.4,
            },
            {
                "id": "sample-3",
                "map_version_id": "map-001",
                "onset_time_ms": 3000,
                "correction_type": "velocity_change",
                "original": {
                    "component": "crash",
                    "confidence": 0.8,
                },
                "corrected": {
                    "component": "crash",
                    "velocity": 100,
                },
                "weight": 0.3,  # Below threshold
            },
        ],
    }


class TestContributionImporter:
    """Tests for ContributionImporter class."""

    def test_component_map_has_standard_components(self):
        """Test component map includes all standard drum components."""
        assert "kick" in ContributionImporter.COMPONENT_MAP
        assert "snare" in ContributionImporter.COMPONENT_MAP
        assert "hi-hat" in ContributionImporter.COMPONENT_MAP
        assert "crash" in ContributionImporter.COMPONENT_MAP
        assert "ride" in ContributionImporter.COMPONENT_MAP

    def test_parse_sample(self, sample_manifest):
        """Test sample parsing from manifest data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            
            sample_data = sample_manifest["samples"][0]
            sample = importer._parse_sample(sample_data)
            
            assert sample.id == "sample-1"
            assert sample.map_version_id == "map-001"
            assert sample.onset_time_ms == 1000
            assert sample.correction_type == "component_change"
            assert sample.original_component == "snare"
            assert sample.original_confidence == 0.95
            assert sample.corrected_component == "hi-hat"
            assert sample.corrected_time_ms == 1005
            assert sample.weight == 1.8

    def test_to_training_format_component_change(self, sample_manifest):
        """Test conversion of component change to training format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            
            sample = importer._parse_sample(sample_manifest["samples"][0])
            training = importer._to_training_format(sample, "test-batch")
            
            assert training is not None
            assert training["label"] == "hihat_closed"  # Mapped from hi-hat
            assert training["original_label"] == "snare_center"
            assert training["onset_time_ms"] == 1005  # Uses corrected time
            assert training["weight"] == 1.8
            assert training["source"] == "community_contribution"

    def test_to_training_format_note_addition(self, sample_manifest):
        """Test conversion of note addition to training format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            
            sample = importer._parse_sample(sample_manifest["samples"][1])
            training = importer._to_training_format(sample, "test-batch")
            
            assert training is not None
            assert training["label"] == "kick"
            assert training["correction_type"] == "note_addition"

    def test_to_training_format_velocity_change_skipped(self, sample_manifest):
        """Test that velocity changes are skipped (no clear label)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            
            sample = importer._parse_sample(sample_manifest["samples"][2])
            training = importer._to_training_format(sample, "test-batch")
            
            # Velocity changes don't give us label information
            assert training is None

    def test_import_from_manifest(self, sample_manifest):
        """Test full manifest import."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            
            imported, skipped = importer.import_from_manifest(
                sample_manifest, min_weight=0.5
            )
            
            # Should import component_change and note_addition
            # Should skip velocity_change (below weight threshold)
            assert imported == 2
            assert skipped == 1
            
            # Check output files exist
            batch_dir = Path(tmpdir) / "test-batch-001"
            assert (batch_dir / "samples.json").exists()
            assert (batch_dir / "import_meta.json").exists()

    def test_import_creates_output_files(self, sample_manifest):
        """Test that import creates proper output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            importer.import_from_manifest(sample_manifest, min_weight=0.5)
            
            batch_dir = Path(tmpdir) / "test-batch-001"
            
            # Check samples file
            with open(batch_dir / "samples.json") as f:
                samples_data = json.load(f)
            
            assert samples_data["batch_id"] == "test-batch-001"
            assert samples_data["source"] == "community_contributions"
            assert samples_data["sample_count"] == 2
            assert len(samples_data["samples"]) == 2
            
            # Check meta file
            with open(batch_dir / "import_meta.json") as f:
                meta_data = json.load(f)
            
            assert meta_data["imported_count"] == 2
            assert meta_data["skipped_count"] == 1

    def test_get_statistics(self, sample_manifest):
        """Test statistics reporting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            importer = ContributionImporter(output_dir=tmpdir)
            importer.import_from_manifest(sample_manifest, min_weight=0.5)
            
            stats = importer.get_statistics()
            
            assert stats["total_imported"] == 2
            assert stats["total_skipped"] == 1
            assert stats["error_count"] == 0


class TestConvenienceFunction:
    """Tests for the import_contributions convenience function."""

    def test_import_contributions_from_file(self, sample_manifest):
        """Test importing from a manifest file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write manifest to file
            manifest_path = Path(tmpdir) / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(sample_manifest, f)
            
            output_dir = Path(tmpdir) / "output"
            
            stats = import_contributions(
                str(manifest_path),
                str(output_dir),
                min_weight=0.5,
            )
            
            assert stats["total_imported"] == 2
            assert stats["total_skipped"] == 1


class TestContributionSample:
    """Tests for ContributionSample dataclass."""

    def test_default_weight(self):
        """Test default weight is 1.0."""
        sample = ContributionSample(
            id="test",
            map_version_id="map",
            onset_time_ms=1000,
            correction_type="component_change",
            original_component="kick",
            original_confidence=0.9,
            corrected_component="snare",
            corrected_time_ms=None,
            corrected_velocity=None,
        )
        
        assert sample.weight == 1.0
