# src/main.py
"""Main service entry point."""
import sys
import time
import signal
import argparse
import sqlite3 # Import sqlite3 here for the command
from pathlib import Path

from config.manager import ConfigManager
from orchestrator.processor import ProcessingOrchestrator
from utils.logger import get_logger
from utils.hash_registry import HashRegistry

logger = get_logger()

shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def clear_cache_command(customer_id=None):
    """Clear processing cache."""
    registry = HashRegistry()
    
    if customer_id:
        deleted = registry.clear_cache(customer_id)
        print(f"✓ Cleared {deleted} cached files for customer: {customer_id}")
    else:
        deleted = registry.clear_cache()
        print(f"✓ Cleared {deleted} cached files (all customers)")


def list_cache_command(customer_id=None):
    """List cached files."""
    registry = HashRegistry()
    
    files = []
    
    if customer_id:
        files = registry.get_customer_history(customer_id)
        print(f"\nCached files for customer: {customer_id}")
    else:
        # FIX: Ensure we correctly handle customers from the DB
        try:
            with sqlite3.connect(registry.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT customer_id FROM processed_files ORDER BY customer_id")
                customer_ids = [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # DB file might not exist yet
            customer_ids = []
            
        if not customer_ids:
            print("No cached files found.")
            return
        
        print(f"\nCached files for all customers:")
        for cid in customer_ids:
            files.extend(registry.get_customer_history(cid))
    
    if not files:
        print("No cached files found for specified customer or system.")
        return
    
    print(f"\nTotal: {len(files)} files")
    print(f"{'Status':<8} {'Customer':<20} {'File Name':<40} {'Processed At':<20}")
    print("-" * 90)
    
    for f in files:
        print(f"{f.status:<8} {f.customer_id:<20} {f.file_name:<40} {f.processed_at.strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    # ... (rest of main() remains the same) ...
    global shutdown_requested
    
    parser = argparse.ArgumentParser(description="BudgetFlow PDF Processing Service")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["run", "clear-cache", "list-cache"],
        default="run",
        help="Command to execute (default: run)"
    )
    parser.add_argument(
        "--customer",
        help="Customer ID (for clear-cache and list-cache commands)"
    )
    
    args = parser.parse_args()
    
    if args.command == "clear-cache":
        clear_cache_command(args.customer)
        return
    
    if args.command == "list-cache":
        list_cache_command(args.customer)
        return
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("BudgetFlow service starting...")
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    if not config:
        logger.info("No configuration found. Launching setup wizard...")
        try:
            from config.setup_wizard import SetupWizard
            wizard = SetupWizard()
            wizard.run()
            
            config = config_manager.load_config()
            if not config:
                logger.critical("Setup wizard closed without saving configuration.")
                sys.exit(1)
        except Exception as e:
            logger.critical(f"Failed to run setup wizard: {e}")
            logger.critical("Please run setup wizard manually: python -m config.setup_wizard")
            sys.exit(1)
    
    is_valid, message = config_manager.validate_config(config)
    if not is_valid:
        logger.critical(f"Invalid configuration: {message}")
        sys.exit(1)
    
    logger.info("Configuration loaded successfully")
    
    if config.oauth_client_secrets:
        logger.info("OAuth authentication configured - checking credentials...")
        try:
            from utils.auth import get_credentials
            get_credentials(
                oauth_client_secrets=config.oauth_client_secrets,
                oauth_token_path=config.oauth_token_path
            )
            logger.info("OAuth credentials validated successfully")
        except Exception as e:
            logger.critical(f"OAuth authorization failed: {e}")
            sys.exit(1)
    
    try:
        orchestrator = ProcessingOrchestrator(config)
    except Exception as e:
        logger.critical(f"Failed to initialize orchestrator: {e}")
        sys.exit(1)
    
    logger.info(f"Service initialized. Polling interval: {config.polling_interval_minutes} minutes")
    
    cycle_count = 0
    while not shutdown_requested:
        cycle_count += 1
        logger.info(f"=== Polling cycle #{cycle_count} ===")
        
        try:
            results = orchestrator.run_polling_cycle()
            
            total_processed = sum(r.files_processed for r in results)
            total_failed = sum(r.files_failed for r in results)
            total_transactions = sum(r.transactions_extracted for r in results)
            
            logger.info(
                f"Cycle #{cycle_count} complete: "
                f"{len(results)} customers, "
                f"{total_processed} files processed, "
                f"{total_failed} files failed, "
                f"{total_transactions} transactions"
            )
            
        except Exception as e:
            logger.error(f"Error in polling cycle: {e}")
        
        logger.info(f"Heartbeat: Service is running (cycle #{cycle_count})")
        
        if not shutdown_requested:
            wait_seconds = config.polling_interval_minutes * 60
            logger.debug(f"Waiting {wait_seconds}s until next cycle...")
            
            for _ in range(wait_seconds):
                if shutdown_requested:
                    break
                time.sleep(1)
    
    logger.info("Service stopped gracefully")


if __name__ == "__main__":
    main()