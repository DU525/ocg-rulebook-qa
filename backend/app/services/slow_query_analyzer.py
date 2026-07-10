"""
Slow Query Analyzer for OCG Rulebook QA backend.

Features:
- Record slow queries with trace_id, method, path, latency, timestamp, params
- SQLite storage with 7-day TTL
- Statistical analysis (avg/median/P95/P99 latency)
- Top slow endpoints ranking
- Thread-safe operations
"""

import json
import os
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "slow_queries.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
TTL_DAYS = 7


@dataclass
class SlowQueryRecord:
    """Data class representing a recorded slow query."""
    trace_id: str
    method: str
    path: str
    latency: int
    timestamp: float
    params: Dict[str, Any] = field(default_factory=dict)


class SlowQueryAnalyzer:
    """Analyzer for recording and analyzing slow HTTP requests."""

    def __init__(self, db_path: Optional[str] = None, ttl_days: int = TTL_DAYS):
        self.db_path = db_path or str(DB_PATH)
        self.ttl_days = ttl_days
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS slow_queries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trace_id TEXT NOT NULL,
                        method TEXT NOT NULL,
                        path TEXT NOT NULL,
                        latency INTEGER NOT NULL,
                        timestamp REAL NOT NULL,
                        params TEXT DEFAULT '{}'
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_slow_queries_timestamp
                    ON slow_queries(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_slow_queries_path
                    ON slow_queries(path)
                """)
                conn.commit()
            finally:
                conn.close()
        self._cleanup_expired()

    def _cleanup_expired(self):
        cutoff = time.time() - self.ttl_days * 86400
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM slow_queries WHERE timestamp < ?", (cutoff,))
                conn.commit()
            finally:
                conn.close()

    def record_slow_query(
        self,
        trace_id: str,
        method: str,
        path: str,
        latency: int,
        **kwargs,
    ) -> int:
        """Record a slow query into the SQLite store."""
        params = kwargs.get("params", {})
        timestamp = kwargs.get("timestamp", time.time())
        params_json = json.dumps(params, ensure_ascii=False)

        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO slow_queries (trace_id, method, path, latency, timestamp, params)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (trace_id, method, path, latency, timestamp, params_json),
                )
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_slow_requests(
        self, threshold_ms: int = 1000, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get slow requests exceeding the threshold, ordered by latency descending."""
        cutoff = time.time() - self.ttl_days * 86400
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT trace_id, method, path, latency, timestamp, params
                FROM slow_queries
                WHERE latency > ? AND timestamp > ?
                ORDER BY latency DESC
                LIMIT ?
                """,
                (threshold_ms, cutoff, limit),
            ).fetchall()

            results = []
            for row in rows:
                record = {
                    "trace_id": row["trace_id"],
                    "method": row["method"],
                    "path": row["path"],
                    "latency": row["latency"],
                    "timestamp": row["timestamp"],
                    "params": json.loads(row["params"]) if row["params"] else {},
                }
                results.append(record)
            return results
        finally:
            conn.close()

    def get_slow_requests_by_path(
        self, path: str, threshold_ms: int = 1000
    ) -> Dict[str, Any]:
        """Get slow request statistics for a specific path."""
        cutoff = time.time() - self.ttl_days * 86400
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT latency
                FROM slow_queries
                WHERE path = ? AND latency > ? AND timestamp > ?
                ORDER BY latency ASC
                """,
                (path, threshold_ms, cutoff),
            ).fetchall()

            if not rows:
                return {
                    "path": path,
                    "count": 0,
                    "avg_latency": 0,
                    "median_latency": 0,
                    "p95_latency": 0,
                    "p99_latency": 0,
                    "max_latency": 0,
                    "min_latency": 0,
                }

            latencies = [row["latency"] for row in rows]
            count = len(latencies)
            return {
                "path": path,
                "count": count,
                "avg_latency": round(sum(latencies) / count, 2),
                "median_latency": self._percentile(latencies, 50),
                "p95_latency": self._percentile(latencies, 95),
                "p99_latency": self._percentile(latencies, 99),
                "max_latency": max(latencies),
                "min_latency": min(latencies),
            }
        finally:
            conn.close()

    def get_statistics(self, window_hours: int = 24) -> Dict[str, Any]:
        """Get overall slow query statistics within a time window."""
        cutoff = time.time() - window_hours * 3600
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT latency, path
                FROM slow_queries
                WHERE timestamp > ?
                ORDER BY latency ASC
                """,
                (cutoff,),
            ).fetchall()

            if not rows:
                return {
                    "window_hours": window_hours,
                    "total_slow_requests": 0,
                    "avg_latency": 0,
                    "median_latency": 0,
                    "p95_latency": 0,
                    "p99_latency": 0,
                    "unique_paths": 0,
                    "unique_methods": 0,
                }

            latencies = [row["latency"] for row in rows]
            paths = set(row["path"] for row in rows)
            count = len(latencies)

            method_counts = defaultdict(int)
            for row in rows:
                method_counts[row["path"]] += 1

            return {
                "window_hours": window_hours,
                "total_slow_requests": count,
                "avg_latency": round(sum(latencies) / count, 2),
                "median_latency": self._percentile(latencies, 50),
                "p95_latency": self._percentile(latencies, 95),
                "p99_latency": self._percentile(latencies, 99),
                "unique_paths": len(paths),
            }
        finally:
            conn.close()

    def get_top_slow_endpoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top slow endpoints ranked by average latency."""
        cutoff = time.time() - self.ttl_days * 86400
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT path, method, COUNT(*) as count,
                       AVG(latency) as avg_latency,
                       MAX(latency) as max_latency,
                       MIN(latency) as min_latency
                FROM slow_queries
                WHERE timestamp > ?
                GROUP BY path, method
                ORDER BY avg_latency DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()

            results = []
            for row in rows:
                results.append({
                    "path": row["path"],
                    "method": row["method"],
                    "count": row["count"],
                    "avg_latency": round(row["avg_latency"], 2),
                    "max_latency": row["max_latency"],
                    "min_latency": row["min_latency"],
                })
            return results
        finally:
            conn.close()

    @staticmethod
    def _percentile(sorted_latencies: List[int], percentile: float) -> float:
        """Calculate the given percentile from a sorted list of latencies."""
        if not sorted_latencies:
            return 0
        n = len(sorted_latencies)
        idx = (percentile / 100.0) * (n - 1)
        lower = int(idx)
        upper = lower + 1
        if upper >= n:
            return float(sorted_latencies[-1])
        weight = idx - lower
        return round(sorted_latencies[lower] * (1 - weight) + sorted_latencies[upper] * weight, 2)
