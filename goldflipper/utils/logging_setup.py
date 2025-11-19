import logging
import logging.handlers
import sys
import os
import gzip
import shutil
from pathlib import Path
import zipfile

try:
    from goldflipper.config.config import config
except Exception:
    config = None  # Fallback if config isn't available during certain tool runs

# Track if logging has been configured to prevent basicConfig conflicts
_logging_configured = False


def _get_config_value(*keys, default=None):
    if config is None:
        return default
    return config.get(*keys, default=default)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_rotate_existing_log(
    log_path: Path,
    max_bytes: int,
    backup_count: int,
    compress_enabled: bool,
    compression_format: str,
) -> None:
    """Safely rotate an existing log file if it exceeds the size threshold.
    
    This function checks if the log file already exists and is too large,
    and rotates it before the logging handler is created. This prevents
    large log files from accumulating between application restarts.
    
    Args:
        log_path: Path to the log file
        max_bytes: Maximum size in bytes before rotation
        backup_count: Number of backup files to keep
        compress_enabled: Whether to compress rotated logs
        compression_format: Compression format ('gz' or 'zip')
    """
    try:
        # Check if log file exists and get its size
        if not log_path.exists():
            return  # No file to rotate
        
        file_size = log_path.stat().st_size
        
        # Only rotate if file exceeds the threshold
        if file_size < max_bytes:
            return  # File is within acceptable size
        
        # File is too large, need to rotate
        # Use the same naming convention as the handlers
        base_name = str(log_path)
        
        # First, rotate existing backups (remove oldest if we're at limit)
        if backup_count > 0:
            # Find and remove the oldest backup if we're at the limit
            backup_files = []
            for i in range(backup_count, 0, -1):
                if compress_enabled:
                    if compression_format == 'zip':
                        backup_name = f"{base_name}.{i}.zip"
                    else:
                        backup_name = f"{base_name}.{i}.gz"
                else:
                    backup_name = f"{base_name}.{i}"
                
                backup_path = Path(backup_name)
                if backup_path.exists():
                    backup_files.append(backup_path)
            
            # Remove oldest backup if we're at the limit
            if len(backup_files) >= backup_count:
                try:
                    backup_files[0].unlink()  # Remove oldest
                except Exception:
                    pass  # Ignore errors removing old backups
            
            # Shift existing backups
            for i in range(backup_count - 1, 0, -1):
                if compress_enabled:
                    if compression_format == 'zip':
                        old_backup = f"{base_name}.{i}.zip"
                        new_backup = f"{base_name}.{i + 1}.zip"
                    else:
                        old_backup = f"{base_name}.{i}.gz"
                        new_backup = f"{base_name}.{i + 1}.gz"
                else:
                    old_backup = f"{base_name}.{i}"
                    new_backup = f"{base_name}.{i + 1}"
                
                old_path = Path(old_backup)
                new_path = Path(new_backup)
                
                if old_path.exists():
                    try:
                        old_path.rename(new_path)
                    except Exception:
                        pass  # Ignore errors during backup shifting
        
        # Rotate the current log file
        if compress_enabled:
            if compression_format == 'zip':
                rotated_name = f"{base_name}.1.zip"
            else:
                rotated_name = f"{base_name}.1.gz"
        else:
            rotated_name = f"{base_name}.1"
        
        rotated_path = Path(rotated_name)
        
        # Compress and move the current log file
        try:
            if compress_enabled:
                if compression_format == 'zip':
                    # Write the rotated file into a zip archive
                    with zipfile.ZipFile(rotated_path, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
                        arcname = log_path.name
                        zf.write(log_path, arcname=arcname)
                    log_path.unlink()  # Remove original after compression
                else:
                    # Gzip compress
                    with open(log_path, 'rb') as f_in, gzip.open(rotated_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    log_path.unlink()  # Remove original after compression
            else:
                # Simple rename without compression
                log_path.rename(rotated_path)
        except Exception:
            # If rotation fails, try simple rename as fallback
            try:
                if rotated_path.exists():
                    rotated_path.unlink()  # Remove existing rotated file first
                log_path.rename(rotated_path)
            except Exception:
                pass  # If all rotation attempts fail, continue anyway
                # The handler will manage rotation on next write
        
    except Exception:
        # If anything goes wrong, silently continue
        # The logging handler will still work and manage rotation going forward
        pass


def configure_logging(
    console_mode: bool = False,
    service_mode: bool = False,
    log_file: os.PathLike | str | None = None,
    level_override: int | None = None,
) -> None:
    """Configure application logging with rotation.

    Parameters:
        console_mode: If True, also log to stdout.
        service_mode: If True, add Windows Event Log handler.
        log_file: Optional explicit log file path. If None, use config or default.
        level_override: Optional logging level (e.g., logging.DEBUG) to override config.
    """
    # Determine log destination
    if log_file is None:
        # Prefer logging.file, then paths.log_file, then default
        file_from_logging = _get_config_value('logging', 'file', default=None)
        file_from_paths = _get_config_value('paths', 'log_file', default=None)
        log_file = file_from_logging or file_from_paths or 'logs/app_run.log'

    log_path = Path(log_file)
    if not log_path.is_absolute():
        # Resolve relative to project root (two levels up from this file: .../goldflipper)
        project_root = Path(__file__).resolve().parents[2]
        log_path = (project_root / log_path).resolve()

    _ensure_parent_dir(log_path)

    # Determine level and format
    level_str = _get_config_value('logging', 'level', default='INFO').upper()
    level = getattr(logging, level_str, logging.INFO)
    if level_override is not None:
        level = level_override
    fmt = _get_config_value('logging', 'format', default='%(asctime)s - %(levelname)s - %(message)s')

    # Rotation settings
    rotation_type = _get_config_value('logging', 'rotation', 'type', default='time')  # 'time' or 'size'
    when = _get_config_value('logging', 'rotation', 'when', default='midnight')
    interval = int(_get_config_value('logging', 'rotation', 'interval', default=1))
    backup_count = int(_get_config_value('logging', 'rotation', 'backup_count', default=14))
    max_bytes = int(_get_config_value('logging', 'rotation', 'max_bytes', default=10 * 1024 * 1024))  # 10MB
    compress_enabled = bool(_get_config_value('logging', 'rotation', 'compress', default=True))
    compression_format = str(_get_config_value('logging', 'rotation', 'compression_format', default='gz')).lower()

    # Check and rotate existing log file if it's already too large
    # This handles the case where the log file grew large between application restarts
    _safe_rotate_existing_log(
        log_path=log_path,
        max_bytes=max_bytes,
        backup_count=backup_count,
        compress_enabled=compress_enabled,
        compression_format=compression_format,
    )

    # Build handlers
    handlers: list[logging.Handler] = []
    if rotation_type == 'size':
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
            delay=True,
        )
    else:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_path),
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding='utf-8',
            delay=True,
            utc=False,
        )

    if compress_enabled:
        def namer(default_name: str) -> str:
            if compression_format == 'zip':
                return f"{default_name}.zip"
            # default to gzip
            return f"{default_name}.gz"

        def rotator(source: str, dest: str) -> None:
            try:
                if dest.endswith('.zip'):
                    # Write the rotated file into a zip archive
                    with zipfile.ZipFile(dest, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
                        arcname = os.path.basename(dest[:-4])  # remove .zip
                        # Use original filename as arcname without .zip
                        zf.write(source, arcname=os.path.basename(arcname))
                    os.remove(source)
                else:
                    # Gzip compress
                    with open(source, 'rb') as f_in, gzip.open(dest, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    os.remove(source)
            except Exception:
                # If compression fails, fall back to simple rename
                try:
                    shutil.move(source, dest)
                except Exception:
                    pass

        file_handler.namer = namer
        file_handler.rotator = rotator
    handlers.append(file_handler)

    if console_mode:
        handlers.append(logging.StreamHandler(sys.stdout))

    if service_mode:
        try:
            handlers.append(logging.handlers.NTEventLogHandler('GoldflipperService'))
        except Exception:
            # Event log handler may not be available; continue without it
            pass

    # Clear existing handlers to avoid duplicates
    # Properly flush, close, and remove all existing handlers first
    root_logger = logging.getLogger()
    
    # Flush and close all existing handlers before removing them
    for existing in root_logger.handlers[:]:
        try:
            existing.flush()  # Flush any buffered messages first
            existing.close()  # Properly close handlers to free resources
        except Exception:
            pass  # Ignore errors during cleanup
        root_logger.removeHandler(existing)
    
    # Also check and clean up any handlers on child loggers that might cause duplicates
    # Child loggers should not have their own handlers - they should propagate to root logger
    # This prevents messages from being logged twice (once by child handler, once by root handler via propagation)
    # Note: We only remove handlers, not change propagation or levels, to respect library configurations
    for logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        if logger.handlers:
            for handler in logger.handlers[:]:
                try:
                    handler.flush()
                    handler.close()
                except Exception:
                    pass
                logger.removeHandler(handler)

    # Also prevent basicConfig from adding a default handler
    # by marking that we've already configured logging
    global _logging_configured
    _logging_configured = True

    formatter = logging.Formatter(fmt)
    for h in handlers:
        h.setFormatter(formatter)

    root_logger.setLevel(level)
    for h in handlers:
        root_logger.addHandler(h)

    # Optional: reduce noise from third-party libraries
    for noisy in ('urllib3', 'yfinance', 'alpaca_trade_api'):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, level))


def is_logging_configured() -> bool:
    """Check if logging has been configured via configure_logging().
    
    This can be used to prevent basicConfig from being called after
    configure_logging has already set up logging.
    """
    return _logging_configured


