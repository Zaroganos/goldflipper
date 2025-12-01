"""
Goldflipper Strategy Package

This package contains the multi-strategy trading framework for Goldflipper.
It provides:

- BaseStrategy: Abstract base class for all trading strategies
- StrategyRegistry: Strategy discovery and registration system
- StrategyOrchestrator: Multi-strategy execution coordinator
- Playbooks: Strategy parameter templates (playbooks/)

Subpackages:
- runners/: Individual strategy implementations
- shared/: Shared utilities (play management, order execution)
- playbooks/: Strategy playbook YAML files and loader
- trailing.py: Trailing stop functionality (existing)

Quick Start:
    # To use the orchestrator
    from goldflipper.strategy import StrategyOrchestrator
    
    orchestrator = StrategyOrchestrator()
    orchestrator.initialize()
    orchestrator.run_cycle()
    
    # To create a new strategy
    from goldflipper.strategy import BaseStrategy, register_strategy
    
    @register_strategy('my_strategy')
    class MyStrategy(BaseStrategy):
        # ... implement abstract methods
        pass
    
    # To use playbooks
    from goldflipper.strategy.playbooks import load_playbook
    
    playbook = load_playbook("sell_puts", "tasty_30_delta")
    tp_pct = playbook.exit.take_profit_pct

Configuration:
    Enable/disable multi-strategy mode in settings.yaml:
    
    strategy_orchestration:
      enabled: true        # Master switch
      mode: "sequential"   # or "parallel"
      
    Each strategy has its own config section:
    
    my_strategy:
      enabled: true
      # ... strategy-specific settings
"""

# Core strategy framework
from goldflipper.strategy.base import (
    BaseStrategy,
    StrategyPhase,
    PlayStatus,
    OrderAction,
    PositionSide,
)

from goldflipper.strategy.registry import (
    StrategyRegistry,
    register_strategy,
    register,
)

from goldflipper.strategy.orchestrator import (
    StrategyOrchestrator,
    ExecutionMode,
    OrchestratorState,
)

# Existing trailing stops functionality (unchanged)
from goldflipper.strategy.trailing import (
    trailing_tp_enabled,
    trailing_sl_enabled,
    has_trailing_enabled,
    update_trailing_levels,
    get_trailing_tp_levels,
)

__all__ = [
    # Base strategy framework
    'BaseStrategy',
    'StrategyPhase',
    'PlayStatus',
    'OrderAction',
    'PositionSide',
    
    # Registry
    'StrategyRegistry',
    'register_strategy',
    'register',
    
    # Orchestrator
    'StrategyOrchestrator',
    'ExecutionMode',
    'OrchestratorState',
    
    # Trailing stops (existing)
    'trailing_tp_enabled',
    'trailing_sl_enabled',
    'has_trailing_enabled',
    'update_trailing_levels',
    'get_trailing_tp_levels',
]
