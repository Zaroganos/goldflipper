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


def _get_config_value(*keys, default=None):
    if config is None:
        return default
    return config.get(*keys, default=default)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


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
    root_logger = logging.getLogger()
    for existing in root_logger.handlers[:]:
        root_logger.removeHandler(existing)

    formatter = logging.Formatter(fmt)
    for h in handlers:
        h.setFormatter(formatter)

    root_logger.setLevel(level)
    for h in handlers:
        root_logger.addHandler(h)

    # Optional: reduce noise from third-party libraries
    for noisy in ('urllib3', 'yfinance', 'alpaca_trade_api'):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, level))


