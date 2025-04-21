import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import os
import time
from datetime import datetime
from pathlib import Path
import traceback  # Add this for detailed error tracking

class GoldflipperService(win32serviceutil.ServiceFramework):
    _svc_name_ = "GoldflipperService"
    _svc_display_name_ = "Goldflipper Trading Service"
    _svc_description_ = "Automated trading service for the Goldflipper platform"

    def __init__(self, args):
        try:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = False
            
            # Set up base directories
            self.base_dir = Path(os.environ.get('PROGRAMDATA', '')) / 'Goldflipper'
            self.log_dir = self.base_dir / 'logs'
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize logging
            self._setup_logging()
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Service initialization failed: {str(e)}\n{traceback.format_exc()}")
            raise

    def _setup_logging(self):
        """Set up logging to file and Windows Event Log"""
        import logging
        log_file = self.log_dir / 'service.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.handlers.NTEventLogHandler(self._svc_name_)
            ]
        )
        self.logger = logging.getLogger('GoldflipperService')
        self.logger.info("Logging initialized")

    def SvcStop(self):
        """Handle service stop request"""
        try:
            self.logger.info("Service stop requested")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            self.running = False
        except Exception as e:
            self.logger.error(f"Error during service stop: {str(e)}\n{traceback.format_exc()}")
            raise

    def SvcDoRun(self):
        """Main service run method"""
        try:
            self.logger.info("Service starting")
            self.running = True
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            self.main()
            
        except Exception as e:
            error_msg = f"Service failed: {str(e)}\n{traceback.format_exc()}"
            self.logger.error(error_msg)
            servicemanager.LogErrorMsg(error_msg)
            raise

    def main(self):
        """Main service logic"""
        try:
            self.logger.info("Initializing main service components")
            from goldflipper.watchdog.watchdog_manager import WatchdogManager
            from goldflipper.core import monitor_plays_continuously
            from goldflipper.config.config import config

            # Check if watchdog is enabled in config
            watchdog_enabled = config.get('watchdog', 'enabled', default=False)
            watchdog_check_interval = config.get('watchdog', 'check_interval', default=30)
            
            watchdog = None
            if watchdog_enabled:
                self.logger.info("Watchdog system is enabled")
                watchdog = WatchdogManager(check_interval=watchdog_check_interval)
                watchdog.start_monitoring()
            else:
                self.logger.info("Watchdog system is disabled in configuration")
            
            self.logger.info("Starting main service loop")
            while self.running:
                try:
                    if watchdog:
                        watchdog.update_heartbeat()
                    
                    monitor_plays_continuously()
                    
                    win32event.WaitForSingleObject(self.stop_event, 30000)
                except Exception as e:
                    error_msg = f"Error in main loop: {str(e)}\n{traceback.format_exc()}"
                    self.logger.error(error_msg)
                    servicemanager.LogErrorMsg(error_msg)
                    time.sleep(10)
                    
        except Exception as e:
            error_msg = f"Fatal error in main: {str(e)}\n{traceback.format_exc()}"
            self.logger.error(error_msg)
            servicemanager.LogErrorMsg(error_msg)
            raise

if __name__ == '__main__':
    try:
        if len(sys.argv) == 1:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(GoldflipperService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(GoldflipperService)
    except Exception as e:
        servicemanager.LogErrorMsg(f"Service host error: {str(e)}\n{traceback.format_exc()}")
        raise 