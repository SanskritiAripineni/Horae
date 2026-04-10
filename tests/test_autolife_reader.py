"""
Tests for tools/autolife_reader.py — Journal parsing.

Tests cover:
- get_context_for_prompt() formatting with various inputs
- read_journals() with real temp files mimicking the export format
- Edge cases: empty input, missing fields, character limits
"""

import os
import pytest
from pathlib import Path

from tools.autolife_reader import AutoLifeReader


# ---------------------------------------------------------------------------
# get_context_for_prompt
# ---------------------------------------------------------------------------

class TestGetContextForPrompt:

    def test_formats_single_entry(self):
        reader = AutoLifeReader(data_dir="/tmp/unused")
        journals = [
            {
                "created_at": "2024-05-10 08:00:00",
                "period": "Morning",
                "content": "Had a good breakfast.",
            }
        ]
        result = reader.get_context_for_prompt(journals)
        assert "2024-05-10 08:00:00" in result
        assert "(Morning)" in result
        assert "Had a good breakfast." in result

    def test_formats_multiple_entries_with_separator(self):
        reader = AutoLifeReader(data_dir="/tmp/unused")
        journals = [
            {"created_at": "2024-05-10 08:00:00", "period": "Morning", "content": "Entry 1"},
            {"created_at": "2024-05-10 14:00:00", "period": "Afternoon", "content": "Entry 2"},
        ]
        result = reader.get_context_for_prompt(journals)
        assert "---" in result
        assert "Entry 1" in result
        assert "Entry 2" in result

    def test_respects_max_chars_limit(self):
        reader = AutoLifeReader(data_dir="/tmp/unused")
        long_content = "x" * 3000
        journals = [
            {"created_at": "2024-01-01", "period": "Morning", "content": long_content},
            {"created_at": "2024-01-02", "period": "Afternoon", "content": long_content},
            {"created_at": "2024-01-03", "period": "Evening", "content": long_content},
        ]
        result = reader.get_context_for_prompt(journals, max_chars=5000)
        # Should include at most entries that fit within 5000 chars
        assert len(result) <= 6000  # some leeway for separators

    def test_empty_input_returns_no_entries_message(self):
        reader = AutoLifeReader(data_dir="/tmp/unused")
        result = reader.get_context_for_prompt([])
        assert "No recent journal entries" in result

    def test_missing_fields_handled_gracefully(self):
        reader = AutoLifeReader(data_dir="/tmp/unused")
        journals = [
            {"content": "Just content, no metadata"},
        ]
        result = reader.get_context_for_prompt(journals)
        assert "Just content" in result

    def test_uses_timestamp_fallback(self):
        reader = AutoLifeReader(data_dir="/tmp/unused")
        journals = [
            {"timestamp": "2024-06-01 09:00:00", "period": "Morning", "content": "test"},
        ]
        result = reader.get_context_for_prompt(journals)
        assert "2024-06-01 09:00:00" in result


# ---------------------------------------------------------------------------
# read_journals (with temp files)
# ---------------------------------------------------------------------------

class TestReadJournals:

    def _write_export_file(self, data_dir: Path, entries: list) -> Path:
        """Write a mock AutoLife export file."""
        autolife_dir = data_dir / "AutoLife"
        autolife_dir.mkdir(parents=True, exist_ok=True)
        filepath = autolife_dir / "all_journals_20240510.txt"

        lines = []
        for entry in entries:
            lines.append("=" * 40)
            lines.append(f"JOURNAL ENTRY #{entry['num']}")
            lines.append(f"Created At: {entry['created_at']}")
            lines.append(f"Period: {entry['period']}")
            lines.append("-" * 20)
            lines.append("")
            lines.append(entry["content"])
            lines.append("")

        filepath.write_text("\n".join(lines))
        return filepath

    def test_parses_export_file(self, tmp_path):
        entries = [
            {"num": 1, "created_at": "2024-05-10 08:00:00", "period": "Morning",
             "content": "Woke up feeling good."},
            {"num": 2, "created_at": "2024-05-10 14:00:00", "period": "Afternoon",
             "content": "Had lunch with friends."},
        ]
        self._write_export_file(tmp_path, entries)

        reader = AutoLifeReader(data_dir=str(tmp_path))
        journals = reader.read_journals()

        assert len(journals) == 2
        # Sorted descending by entry_number
        assert journals[0]["entry_number"] == 2
        assert journals[1]["entry_number"] == 1
        assert "Woke up feeling good" in journals[1]["content"]
        assert journals[0]["period"] == "Afternoon"

    def test_respects_limit(self, tmp_path):
        entries = [
            {"num": i, "created_at": f"2024-05-{10+i} 08:00:00", "period": "Morning",
             "content": f"Entry {i}"}
            for i in range(1, 6)
        ]
        self._write_export_file(tmp_path, entries)

        reader = AutoLifeReader(data_dir=str(tmp_path))
        journals = reader.read_journals(limit=3)
        assert len(journals) == 3

    def test_returns_empty_when_no_files(self, tmp_path):
        reader = AutoLifeReader(data_dir=str(tmp_path))
        journals = reader.read_journals()
        assert journals == []

    def test_entry_ids_are_generated(self, tmp_path):
        entries = [
            {"num": 42, "created_at": "2024-05-10 08:00:00", "period": "Morning",
             "content": "Test content"},
        ]
        self._write_export_file(tmp_path, entries)

        reader = AutoLifeReader(data_dir=str(tmp_path))
        journals = reader.read_journals()
        assert journals[0]["id"] == "entry_42"

    def test_creates_data_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "brand_new"
        reader = AutoLifeReader(data_dir=str(new_dir))
        assert new_dir.exists()
