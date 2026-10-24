"""SQLite Cache and Model Call Logging (Hard Rules 6, 7)."""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class ModelCallLog(BaseModel):
    """Structured record of a single model call or cache hit."""
    run_id: str
    case_id: str
    model: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    is_cache_hit: bool = False
    timestamp: float = 0.0


class ExtractionCache:
    """Persistent SQLite cache and telemetry store for LLM/VLM extractions."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            # Extraction response cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extraction_cache (
                    cache_key TEXT PRIMARY KEY,
                    case_id TEXT,
                    evidence_hash TEXT,
                    prompt_version TEXT,
                    model TEXT,
                    response_json TEXT,
                    created_at REAL
                );
            """)
            # Call telemetry & cost log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_call_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    case_id TEXT,
                    model TEXT,
                    prompt_version TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    latency_ms REAL,
                    estimated_cost_usd REAL,
                    is_cache_hit INTEGER,
                    timestamp REAL
                );
            """)
            conn.commit()

    @staticmethod
    def generate_cache_key(case_id: str, evidence_hash: str, prompt_version: str, model: str) -> str:
        """Cache key strictly keyed by (case_id, evidence hash, prompt version, model) per Hard Rule 6."""
        return f"{case_id}::{evidence_hash}::{prompt_version}::{model}"

    def get(self, case_id: str, evidence_hash: str, prompt_version: str, model: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached extraction JSON if present."""
        key = self.generate_cache_key(case_id, evidence_hash, prompt_version, model)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT response_json FROM extraction_cache WHERE cache_key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["response_json"])
        return None

    def put(
        self,
        case_id: str,
        evidence_hash: str,
        prompt_version: str,
        model: str,
        response_dict: Dict[str, Any],
    ):
        """Store extraction JSON in cache."""
        key = self.generate_cache_key(case_id, evidence_hash, prompt_version, model)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO extraction_cache 
                (cache_key, case_id, evidence_hash, prompt_version, model, response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    case_id,
                    evidence_hash,
                    prompt_version,
                    model,
                    json.dumps(response_dict),
                    time.time(),
                ),
            )
            conn.commit()

    def log_call(self, log_entry: ModelCallLog):
        """Record model telemetry per Hard Rule 7."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO model_call_logs 
                (run_id, case_id, model, prompt_version, input_tokens, output_tokens, latency_ms, estimated_cost_usd, is_cache_hit, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_entry.run_id,
                    log_entry.case_id,
                    log_entry.model,
                    log_entry.prompt_version,
                    log_entry.input_tokens,
                    log_entry.output_tokens,
                    log_entry.latency_ms,
                    log_entry.estimated_cost_usd,
                    1 if log_entry.is_cache_hit else 0,
                    log_entry.timestamp or time.time(),
                ),
            )
            conn.commit()

    def get_run_summary(self, run_id: str) -> Dict[str, Any]:
        """Aggregate token usage, total cost, and call counts for a run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    model,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN is_cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                    SUM(estimated_cost_usd) as total_cost_usd
                FROM model_call_logs
                WHERE run_id = ?
                GROUP BY model
                """,
                (run_id,),
            )
            rows = cursor.fetchall()
            models_summary = []
            total_run_cost = 0.0
            for r in rows:
                cost = r["total_cost_usd"] or 0.0
                total_run_cost += cost
                models_summary.append({
                    "model": r["model"],
                    "input_tokens": r["total_input_tokens"] or 0,
                    "output_tokens": r["total_output_tokens"] or 0,
                    "total_calls": r["total_calls"],
                    "cache_hits": r["cache_hits"],
                    "cost_usd": round(cost, 6),
                })

            return {
                "run_id": run_id,
                "total_cost_usd": round(total_run_cost, 6),
                "models": models_summary,
            }
