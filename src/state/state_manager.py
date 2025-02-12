import json
import threading
import time
from pathlib import Path
import logging

class StateManager:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_file = state_dir / "service_state.json"
        self.state_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def save_state(self, state_data: dict):
        with self.state_lock:
            try:
                # Create backup before saving
                self._backup_current_state()
                
                # Write new state
                with open(self.state_file, 'w') as f:
                    json.dump(state_data, f, indent=4)
                
                self.logger.info("State saved successfully")
            except Exception as e:
                self.logger.error(f"Error saving state: {str(e)}")
                raise

    def load_state(self) -> dict:
        with self.state_lock:
            try:
                if not self.state_file.exists():
                    return {}
                
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                if self._validate_state(state):
                    return state
                
                # If validation fails, try to recover from backup
                return self._recover_from_backup()
            except Exception as e:
                self.logger.error(f"Error loading state: {str(e)}")
                return self._recover_from_backup()

    def _backup_current_state(self):
        if self.state_file.exists():
            backup_file = self.state_dir / f"state_backup_{int(time.time())}.json"
            self.state_file.rename(backup_file)

    def _validate_state(self, state: dict) -> bool:
        # Implement state validation logic
        required_keys = ['timestamp', 'version', 'data']
        return all(key in state for key in required_keys)

    def _recover_from_backup(self) -> dict:
        # Find most recent valid backup
        backups = sorted(self.state_dir.glob("state_backup_*.json"), reverse=True)
        
        for backup in backups:
            try:
                with open(backup, 'r') as f:
                    state = json.load(f)
                if self._validate_state(state):
                    self.logger.info(f"Recovered state from backup: {backup.name}")
                    return state
            except Exception:
                continue
        
        return {} 