import sqlite3
from pathlib import Path

import pandas as pd


def get_available_queries(db_path: str) -> list[str]:
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT DISTINCT query FROM jobs ORDER BY query", conn)
        return df["query"].tolist()
    except Exception:
        return []
    finally:
        conn.close()


def load_skills_from_db(db_path: str, queries: list[str] | None = None) -> pd.DataFrame:
    """Aggregate skill frequencies from jobs.db, optionally filtered by query list."""
    if not Path(db_path).exists():
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    try:
        if queries:
            placeholders = ",".join("?" * len(queries))
            skills_df = pd.read_sql_query(
                f"""
                SELECT s.skill_name, s.skill_type, s.source,
                       COUNT(DISTINCT s.job_id) AS job_count
                FROM skills s
                JOIN jobs j ON s.job_id = j.job_id
                WHERE j.query IN ({placeholders})
                GROUP BY s.skill_name, s.skill_type, s.source
                ORDER BY job_count DESC
                """,
                conn,
                params=queries,
            )
            total_row = pd.read_sql_query(
                f"SELECT COUNT(DISTINCT job_id) AS n FROM jobs WHERE query IN ({placeholders})",
                conn,
                params=queries,
            )
        else:
            skills_df = pd.read_sql_query(
                """
                SELECT s.skill_name, s.skill_type, s.source,
                       COUNT(DISTINCT s.job_id) AS job_count
                FROM skills s
                GROUP BY s.skill_name, s.skill_type, s.source
                ORDER BY job_count DESC
                """,
                conn,
            )
            total_row = pd.read_sql_query(
                "SELECT COUNT(DISTINCT job_id) AS n FROM jobs", conn
            )

        total = int(total_row.iloc[0]["n"]) if not total_row.empty else 0
        if not skills_df.empty and total > 0:
            skills_df["mention_rate"] = (skills_df["job_count"] / total * 100).round(1)
        else:
            skills_df["mention_rate"] = 0.0

        return skills_df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def load_skills_from_csv(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)
