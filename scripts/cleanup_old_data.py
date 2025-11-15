#!/usr/bin/env python
"""
Script for automated data cleanup based on retention policies.

Usage:
    python scripts/cleanup_old_data.py              # Run with default settings
    python scripts/cleanup_old_data.py --dry-run    # Preview what would be deleted
    python scripts/cleanup_old_data.py --type sessions  # Clean only sessions
    python scripts/cleanup_old_data.py --config config/retention.json  # Custom config

Compliance:
- Ley 19.628 (Chile): Protección de datos personales
- GDPR (EU): Data protection regulation
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from src.security.data_retention import DataRetentionManager, DataType
from src.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


def load_retention_config(config_path: Path) -> Dict[DataType, int]:
    """Load retention configuration from JSON file."""
    if not config_path.exists():
        logger.info(f"Config file not found: {config_path}, using defaults")
        return {}

    with open(config_path) as f:
        config = json.load(f)

    retention_config = {}
    for key, days in config.items():
        try:
            data_type = DataType(key.lower())
            retention_config[data_type] = days
        except ValueError:
            logger.warning(f"Unknown data type in config: {key}")

    return retention_config


def apply_custom_config(
    manager: DataRetentionManager,
    config: Dict[DataType, int]
) -> None:
    """Apply custom retention configuration."""
    for data_type, retention_days in config.items():
        manager.set_policy(data_type, retention_days=retention_days)
        logger.info(f"Set policy {data_type.value}: {retention_days} days")


def run_cleanup(
    manager: DataRetentionManager,
    settings: Any,
    dry_run: bool = False,
    data_type: str = None
) -> Dict[str, Any]:
    """
    Run cleanup operations.

    Args:
        manager: DataRetentionManager instance
        settings: Application settings
        dry_run: If True, don't actually delete anything
        data_type: If specified, clean only this type

    Returns:
        Dictionary with cleanup results
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "cleanups": {},
        "total_deleted": 0,
        "total_archived": 0
    }

    logger.info(f"Starting cleanup {'(DRY RUN)' if dry_run else ''}")

    # Sessions cleanup
    if not data_type or data_type == DataType.SESSION.value:
        logger.info("Cleaning up old sessions...")
        try:
            soft_del, hard_del = manager.cleanup_sessions(settings.sessions_db_path)
            if not dry_run:
                manager.record_deletion(
                    DataType.SESSION,
                    soft_del + hard_del,
                    user_id=None,
                    reason="retention_policy"
                )
            results["cleanups"]["sessions"] = {"soft_deleted": soft_del, "hard_deleted": hard_del}
            results["total_deleted"] += soft_del + hard_del
            logger.info(f"Sessions: deleted {soft_del + hard_del} records")
        except Exception as e:
            logger.error(f"Error cleaning sessions: {e}")
            results["cleanups"]["sessions"] = {"error": str(e)}

    # Analytics cleanup
    if not data_type or data_type == DataType.ANALYTICS.value:
        logger.info("Cleaning up old analytics data...")
        try:
            soft_del, hard_del = manager.cleanup_analytics(settings.analytics_db_path)
            if not dry_run:
                manager.record_deletion(
                    DataType.ANALYTICS,
                    soft_del + hard_del,
                    user_id=None,
                    reason="retention_policy"
                )
            results["cleanups"]["analytics"] = {"soft_deleted": soft_del, "hard_deleted": hard_del}
            results["total_deleted"] += soft_del + hard_del
            logger.info(f"Analytics: deleted {soft_del + hard_del} records")
        except Exception as e:
            logger.error(f"Error cleaning analytics: {e}")
            results["cleanups"]["analytics"] = {"error": str(e)}

    # Activity logs cleanup
    if not data_type or data_type == DataType.ACTIVITY_LOG.value:
        logger.info("Cleaning up old activity logs...")
        try:
            soft_del, hard_del = manager.cleanup_activity_logs(settings.analytics_db_path)
            if not dry_run:
                manager.record_deletion(
                    DataType.ACTIVITY_LOG,
                    soft_del + hard_del,
                    user_id=None,
                    reason="retention_policy"
                )
            results["cleanups"]["activity_logs"] = {"soft_deleted": soft_del, "hard_deleted": hard_del}
            results["total_deleted"] += soft_del + hard_del
            logger.info(f"Activity logs: deleted {soft_del + hard_del} records")
        except Exception as e:
            logger.error(f"Error cleaning activity logs: {e}")
            results["cleanups"]["activity_logs"] = {"error": str(e)}

    # Deleted users permanent deletion
    if not data_type or data_type == DataType.DELETED_USER.value:
        logger.info("Permanently deleting user data scheduled for deletion...")
        try:
            soft_del, hard_del = manager.cleanup_deleted_users(settings.auth_db_path)
            if not dry_run:
                manager.record_deletion(
                    DataType.DELETED_USER,
                    hard_del,
                    user_id=None,
                    reason="retention_policy"
                )
            results["cleanups"]["deleted_users"] = {"soft_deleted": soft_del, "hard_deleted": hard_del}
            results["total_deleted"] += hard_del
            logger.info(f"Deleted users: permanently deleted {hard_del} records")
        except Exception as e:
            logger.error(f"Error cleaning deleted users: {e}")
            results["cleanups"]["deleted_users"] = {"error": str(e)}

    # Temporary files cleanup
    if not data_type or data_type == DataType.TEMP_FILES.value:
        logger.info("Cleaning up temporary files...")
        try:
            temp_dir = Path("data/temp")
            deleted = manager.cleanup_temp_files(temp_dir)
            if not dry_run:
                manager.record_deletion(
                    DataType.TEMP_FILES,
                    deleted,
                    user_id=None,
                    reason="retention_policy"
                )
            results["cleanups"]["temp_files"] = {"deleted": deleted}
            results["total_deleted"] += deleted
            logger.info(f"Temp files: deleted {deleted} files")
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
            results["cleanups"]["temp_files"] = {"error": str(e)}

    logger.info(f"Cleanup completed: {results['total_deleted']} records deleted")
    return results


def print_cleanup_report(results: Dict[str, Any]) -> None:
    """Print cleanup results in a readable format."""
    print("\n" + "=" * 60)
    print(f"CLEANUP REPORT - {results['timestamp']}")
    print("=" * 60)

    if results['dry_run']:
        print("⚠️  DRY RUN - No data was actually deleted")
    print()

    for cleanup_type, cleanup_result in results['cleanups'].items():
        print(f"\n{cleanup_type.upper()}:")
        if isinstance(cleanup_result, dict) and "error" in cleanup_result:
            print(f"  ❌ Error: {cleanup_result['error']}")
        else:
            for key, value in cleanup_result.items():
                print(f"  - {key}: {value}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL DELETED: {results['total_deleted']}")
    print("=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up old data based on retention policies"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview cleanup without deleting data"
    )
    parser.add_argument(
        "--type",
        dest="data_type",
        help=f"Clean only specific type: {', '.join(dt.value for dt in DataType)}"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to custom retention configuration JSON"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    args = parser.parse_args()

    # Setup logging
    import logging as stdlib_logging
    log_level = getattr(stdlib_logging, args.log_level)
    setup_logging(log_level=log_level)

    logger.info(f"org-assistant cleanup script started")
    logger.info(f"Arguments: dry_run={args.dry_run}, type={args.data_type}, config={args.config}")

    # Get settings
    settings = get_settings()

    # Create retention manager
    audit_db = Path("data/audit/retention_audit.db")
    manager = DataRetentionManager(audit_db)

    # Apply custom configuration if provided
    if args.config:
        logger.info(f"Loading custom retention config: {args.config}")
        custom_config = load_retention_config(args.config)
        if custom_config:
            apply_custom_config(manager, custom_config)

    # Run cleanup
    results = run_cleanup(
        manager,
        settings,
        dry_run=args.dry_run,
        data_type=args.data_type
    )

    # Print results
    print_cleanup_report(results)

    # Save results to file
    results_file = Path("data/audit/cleanup_results.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {results_file}")

    return 0 if all(
        "error" not in v for v in results["cleanups"].values() if isinstance(v, dict)
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
