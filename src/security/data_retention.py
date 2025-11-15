"""
Module for managing data retention policies and automated cleanup.

Implements:
- Retention period configuration by data type
- Automated deletion of expired data
- Soft delete (archiving) before hard delete
- Audit trail of deletions
- Compliance with Ley 19.628 (Chile) and GDPR

Retention schedule (configurable via settings):
- Session data: 30 days
- Analytics data: 90 days
- User activity logs: 180 days
- Auth logs (security): 365 days
- Deleted user data: 30 days (before permanent deletion)
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
import json
import logging

logger = logging.getLogger(__name__)


class DataType(Enum):
    """Types of data with retention policies."""
    SESSION = "session"
    ANALYTICS = "analytics"
    ACTIVITY_LOG = "activity_log"
    AUTH_LOG = "auth_log"
    USER_DATA = "user_data"
    DELETED_USER = "deleted_user"
    CHAT_HISTORY = "chat_history"
    TEMP_FILES = "temp_files"


@dataclass
class RetentionPolicy:
    """Configuration for data retention."""
    data_type: DataType
    retention_days: int
    soft_delete_before_hard: bool = True
    soft_delete_days: int = 7
    archive_before_delete: bool = False
    archive_path: Optional[Path] = None

    def retention_until(self) -> datetime:
        """Calculate the date until which data should be retained."""
        return datetime.utcnow() - timedelta(days=self.retention_days)

    def soft_delete_until(self) -> datetime:
        """Calculate the date for soft delete (before hard delete)."""
        return datetime.utcnow() - timedelta(
            days=self.retention_days + self.soft_delete_days
        )


@dataclass
class DeletionAudit:
    """Record of a deletion operation."""
    deletion_id: str
    timestamp: datetime
    data_type: DataType
    records_deleted: int
    records_archived: int
    user_id: Optional[str]
    reason: str
    details: Dict


class DataRetentionManager:
    """
    Manages data retention policies and automated cleanup.

    Features:
    - Multiple retention policies
    - Soft delete (mark as deleted) before hard delete
    - Archiving before deletion
    - Audit trail of deletions
    - Compliance logging
    """

    # Default retention policies (in days)
    DEFAULT_POLICIES: Dict[DataType, int] = {
        DataType.SESSION: 30,
        DataType.ANALYTICS: 90,
        DataType.ACTIVITY_LOG: 180,
        DataType.AUTH_LOG: 365,
        DataType.USER_DATA: 2555,  # 7 years (legal hold)
        DataType.DELETED_USER: 30,  # 30 days after user deletion
        DataType.CHAT_HISTORY: 365,
        DataType.TEMP_FILES: 7,
    }

    def __init__(self, audit_db_path: Path):
        """
        Initialize data retention manager.

        Args:
            audit_db_path: Path to audit database
        """
        self.audit_db_path = audit_db_path
        self.policies: Dict[DataType, RetentionPolicy] = {}
        self._init_audit_db()
        self._setup_default_policies()

    def _init_audit_db(self) -> None:
        """Initialize audit database for deletion records."""
        self.audit_db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.audit_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deletion_audits (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    records_deleted INTEGER,
                    records_archived INTEGER,
                    user_id TEXT,
                    reason TEXT,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _setup_default_policies(self) -> None:
        """Set up default retention policies."""
        for data_type, days in self.DEFAULT_POLICIES.items():
            self.set_policy(
                data_type,
                retention_days=days,
                soft_delete_before_hard=True
            )

    def set_policy(
        self,
        data_type: DataType,
        retention_days: int,
        soft_delete_before_hard: bool = True,
        soft_delete_days: int = 7,
        archive_before_delete: bool = False,
        archive_path: Optional[Path] = None
    ) -> None:
        """
        Set retention policy for a data type.

        Args:
            data_type: Type of data
            retention_days: Days to retain data
            soft_delete_before_hard: Whether to soft delete before hard delete
            soft_delete_days: Days to keep soft-deleted data
            archive_before_delete: Whether to archive before deleting
            archive_path: Path to archive files
        """
        policy = RetentionPolicy(
            data_type=data_type,
            retention_days=retention_days,
            soft_delete_before_hard=soft_delete_before_hard,
            soft_delete_days=soft_delete_days,
            archive_before_delete=archive_before_delete,
            archive_path=archive_path
        )
        self.policies[data_type] = policy
        logger.info(f"Policy set for {data_type.value}: {retention_days} days")

    def get_policy(self, data_type: DataType) -> Optional[RetentionPolicy]:
        """Get retention policy for data type."""
        return self.policies.get(data_type)

    def cleanup_sessions(self, db_path: Path) -> Tuple[int, int]:
        """
        Delete old session data.

        Args:
            db_path: Path to sessions database

        Returns:
            Tuple of (soft_deleted_count, hard_deleted_count)
        """
        policy = self.get_policy(DataType.SESSION)
        if not policy:
            return 0, 0

        return self._cleanup_database(
            db_path,
            table_name="sessions",
            date_column="created_at",
            policy=policy,
            data_type=DataType.SESSION
        )

    def cleanup_analytics(self, db_path: Path) -> Tuple[int, int]:
        """Delete old analytics data."""
        policy = self.get_policy(DataType.ANALYTICS)
        if not policy:
            return 0, 0

        return self._cleanup_database(
            db_path,
            table_name="metrics",
            date_column="timestamp",
            policy=policy,
            data_type=DataType.ANALYTICS
        )

    def cleanup_activity_logs(self, db_path: Path) -> Tuple[int, int]:
        """Delete old activity logs."""
        policy = self.get_policy(DataType.ACTIVITY_LOG)
        if not policy:
            return 0, 0

        return self._cleanup_database(
            db_path,
            table_name="activity_logs",
            date_column="timestamp",
            policy=policy,
            data_type=DataType.ACTIVITY_LOG
        )

    def cleanup_auth_logs(self, db_path: Path) -> Tuple[int, int]:
        """Delete old auth logs (keep for compliance/auditing)."""
        policy = self.get_policy(DataType.AUTH_LOG)
        if not policy:
            return 0, 0

        # For auth logs, only do soft delete - keep for audit
        return self._cleanup_database(
            db_path,
            table_name="auth_logs",
            date_column="timestamp",
            policy=policy,
            data_type=DataType.AUTH_LOG,
            soft_delete_only=True
        )

    def cleanup_deleted_users(self, db_path: Path) -> Tuple[int, int]:
        """Permanently delete user data 30 days after account deletion."""
        policy = self.get_policy(DataType.DELETED_USER)
        if not policy:
            return 0, 0

        return self._cleanup_database(
            db_path,
            table_name="users",
            date_column="deleted_at",
            policy=policy,
            data_type=DataType.DELETED_USER,
            where_clause="deleted_at IS NOT NULL"
        )

    def _cleanup_database(
        self,
        db_path: Path,
        table_name: str,
        date_column: str,
        policy: RetentionPolicy,
        data_type: DataType,
        where_clause: Optional[str] = None,
        soft_delete_only: bool = False
    ) -> Tuple[int, int]:
        """
        Generic database cleanup implementation.

        Args:
            db_path: Path to database
            table_name: Table to clean
            date_column: Column with timestamp
            policy: Retention policy
            data_type: Type of data being deleted
            where_clause: Additional WHERE conditions
            soft_delete_only: Only soft delete, don't hard delete

        Returns:
            Tuple of (soft_deleted_count, hard_deleted_count)
        """
        if not db_path.exists():
            return 0, 0

        soft_deleted = 0
        hard_deleted = 0

        try:
            with sqlite3.connect(db_path) as conn:
                # Soft delete: mark as deleted without removing
                if policy.soft_delete_before_hard and not soft_delete_only:
                    retention_date = policy.retention_until().isoformat()
                    where = f"{date_column} < ?"
                    if where_clause:
                        where = f"{where} AND {where_clause}"

                    cursor = conn.execute(
                        f"SELECT COUNT(*) FROM {table_name} WHERE {where}",
                        (retention_date,)
                    )
                    soft_deleted = cursor.fetchone()[0]

                    if soft_deleted > 0:
                        if "deleted_at" in self._get_table_columns(conn, table_name):
                            conn.execute(
                                f"UPDATE {table_name} SET deleted_at = ? WHERE {where}",
                                (datetime.utcnow().isoformat(), retention_date)
                            )
                        conn.commit()

                # Hard delete: permanently remove data
                if not soft_delete_only:
                    soft_delete_date = policy.soft_delete_until().isoformat()
                    where = f"{date_column} < ?"
                    if where_clause:
                        where = f"{where} AND {where_clause}"

                    cursor = conn.execute(
                        f"SELECT COUNT(*) FROM {table_name} WHERE {where}",
                        (soft_delete_date,)
                    )
                    hard_deleted = cursor.fetchone()[0]

                    if hard_deleted > 0:
                        conn.execute(
                            f"DELETE FROM {table_name} WHERE {where}",
                            (soft_delete_date,)
                        )
                        conn.commit()

                logger.info(
                    f"Cleanup {data_type.value}: "
                    f"soft_deleted={soft_deleted}, hard_deleted={hard_deleted}"
                )

        except Exception as e:
            logger.error(f"Error cleaning {data_type.value}: {e}")

        return soft_deleted, hard_deleted

    def _get_table_columns(self, conn: sqlite3.Connection, table_name: str) -> List[str]:
        """Get list of columns in a table."""
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    def cleanup_temp_files(self, temp_dir: Path) -> int:
        """
        Delete old temporary files.

        Args:
            temp_dir: Directory containing temporary files

        Returns:
            Number of files deleted
        """
        if not temp_dir.exists():
            return 0

        policy = self.get_policy(DataType.TEMP_FILES)
        if not policy:
            return 0

        deleted_count = 0
        retention_date = policy.retention_until()

        try:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    file_age = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_age < retention_date:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted temp file: {file_path}")

            logger.info(f"Cleanup temp files: deleted={deleted_count}")

        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")

        return deleted_count

    def record_deletion(
        self,
        data_type: DataType,
        records_deleted: int,
        records_archived: int = 0,
        user_id: Optional[str] = None,
        reason: str = "retention_policy",
        details: Optional[Dict] = None
    ) -> str:
        """
        Record a deletion in the audit trail.

        Args:
            data_type: Type of data deleted
            records_deleted: Number of records deleted
            records_archived: Number of records archived
            user_id: User who requested deletion (if applicable)
            reason: Reason for deletion
            details: Additional details

        Returns:
            Deletion audit ID
        """
        import uuid
        deletion_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        audit = DeletionAudit(
            deletion_id=deletion_id,
            timestamp=datetime.utcnow(),
            data_type=data_type,
            records_deleted=records_deleted,
            records_archived=records_archived,
            user_id=user_id,
            reason=reason,
            details=details or {}
        )

        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                conn.execute("""
                    INSERT INTO deletion_audits
                    (id, timestamp, data_type, records_deleted, records_archived,
                     user_id, reason, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    audit.deletion_id,
                    audit.timestamp.isoformat(),
                    audit.data_type.value,
                    audit.records_deleted,
                    audit.records_archived,
                    audit.user_id,
                    audit.reason,
                    json.dumps(audit.details)
                ))
                conn.commit()

            logger.info(f"Recorded deletion: {deletion_id} ({data_type.value})")

        except Exception as e:
            logger.error(f"Error recording deletion: {e}")

        return deletion_id

    def get_deletion_history(
        self,
        data_type: Optional[DataType] = None,
        days: int = 90
    ) -> List[Dict]:
        """
        Get deletion audit history.

        Args:
            data_type: Filter by data type (optional)
            days: Number of days to look back

        Returns:
            List of deletion records
        """
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM deletion_audits WHERE created_at > ?"
                params = [(datetime.utcnow() - timedelta(days=days)).isoformat()]

                if data_type:
                    query += " AND data_type = ?"
                    params.append(data_type.value)

                query += " ORDER BY created_at DESC"

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error retrieving deletion history: {e}")
            return []

    def run_all_cleanup(
        self,
        sessions_db: Path,
        analytics_db: Path,
        users_db: Path,
        temp_dir: Path
    ) -> Dict[str, Tuple[int, int]]:
        """
        Run all cleanup operations.

        Args:
            sessions_db: Path to sessions database
            analytics_db: Path to analytics database
            users_db: Path to users database
            temp_dir: Path to temporary files directory

        Returns:
            Dictionary with cleanup results by data type
        """
        results = {}

        results["sessions"] = self.cleanup_sessions(sessions_db)
        results["analytics"] = self.cleanup_analytics(analytics_db)
        results["deleted_users"] = self.cleanup_deleted_users(users_db)
        results["temp_files"] = (self.cleanup_temp_files(temp_dir), 0)

        logger.info(f"Completed all cleanup operations: {results}")
        return results
