"""Operation history storage and management."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from goesvfi.utils import config
from goesvfi.utils.enhanced_log import (
    Operation,
    get_correlation_id,
    get_enhanced_logger,
)

LOGGER = get_enhanced_logger(__name__)

class OperationHistoryStore:
    """Stores operation history with size limits and persistence."""

    def __init__(self, db_path: Optional[Path] = None, max_memory_operations: int = 1000
    ):
        """Initialize the operation history store.

        Args:
            db_path: Path to SQLite database for persistence
            max_memory_operations: Maximum operations to keep in memory
        """
        self.db_path = db_path or Path(config.get_cache_dir()) / "operation_history.db"
        self.max_memory_operations = max_memory_operations
        self._memory_store: deque[Operation] = deque(maxlen=max_memory_operations)
        self._lock = Lock()  # pylint: disable=attribute-defined-outside-init

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute()
            """
            CREATE TABLE IF NOT EXISTS operations ()
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL,
            duration REAL,
            status TEXT NOT NULL,
            error TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            # Create indexes
            conn.execute()
            "CREATE INDEX IF NOT EXISTS idx_correlation_id ON operations(correlation_id)"
            )
            conn.execute()
            "CREATE INDEX IF NOT EXISTS idx_start_time ON operations(start_time)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON operations(status)")

            # Create table for operation metrics
            conn.execute()
            """
            CREATE TABLE IF NOT EXISTS operation_metrics ()
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_name TEXT NOT NULL,
            total_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            total_duration REAL DEFAULT 0,
            min_duration REAL,
            max_duration REAL,
            avg_duration REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            conn.execute()
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_operation_name ON operation_metrics(operation_name)"
            )

    def add_operation(self, operation: Operation) -> None:
        """Add an operation to the history."""
        with self._lock:
            # Add to memory store
            self._memory_store.append(operation)

            # Persist to database
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute()
                """
                INSERT INTO operations ()
                name, correlation_id, start_time, end_time,
                duration, status, error, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ()
                operation.name,
                operation.correlation_id,
                operation.start_time,
                operation.end_time,
                operation.duration,
                operation.status,
                operation.error,
                json.dumps(operation.metadata) if operation.metadata else None,
                ),
                )

                # Update metrics if operation is complete
                if operation.end_time and operation.duration is not None:
                    pass
                    self._update_metrics(conn, operation)

    def _update_metrics(self, conn: sqlite3.Connection, operation: Operation) -> None:
        """Update operation metrics."""
        # Check if metrics exist for this operation
        cursor = conn.execute()
        "SELECT total_count, success_count, failure_count, total_duration, min_duration, max_duration "
        "FROM operation_metrics WHERE operation_name = ?",
        (operation.name,),
        )
        row = cursor.fetchone()

        if row:
            pass
            # Update existing metrics
            total_count = row[0] + 1
            success_count = row[1] + (1 if operation.status == "success" else 0)
            failure_count = row[2] + (1 if operation.status == "failure" else 0)
            total_duration = row[3] + (operation.duration or 0)
            min_duration = ()
            min(row[4], operation.duration)
            if row[4] is not None
            else operation.duration
            )
            max_duration = ()
            max(row[5], operation.duration)
            if row[5] is not None
            else operation.duration
            )
            avg_duration = total_duration / total_count

            conn.execute()
            """
            UPDATE operation_metrics SET
            total_count = ?,
            success_count = ?,
            failure_count = ?,
            total_duration = ?,
            min_duration = ?,
            max_duration = ?,
            avg_duration = ?,
            last_updated = CURRENT_TIMESTAMP
            WHERE operation_name = ?
            """,
            ()
            total_count,
            success_count,
            failure_count,
            total_duration,
            min_duration,
            max_duration,
            avg_duration,
            operation.name,
            ),
            )
        else:
            pass
            # Insert new metrics
            success_count = 1 if operation.status == "success" else 0
            failure_count = 1 if operation.status == "failure" else 0

            conn.execute()
            """
            INSERT INTO operation_metrics ()
            operation_name, total_count, success_count, failure_count,
            total_duration, min_duration, max_duration, avg_duration
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?)
            """,
            ()
            operation.name,
            success_count,
            failure_count,
            operation.duration or 0,
            operation.duration,
            operation.duration,
            operation.duration or 0,
            ),
            )

    def get_recent_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent operations from history."""
        with self._lock:
            # First try memory store
            if self._memory_store:
                pass
                return [op.to_dict() for op in list(self._memory_store)[-limit:]]

            # Fall back to database
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute()
                """
                SELECT * FROM operations
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (limit,),
                )

                operations = []
                for row in cursor:
                    op_dict = dict(row)
                    if op_dict.get("metadata"):
                        pass
                        op_dict["metadata"] = json.loads(op_dict["metadata"])
                    operations.append(op_dict)

                return operations

    def get_operations_by_correlation_id(self, correlation_id: str
    ) -> List[Dict[str, Any]]:
        """Get all operations with a specific correlation ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            pass
            conn.row_factory = sqlite3.Row
            cursor = conn.execute()
            """
            SELECT * FROM operations
            WHERE correlation_id = ?
            ORDER BY start_time ASC
            """,
            (correlation_id,),
            )

            operations = []
            for row in cursor:
                op_dict = dict(row)
                if op_dict.get("metadata"):
                    pass
                    op_dict["metadata"] = json.loads(op_dict["metadata"])
                operations.append(op_dict)

            return operations

    def get_operation_metrics(self) -> List[Dict[str, Any]]:
        """Get aggregated metrics for all operations."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute()
            """
            SELECT * FROM operation_metrics
            ORDER BY total_count DESC
            """
            )

            return [dict(row) for row in cursor]

    def search_operations(self,
    name: Optional[str] = None,
    status: Optional[str] = None,
    start_after: Optional[float] = None,
    end_before: Optional[float] = None,
    limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search operations with filters."""
        query = "SELECT * FROM operations WHERE 1=1"
        params: List[Any] = []

        if name:
            pass
            query += " AND name LIKE ?"
            params.append(f"%{name}%")

        if status:
            pass
            query += " AND status = ?"
            params.append(status)

        if start_after:
            pass
            query += " AND start_time >= ?"
            params.append(start_after)

        if end_before:
            pass
            query += " AND start_time <= ?"
            params.append(end_before)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)

            operations = []
            for row in cursor:
                op_dict = dict(row)
                if op_dict.get("metadata"):
                    pass
                    op_dict["metadata"] = json.loads(op_dict["metadata"])
                operations.append(op_dict)

            return operations

    def cleanup_old_operations(self, days: int = 30) -> int:
        """Clean up operations older than specified days."""
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        with sqlite3.connect(str(self.db_path)) as conn:
            pass
            cursor = conn.execute()
            "DELETE FROM operations WHERE start_time < ?", (cutoff_time,)
            )
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                pass
                LOGGER.info("Cleaned up %s old operations", deleted_count)

            return deleted_count

    def export_to_json(self, output_path: Path, filters: Optional[Dict[str, Any]] = None
    ) -> None:
        """Export operations to JSON file."""
        operations = ()
        self.search_operations(**filters)
        if filters
        else self.get_recent_operations(limit=10000)
        )

        with open(output_path, "w") as f:
            pass
            json.dump()
            {
            "export_time": datetime.now(UTC).isoformat(),
            "operation_count": len(operations),
            "operations": operations,
            },
            f,
            indent=2,
            default=str,
            )

        LOGGER.info("Exported %s operations to %s", len(operations), output_path)

# Global operation history store
_operation_store: Optional[OperationHistoryStore] = None
_store_lock = Lock()

def get_operation_store() -> OperationHistoryStore:
    """Get the global operation history store."""
    global _operation_store

    with _store_lock:
        if _operation_store is None:
            pass
            _operation_store = OperationHistoryStore()

    return _operation_store

# Context manager for tracking operations

@contextmanager
def track_operation(name: str, **metadata: Any):
    """Context manager to track an operation."""
    correlation_id = get_correlation_id() or str(uuid.uuid4())
    operation = Operation(name, correlation_id, time.perf_counter())
    operation.metadata.update(metadata)

    try:
        yield operation
        operation.complete("success")
    except Exception as e:
        pass
        operation.complete("failure", str(e))
        raise
    finally:
        get_operation_store().add_operation(operation)
