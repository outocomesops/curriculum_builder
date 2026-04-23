"""Shared fixtures for the curriculum_builder test suite."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Make the project root importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def tmp_jobs_db(tmp_path: Path) -> Path:
    """Create a small SQLite jobs.db with realistic schema and a few rows."""
    db_path = tmp_path / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            query TEXT,
            title TEXT,
            employer TEXT,
            description TEXT,
            job_city TEXT,
            job_country TEXT,
            posted_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE skills (
            job_id TEXT,
            skill_name TEXT,
            skill_type TEXT,
            match_score REAL,
            source TEXT
        )
        """
    )
    jobs = [
        ("j1", "data scientist", "DS", "E1", "desc", "NYC", "US", "2024-01-01"),
        ("j2", "data scientist", "DS", "E2", "desc", "NYC", "US", "2024-01-02"),
        ("j3", "data analyst",   "DA", "E3", "desc", "LA",  "US", "2024-01-03"),
    ]
    cur.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", jobs)
    skills = [
        ("j1", "Python",  "tool",  0.9, "ngram"),
        ("j1", "SQL",     "tool",  0.8, "ngram"),
        ("j2", "Python",  "tool",  0.9, "ngram"),
        ("j2", "ML",      "concept", 0.85, "ngram"),
        ("j3", "Excel",   "tool",  0.7, "ngram"),
        ("j3", "SQL",     "tool",  0.8, "ngram"),
    ]
    cur.executemany("INSERT INTO skills VALUES (?,?,?,?,?)", skills)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def tmp_quality_sources(tmp_path: Path) -> Path:
    """Create a minimal quality_assurance/sources tree."""
    root = tmp_path / "sources"
    root.mkdir()
    catalog = {
        "agencies": [
            {
                "agency_code": "ABC",
                "agency_name": "Agency ABC",
                "full_name": "Agency of Better Colleges",
                "metadata_path": "us/ABC",
                "program_scope": ["engineering", "computing"],
            },
            {
                "agency_code": "XYZ",
                "agency_name": "Agency XYZ",
                "full_name": "XYZ Quality Council",
                "metadata_path": "uk/XYZ",
                "program_scope": "business",
            },
        ]
    }
    (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

    abc_dir = root / "us" / "ABC"
    abc_dir.mkdir(parents=True)
    (abc_dir / "quality_definition.json").write_text(
        json.dumps(
            {
                "definition_of_quality": "High quality engineering education.",
                "core_quality_dimensions": ["rigour", "relevance"],
                "curriculum_requirements": ["math core", "capstone"],
                "what_agencies_measure": ["graduation rate"],
                "best_practices_for_programs": ["industry projects"],
            }
        ),
        encoding="utf-8",
    )

    xyz_dir = root / "uk" / "XYZ"
    xyz_dir.mkdir(parents=True)
    # No quality_definition.json for XYZ — tests the missing-file branch
    return root


@pytest.fixture()
def sample_docs_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "mission.txt").write_text(
        "Our mission is to educate and inspire.", encoding="utf-8"
    )
    (folder / "policy.md").write_text(
        "# Policy\nWe value academic integrity.", encoding="utf-8"
    )
    (folder / "data.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    # A totally unsupported file
    (folder / "ignore.xyz").write_text("garbage", encoding="utf-8")
    return folder


class FakeResponse:
    """Stand-in for a requests.Response used by tests that patch requests.post/get."""

    def __init__(self, json_data=None, status_code: int = 200, content: bytes = b"",
                 text: str = "", iter_lines_data: list[bytes] | None = None):
        self._json = json_data or {}
        self.status_code = status_code
        self.content = content
        self.text = text
        self._iter_lines = iter_lines_data or []

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            err = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def json(self):
        return self._json

    def iter_lines(self):
        for line in self._iter_lines:
            yield line

    def iter_content(self, chunk_size=1024):
        yield self.content
