"""Main service entry point."""
import sys
import time
import signal
import argparse
import sqlite3
from pathlib import Path

from config.manager import ConfigManager
from config.setup_wizard import SetupWizard
from orchestrator.processor import ProcessingOrchestrator
from utils.logger import get_logger
from utils.hash_registry import HashRegistry
from utils.auth import get_credentials

logger = get_logger()
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def clear_cache_command(customer_id: str = None) -> None:
    """Clear processing cache for specified customer or all customers."""
    registry = HashRegistry()
    deleted = registry.clear_cache(customer_id)
    
    if customer_id:
        print(f"✓ Cleared {deleted} cached files for customer: {customer_id}")
    else:
        print(f"✓ Cleared {deleted} cached files (all customers)")


def list_cache_command(customer_id: str = None) -> None:
    """List cached files for specified customer or all customers."""
    registry = HashRegistry()
    
    if customer_id:
        files = registry.get_customer_history(customer_id)
        print(f"\nCached files for customer: {customer_id}")
    else:
        files = _get_all_customer_files(registry)
        if not files:
            print("No cached files found.")
            return
        print("\nCached files for all customers:")
    
    if not files:
        print("No cached files found for specified customer.")
        return
    
    _print_file_table(files)


def _get_all_customer_files(registry: HashRegistry) -> list:
    """Get all cached files across all customers."""
    try:
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT customer_id FROM processed_files ORDER BY customer_id")
            customer_ids = [row[0] for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
    
    files = []
    for customer_id in customer_ids:
        files.extend(registry.get_customer_history(customer_id))
    return files


def _print_file_table(files: list) -> None:
    """Print formatted table of cached files."""
    print(f"\nTotal: {len(files)} files")
    print(f"{'Status':<8} {'Customer':<20} {'File Name':<40} {'Processed At':<20}")
    print("-" * 90)
    
    for file in files:
        print(
            f"{file.status:<8} {file.customer_id:<20} "
            f"{file.file_name:<40} {file.processed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )


def _load_and_validate_config() -> object:
    """Load and validate configuration, launching setup wizard if needed."""
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    if not config:
        logger.info("No configuration found. Launching setup wizard...")
        wizard = SetupWizard()
        wizard.run()
        
        config = config_manager.load_config()
        if not config:
            logger.critical("Setup wizard closed without saving configuration.")
            sys.exit(1)
    
    is_valid, message = config_manager.validate_config(config)
    if not is_valid:
        logger.critical(f"Invalid configuration: {message}")
        sys.exit(1)
    
    logger.info("Configuration loaded successfully")
    return config


def _validate_oauth_credentials(config: object) -> None:
    """Validate OAuth credentials if configured."""
    if config.oauth_client_secrets:
        logger.info("OAuth authentication configured - checking credentials...")
        get_credentials(
            oauth_client_secrets=config.oauth_client_secrets,
            oauth_token_path=config.oauth_token_path
        )
        logger.info("OAuth credentials validated successfully")


def _run_polling_loop(orchestrator: ProcessingOrchestrator, config: object) -> None:
    """Run the main polling loop."""
    global shutdown_requested
    cycle_count = 0
    
    logger.info(f"Service initialized. Polling interval: {config.polling_interval_minutes} minutes")
    
    while not shutdown_requested:
        cycle_count += 1
        logger.info(f"=== Polling cycle #{cycle_count} ===")
        
        try:
            results = orchestrator.run_polling_cycle()
            _log_cycle_results(cycle_count, results)
        except Exception as e:
            logger.error(f"Error in polling cycle: {e}")
        
        logger.info(f"Heartbeat: Service is running (cycle #{cycle_count})")
        _wait_for_next_cycle(config.polling_interval_minutes)
    
    logger.info("Service stopped gracefully")


def _log_cycle_results(cycle_count: int, results: list) -> None:
    """Log summary of polling cycle results."""
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


def _wait_for_next_cycle(interval_minutes: int) -> None:
    """Wait for next polling cycle with graceful shutdown support."""
    global shutdown_requested
    wait_seconds = interval_minutes * 60
    logger.debug(f"Waiting {wait_seconds}s until next cycle...")
    
    for _ in range(wait_seconds):
        if shutdown_requested:
            break
        time.sleep(1)


def main():
    """Main entry point for BudgetFlow service."""
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
    
    try:
        config = _load_and_validate_config()
        _validate_oauth_credentials(config)
        orchestrator = ProcessingOrchestrator(config)
        _run_polling_loop(orchestrator, config)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()