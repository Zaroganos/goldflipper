import os

import psutil


def is_trading_system_running():
    """
    Check if the trading system is running either as a Windows service or as a process.
    This implementation first checks the Windows service status (if applicable) and then
    validates that no stray trading process exists.
    """
    # On Windows, check the service status first.
    if os.name == "nt":
        try:
            import win32service
            import win32serviceutil

            status = win32serviceutil.QueryServiceStatus("GoldflipperService")
            if status[1] == win32service.SERVICE_RUNNING:
                return True
        except Exception:
            # If there's an error checking the service, proceed to process check.
            pass

    # Check for processes whose command line contains "python -m goldflipper.run"
    for proc in psutil.process_iter(attrs=["cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "python -m goldflipper.run" in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return False
