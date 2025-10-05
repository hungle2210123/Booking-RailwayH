#!/usr/bin/env python3
"""
🔄 Hotel Booking System - Sync Manager
Command-line tool for managing database synchronization
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import sync service
from core.auto_sync_service import auto_sync_service

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")

def print_status(status):
    """Print formatted sync status"""
    print(f"📊 Sync Status")
    print(f"   Local records:   {status.local_count}")
    print(f"   Railway records: {status.railway_count}")
    print(f"   Sync needed:     {'YES ⚠️' if status.sync_needed else 'NO ✅'}")
    print(f"   Direction:       {status.recommended_direction}")

    if status.differences:
        print(f"\n📋 Differences by table:")
        for table, diff in status.differences.items():
            print(f"   {table:20} Local: {diff['local']:4d} | Railway: {diff['railway']:4d} | Diff: {diff['difference']:4d}")

def cmd_status(args):
    """Show current sync status"""
    print_header("Database Sync Status")

    status = auto_sync_service.analyze_sync_status(force_refresh=args.force)
    print_status(status)

    if status.last_sync_time:
        print(f"\n⏰ Last check: {status.last_sync_time}")

def cmd_sync_local_to_railway(args):
    """Sync from local to Railway"""
    print_header("Sync: Local → Railway")

    # Show status first
    status = auto_sync_service.analyze_sync_status(force_refresh=True)
    print_status(status)

    if not args.force and not status.sync_needed:
        print("\n✅ Databases are already in sync!")
        return

    # Confirm if not forced
    if not args.force and not args.yes:
        response = input(f"\n⚠️  This will sync {status.local_count - status.railway_count} records to Railway. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            return

    print("\n🚀 Starting sync...")
    result = auto_sync_service.sync_local_to_railway()

    if result['success']:
        print(f"\n✅ Sync completed successfully!")
        print(f"   Total records processed: {result['total_records']}")
        print(f"   Successful tables: {', '.join(result['successful_tables'])}")
        if result['failed_tables']:
            print(f"   Failed tables: {', '.join(result['failed_tables'])}")
    else:
        print(f"\n❌ Sync failed: {result['message']}")
        if result.get('failed_tables'):
            print(f"   Failed tables: {', '.join(result['failed_tables'])}")

def cmd_sync_railway_to_local(args):
    """Sync from Railway to local"""
    print_header("Sync: Railway → Local")

    # Show status first
    status = auto_sync_service.analyze_sync_status(force_refresh=True)
    print_status(status)

    if not args.force and not status.sync_needed:
        print("\n✅ Databases are already in sync!")
        return

    # Confirm if not forced
    if not args.force and not args.yes:
        response = input(f"\n⚠️  This will sync {status.railway_count - status.local_count} records to local. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            return

    print("\n🚀 Starting sync...")
    result = auto_sync_service.sync_railway_to_local()

    if result['success']:
        print(f"\n✅ Sync completed successfully!")
        print(f"   Total records processed: {result['total_records']}")
        print(f"   Successful tables: {', '.join(result['successful_tables'])}")
        if result['failed_tables']:
            print(f"   Failed tables: {', '.join(result['failed_tables'])}")
    else:
        print(f"\n❌ Sync failed: {result['message']}")
        if result.get('failed_tables'):
            print(f"   Failed tables: {', '.join(result['failed_tables'])}")

def cmd_smart_sync(args):
    """Perform smart bidirectional sync"""
    print_header("Smart Sync (Bidirectional)")

    # Analyze and sync
    print("🔍 Analyzing databases...")
    result = auto_sync_service.perform_smart_sync()

    if result['success']:
        print(f"\n✅ Smart sync completed!")
        print(f"\n📋 Actions taken:")
        for action in result['actions_taken']:
            print(f"   • {action}")
    else:
        print(f"\n❌ Smart sync failed")
        print(f"   Actions taken:")
        for action in result['actions_taken']:
            print(f"   • {action}")

def cmd_history(args):
    """Show sync history"""
    print_header("Sync History")

    history = auto_sync_service.get_sync_history_from_database(limit=args.limit)

    if not history:
        print("📭 No sync history found")
        return

    print(f"📜 Last {len(history)} sync operations:\n")

    for i, entry in enumerate(history, 1):
        timestamp = entry['timestamp']
        success_icon = "✅" if entry['success'] else "❌"

        print(f"{i}. {success_icon} {timestamp}")
        print(f"   Direction: {entry['recommended_direction']}")
        print(f"   Records: Local={entry['local_count']}, Railway={entry['railway_count']}")
        print(f"   Processed: {entry['total_records']} records")

        if entry.get('successful_tables'):
            print(f"   Success: {', '.join(entry['successful_tables'])}")
        if entry.get('failed_tables'):
            print(f"   Failed: {', '.join(entry['failed_tables'])}")
        print()

def cmd_test_connections(args):
    """Test database connections"""
    print_header("Database Connection Test")

    print("🔌 Testing local PostgreSQL...")
    try:
        local_counts = auto_sync_service.get_table_counts(auto_sync_service.local_engine)
        print(f"   ✅ Local connected: {sum(local_counts.values())} total records")
        for table, count in local_counts.items():
            print(f"      {table}: {count}")
    except Exception as e:
        print(f"   ❌ Local connection failed: {e}")

    print("\n🔌 Testing Railway PostgreSQL...")
    try:
        railway_counts = auto_sync_service.get_table_counts(auto_sync_service.railway_engine)
        print(f"   ✅ Railway connected: {sum(railway_counts.values())} total records")
        for table, count in railway_counts.items():
            print(f"      {table}: {count}")
    except Exception as e:
        print(f"   ❌ Railway connection failed: {e}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Hotel Booking System - Database Sync Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                    # Check sync status
  %(prog)s push                      # Sync local → Railway
  %(prog)s pull                      # Sync Railway → local
  %(prog)s sync                      # Smart bidirectional sync
  %(prog)s history                   # View sync history
  %(prog)s test                      # Test database connections
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show current sync status')
    status_parser.add_argument('--force', '-f', action='store_true',
                              help='Force refresh (bypass cache)')
    status_parser.set_defaults(func=cmd_status)

    # Push command (local → Railway)
    push_parser = subparsers.add_parser('push', help='Sync local → Railway')
    push_parser.add_argument('--force', '-f', action='store_true',
                            help='Force sync even if not needed')
    push_parser.add_argument('--yes', '-y', action='store_true',
                            help='Skip confirmation')
    push_parser.set_defaults(func=cmd_sync_local_to_railway)

    # Pull command (Railway → local)
    pull_parser = subparsers.add_parser('pull', help='Sync Railway → local')
    pull_parser.add_argument('--force', '-f', action='store_true',
                            help='Force sync even if not needed')
    pull_parser.add_argument('--yes', '-y', action='store_true',
                            help='Skip confirmation')
    pull_parser.set_defaults(func=cmd_sync_railway_to_local)

    # Smart sync command
    sync_parser = subparsers.add_parser('sync', help='Smart bidirectional sync')
    sync_parser.set_defaults(func=cmd_smart_sync)

    # History command
    history_parser = subparsers.add_parser('history', help='Show sync history')
    history_parser.add_argument('--limit', '-n', type=int, default=10,
                               help='Number of entries to show (default: 10)')
    history_parser.set_defaults(func=cmd_history)

    # Test command
    test_parser = subparsers.add_parser('test', help='Test database connections')
    test_parser.set_defaults(func=cmd_test_connections)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if '--debug' in sys.argv:
            raise
        sys.exit(1)

if __name__ == '__main__':
    main()
