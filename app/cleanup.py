"""Background cleanup task for old files.

This module provides automated cleanup of old files from upload and output
directories to prevent disk space exhaustion.
"""
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_old_files(directory: Path, max_age_hours: int = 24):
    """Remove files older than max_age_hours.
    
    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files in hours
    
    Returns:
        Tuple of (deleted_count, deleted_size_mb)
    """
    if not directory.exists():
        logging.warning(f"Cleanup skipped: directory does not exist: {directory}")
        return 0, 0
        
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    deleted_count = 0
    deleted_size = 0
    
    try:
        for file_path in directory.iterdir():
            if file_path.is_file():
                try:
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        deleted_size += file_size
                        logging.debug(f"Deleted old file: {file_path}")
                except Exception as file_error:
                    logging.error(f"Failed to delete {file_path}: {file_error}")
        
        if deleted_count > 0:
            size_mb = deleted_size / (1024 * 1024)
            logging.info(f"Cleanup: Deleted {deleted_count} files ({size_mb:.2f} MB) from {directory}")
        else:
            logging.debug(f"Cleanup: No old files to delete in {directory}")
            
        return deleted_count, deleted_size / (1024 * 1024)
            
    except Exception as e:
        logging.error(f"Cleanup failed for {directory}: {e}")
        return deleted_count, deleted_size / (1024 * 1024)


def start_cleanup_worker(upload_dir: str, output_dir: str, interval_seconds: int = 3600):
    """Start background cleanup worker thread.
    
    Args:
        upload_dir: Upload directory path
        output_dir: Output directory path
        interval_seconds: Cleanup interval in seconds (default 1 hour)
    """
    import threading
    
    def cleanup_loop():
        """Main cleanup loop running in background thread."""
        logging.info(f"Cleanup worker started (interval: {interval_seconds}s)")
        
        while True:
            try:
                logging.info("Running scheduled cleanup...")
                
                # Clean uploads (keep for 24 hours)
                upload_count, upload_mb = cleanup_old_files(Path(upload_dir), max_age_hours=24)
                
                # Clean outputs (keep for 48 hours - longer for results)
                output_count, output_mb = cleanup_old_files(Path(output_dir), max_age_hours=48)
                
                total_count = upload_count + output_count
                total_mb = upload_mb + output_mb
                
                if total_count > 0:
                    logging.info(
                        f"Cleanup complete: Removed {total_count} files "
                        f"({total_mb:.2f} MB total). Next cleanup in {interval_seconds}s"
                    )
                else:
                    logging.debug(f"Cleanup complete: No files to remove. Next cleanup in {interval_seconds}s")
                    
            except Exception as e:
                logging.error(f"Cleanup worker error: {e}")
            
            time.sleep(interval_seconds)
    
    # Start daemon thread (will exit when main program exits)
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    logging.info("Cleanup worker thread initialized")


def cleanup_directory_now(directory: Path, max_age_hours: int = 0):
    """Immediately cleanup all files in directory.
    
    Useful for manual cleanup or testing.
    
    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files in hours (default 0 = all files)
    
    Returns:
        Tuple of (deleted_count, deleted_size_mb)
    """
    return cleanup_old_files(directory, max_age_hours)
