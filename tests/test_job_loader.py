from pathlib import Path

import pandas as pd

from loaders import job_loader


def test_get_available_queries_missing_db(tmp_path: Path):
    assert job_loader.get_available_queries(str(tmp_path / "nope.db")) == []


def test_get_available_queries_returns_sorted_unique(tmp_jobs_db):
    queries = job_loader.get_available_queries(str(tmp_jobs_db))
    assert queries == sorted(set(queries))
    assert "data scientist" in queries
    assert "data analyst" in queries


def test_load_skills_from_db_no_filter(tmp_jobs_db):
    df = job_loader.load_skills_from_db(str(tmp_jobs_db))
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    for col in ("skill_name", "skill_type", "source", "job_count", "mention_rate"):
        assert col in df.columns

    # Python appears on 2 of 3 jobs → 66.7% mention rate
    python_row = df[df["skill_name"] == "Python"].iloc[0]
    assert python_row["job_count"] == 2
    assert python_row["mention_rate"] == 66.7


def test_load_skills_from_db_filtered(tmp_jobs_db):
    df = job_loader.load_skills_from_db(str(tmp_jobs_db), queries=["data scientist"])
    assert not df.empty
    # Excel only appears for data analyst query — should be absent
    assert "Excel" not in df["skill_name"].tolist()
    # SQL for data scientist: 1 of 2 jobs → 50%
    sql_row = df[df["skill_name"] == "SQL"].iloc[0]
    assert sql_row["job_count"] == 1
    assert sql_row["mention_rate"] == 50.0


def test_load_skills_from_db_missing_db(tmp_path: Path):
    assert job_loader.load_skills_from_db(str(tmp_path / "nope.db")).empty


def test_load_skills_from_csv(tmp_path: Path):
    csv = tmp_path / "skills.csv"
    csv.write_text("skill_name,skill_type,job_count\nPython,tool,10\nSQL,tool,8\n", encoding="utf-8")
    df = job_loader.load_skills_from_csv(str(csv))
    assert list(df.columns) == ["skill_name", "skill_type", "job_count"]
    assert len(df) == 2
