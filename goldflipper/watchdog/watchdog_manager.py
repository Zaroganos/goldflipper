import logging
import threading
import time
from datetime import datetime

import psutil


class WatchdogManager:
    def __init__(self, check_interval=30):
        self.check_interval = check_interval
        self.last_heartbeat = datetime.now()
        self.watchdog_thread = None
        self.running = False
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self.logger.info("WatchdogManager initialized with check_interval=%d", check_interval)

    def start_monitoring(self):
        """Start the watchdog monitoring thread if not already running"""
        with self._lock:
            if not self.running:
                self.running = True
                self.last_heartbeat = datetime.now()
                self.watchdog_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.watchdog_thread.start()
                self.logger.info("Watchdog monitoring thread started")
                self.logger.info(f"Initial heartbeat set to {self.last_heartbeat}")
            else:
                self.logger.warning("Watchdog monitoring already running")

    def stop_monitoring(self):
        """Stop the watchdog monitoring thread"""
        with self._lock:
            if self.running:
                self.running = False
                if self.watchdog_thread:
                    self.watchdog_thread.join(timeout=5)
                self.logger.info("Watchdog monitoring stopped")

    def update_heartbeat(self):
        """Update the heartbeat timestamp"""
        with self._lock:
            previous = self.last_heartbeat
            self.last_heartbeat = datetime.now()
            elapsed = (self.last_heartbeat - previous).total_seconds()
            self.logger.info(f"Heartbeat updated. Time since last update: {elapsed:.2f}s")

    def _monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Monitor loop started")
        last_check_time = datetime.now()

        while self.running:
            try:
                current_time = datetime.now()
                with self._lock:
                    heartbeat_age = (current_time - self.last_heartbeat).total_seconds()
                    check_interval = (current_time - last_check_time).total_seconds()

                self.logger.info(f"Checking health. Heartbeat age: {heartbeat_age:.2f}s, Check interval: {check_interval:.2f}s")
                last_check_time = current_time

                self._check_system_health()
                self._check_application_health()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in watchdog monitoring: {str(e)}")

    def _check_system_health(self):
        """Monitor system resources"""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()
            disk = psutil.disk_usage("/")

            if memory.percent > 90:
                self.logger.warning(f"High memory usage: {memory.percent}%")
            if cpu_percent > 90:
                self.logger.warning(f"High CPU usage: {cpu_percent}%")
            if disk.percent > 90:
                self.logger.warning(f"Low disk space: {disk.percent}% used")

        except Exception as e:
            self.logger.error(f"Error checking system health: {str(e)}")

    def _check_application_health(self):
        """Check if main application is responsive"""
        try:
            with self._lock:
                heartbeat_age = (datetime.now() - self.last_heartbeat).total_seconds()

            if heartbeat_age > self.check_interval * 2:
                self.logger.error(f"Application heartbeat missing for {heartbeat_age:.6f} seconds")
                self._trigger_recovery()
            else:
                self.logger.debug(f"Application heartbeat age: {heartbeat_age:.6f} seconds")

        except Exception as e:
            self.logger.error(f"Error checking application health: {str(e)}")

    def _trigger_recovery(self):
        """Handle recovery actions when application appears unresponsive"""
        self.logger.warning("Initiating recovery procedure")
        # For now, just log the event. We can add more recovery actions later
        # Such as restarting specific components or notifying administrators
