import os
import psutil

def is_trading_system_running():
    """
    Check if the trading system is running either as a console process or as a Windows service.
    
    This function uses psutil to look for a process with a command line that includes
    'goldflipper.run'. Additionally, on Windows it checks for a service named 
    'GoldFlipperService' being in the running state.
    
    Returns:
        bool: True if the trading system is running, False otherwise.
    """
    # Check for processes whose command line contains "goldflipper.run"
    for proc in psutil.process_iter(attrs=["cmdline", "name"]):
        try:
            cmdline_list = proc.info.get("cmdline") or []  # Ensure we have a list even if None
            cmdline = " ".join(cmdline_list)
            if "goldflipper.run" in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Additionally, on Windows, check if the GoldFlipperService is running
    if os.name == 'nt':
        try:
            import win32serviceutil
            import win32service
            status = win32serviceutil.QueryServiceStatus("GoldFlipperService")
            # SERVICE_RUNNING is indicated by the status value equal to win32service.SERVICE_RUNNING
            if status[1] == win32service.SERVICE_RUNNING:
                return True
        except Exception:
            # If there is any issue querying the service, we simply ignore it
            pass

    return False