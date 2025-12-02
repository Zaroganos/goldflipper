from __future__ import annotations

import argparse
import importlib
import logging
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger("goldflipper.launcher")


def _settings_path() -> Path:
    """Return the canonical path to the primary settings file."""
    return Path(__file__).resolve().parent / "config" / "settings.yaml"


def _run_first_run_setup(force: bool) -> bool:
    """
    Launch the first-run wizard when required.

    Returns True when a previously-missing settings file is created during this
    invocation. This allows the TUI to display the onboarding affordances.
    """
    settings_file = _settings_path()
    existed_before = settings_file.exists()

    if not force and existed_before:
        return False

    try:
        from goldflipper.first_run_setup import FirstRunSetup
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("First-run setup unavailable: %s", exc)
        return False

    LOGGER.info(
        "Launching first-run setup (force=%s, existed_before=%s)",
        force,
        existed_before,
    )
    try:
        FirstRunSetup().run()
    except Exception as exc:  # pragma: no cover - GUI loop exceptions
        LOGGER.error("First-run setup terminated unexpectedly: %s", exc)

    created_now = (not existed_before) and settings_file.exists()
    if created_now:
        LOGGER.info("Settings profile created at %s", settings_file)
    else:
        LOGGER.debug(
            "First-run setup did not create a new settings file (exists=%s)",
            settings_file.exists(),
        )
    return created_now


def _launch_tui() -> None:
    """Start the Textual interface."""
    from goldflipper.goldflipper_tui import GoldflipperTUI

    app = GoldflipperTUI()
    app.run()


def main(argv: Optional[list[str]] = None) -> int:
    """
    Entry point for the packaged Goldflipper desktop experience.

    - Runs the onboarding wizard on the very first launch.
    - Falls back to the existing configuration afterwards.
    - Starts the Textual TUI by default.
    
    Special exe-mode arguments:
    - --trading-mode: Run the trading system directly (for spawned processes)
    - --service-install: Install the Windows service
    - --service-remove: Remove the Windows service
    """
    parser = argparse.ArgumentParser(description="Goldflipper Desktop Launcher")
    parser.add_argument(
        "--force-setup",
        action="store_true",
        help="Always run the configuration wizard before launching the TUI.",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Never launch the configuration wizard (even on first run).",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Run the configuration wizard and exit without launching the TUI.",
    )
    # Exe-mode special arguments
    parser.add_argument(
        "--trading-mode",
        action="store_true",
        help="Run the trading system directly (used when launching from exe TUI).",
    )
    parser.add_argument(
        "--service-install",
        action="store_true",
        help="Install the Windows service (requires admin privileges).",
    )
    parser.add_argument(
        "--service-remove",
        action="store_true",
        help="Remove the Windows service (requires admin privileges).",
    )
    args = parser.parse_args(argv)

    # Handle special exe-mode arguments
    if args.trading_mode:
        LOGGER.info("Trading mode requested; launching trading system directly.")
        from goldflipper.run import run_trading_system
        run_trading_system(console_mode=True)
        return 0
    
    if args.service_install:
        LOGGER.info("Service installation requested.")
        import win32serviceutil
        from goldflipper.run import GoldflipperService
        win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', '--startup', 'auto', 'install'])
        return 0
    
    if args.service_remove:
        LOGGER.info("Service removal requested.")
        import win32serviceutil
        from goldflipper.run import GoldflipperService
        win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', 'remove'])
        return 0

    # Normal TUI launch flow
    settings_created = False
    if not args.skip_setup:
        settings_created = _run_first_run_setup(force=args.force_setup)

    config_module = importlib.import_module("goldflipper.config.config")
    if settings_created:
        # Signal to the TUI that the onboarding workflow just completed so it
        # can highlight the configuration button and show notifications.
        config_module.settings_just_created = True

    if args.setup_only:
        LOGGER.info("Setup-only mode requested; exiting before launching TUI.")
        return 0

    _launch_tui()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())

