from typing import Optional, Any, Dict
import logging

class CycleCache:
    """Cycle-aware cache for market data"""
    
    def __init__(self, config: dict):
        self.logger = logging.getLogger(__name__)
        self.enabled = config['cache']['enabled']
        self.max_items = config['cache'].get('max_items', 1000)
        self._cache: Dict[str, Any] = {}
        self._cycle_id = 0
        
    def new_cycle(self):
        """Start a new cycle, clearing previous cache"""
        if not self.enabled:
            return
            
        self._cycle_id += 1
        self._cache.clear()
        self.logger.debug(f"Started new cache cycle {self._cycle_id}")
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from current cycle's cache"""
        if not self.enabled:
            return None
            
        if value := self._cache.get(key):
            self.logger.debug(f"Cache hit for {key} in cycle {self._cycle_id}")
            return value
        return None
        
    def set(self, key: str, value: Any) -> bool:
        """Set value in current cycle's cache"""
        if not self.enabled:
            return False
            
        if len(self._cache) >= self.max_items:
            self.logger.warning(f"Cache full in cycle {self._cycle_id}, not caching {key}")
            return False
            
        self._cache[key] = value
        self.logger.debug(f"Cached {key} in cycle {self._cycle_id}")
        return True 