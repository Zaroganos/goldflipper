# Trailing Take Profit & Trailing Stop Loss Implementation Plan
## Goldflipper Trading System Enhancement

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current System Analysis](#current-system-analysis)
3. [Requirements Specification](#requirements-specification)
4. [Technical Design](#technical-design)
5. [Data Structure Modifications](#data-structure-modifications)
6. [Implementation Phases](#implementation-phases)
7. [Integration Strategy](#integration-strategy)
8. [Risk Management](#risk-management)
9. [Testing Strategy](#testing-strategy)
10. [Success Metrics](#success-metrics)
11. [Timeline & Dependencies](#timeline--dependencies)

---

## Executive Summary

### Objective
Implement dynamic trailing take-profit and stop-loss functionality in the Goldflipper options trading system to automatically adjust exit levels based on favorable price movements, maximizing profits while protecting against reversals.

### Key Benefits
- **Profit Maximization**: Capture extended trends beyond initial TP targets
- **Risk Reduction**: Protect profits with automatic stop adjustments
- **Automation**: Reduce manual intervention in position management
- **Flexibility**: Multiple trailing strategies (percentage, ATR, fixed amount)

### Scope
- Enhance existing play structure with trailing configurations
- Implement real-time trail level calculations and updates
- Integrate with existing monitoring and execution systems
- Provide user interfaces for trailing configuration and monitoring

---

## Current System Analysis

### Architecture Overview
```
Plays Directory Structure:
├── new/           # Plays awaiting entry conditions
├── open/          # Active positions being monitored
├── pending-opening/   # Orders submitted but not filled
├── pending-closing/   # Exit orders submitted but not filled
└── closed/        # Completed trades
```

### Key Components
1. **Play Structure**: JSON-based trade definitions with static TP/SL
2. **Monitoring Loop**: `monitor_plays_continuously()` checks conditions every cycle
3. **Condition Evaluation**: `evaluate_closing_strategy()` determines exit triggers
4. **Data Providers**: Real-time market data from Alpaca, YFinance, MarketDataApp
5. **Order Management**: Integration with Alpaca API for trade execution

### Current Limitations & How Trailing Stops Overcome Them

#### Limitation 1: Static Targets
**Current State**: TP/SL levels are calculated once at position entry based on entry price and never adjusted, regardless of subsequent price movements.

**Problem**: 
- A CALL option with entry at $100 stock price might set TP at $110 (10% move)
- If stock moves to $120, the TP remains at $110, missing potential profits from $110-120 range
- Similarly, SL remains at original level even if position becomes highly profitable

**Solution with Trailing**:
- **Dynamic Adjustment**: TP/SL levels automatically adjust as price moves favorably
- **Profit Maximization**: As stock moves from $110 to $120, trailing TP follows upward, capturing extended trends
- **Risk Reduction**: Trailing SL moves up with favorable price movements, protecting accumulated profits

#### Limitation 2: No Trend Following Capability
**Current State**: The system cannot distinguish between minor pullbacks and trend reversals, treating all price movements as potential exit signals.

**Problem**:
- Strong uptrends often have 2-3% pullbacks that would trigger static stops
- Missing 20-30% trends because of 5% initial stop loss
- No mechanism to "ride the wave" during strong directional moves
- Equal treatment of consolidation vs. trend continuation patterns

**Solution with Trailing**:
- **Trend Participation**: Allows positions to stay active during extended favorable moves
- **Volatility Adaptation**: ATR-based trailing adjusts to market volatility, avoiding premature exits during normal fluctuations
- **Momentum Capture**: System can now participate in multi-day/week trends instead of quick scalps
- **Pattern Recognition**: Different trail types for different market conditions (tight trails in choppy markets, loose trails in trending markets)

#### Limitation 3: Fixed Risk/Reward Ratios
**Current State**: Risk/reward is locked in at entry with no adaptation to changing market conditions or trade performance.

**Problem**:
- 2:1 risk/reward ratio maintained regardless of option Greeks changes
- No consideration for time decay acceleration near expiration
- Inflexible response to volatility expansion/contraction
- Same exit strategy for 1-day vs. 30-day options

**Solution with Trailing**:
- **Dynamic Risk Management**: Risk/reward improves as trails move favorably
- **Greeks-Aware Trailing**: Can integrate with existing Greeks calculations for smarter trail placement
- **Time-Adaptive Strategies**: Trail behavior can change based on days to expiration
- **Volatility-Responsive**: ATR-based trailing automatically adjusts to current market volatility
- **Profit Scaling**: As profits increase, trail distances can tighten to protect gains

#### Limitation 4: Manual Position Management
**Current State**: All position adjustments require manual intervention, creating delays and emotional decision-making risks.

**Problem**:
- Trader must manually monitor positions and decide on adjustments
- Emotional interference in exit decisions (fear of giving back profits)
- Inconsistent application of exit strategies across different trades
- Time-intensive monitoring required for multiple positions
- Risk of missing optimal exit points due to human limitations

**Solution with Trailing**:
- **Automated Execution**: Trail levels adjust automatically without human intervention
- **Consistent Application**: Same trailing logic applied to all positions uniformly
- **24/7 Monitoring**: Automated system never "sleeps" or gets distracted
- **Emotion-Free Decisions**: Systematic approach eliminates fear and greed from exit timing
- **Scalability**: Can manage unlimited positions simultaneously with consistent quality

#### Limitation 5: Inability to Adapt to Market Regime Changes
**Current State**: Static exit strategies cannot adapt to changing market conditions during the life of a trade.

**Problem**:
- Same exit strategy used during high volatility and low volatility periods
- No adjustment for market regime shifts (trending → choppy → trending)
- Fixed approach regardless of broader market conditions
- Cannot optimize for different underlying characteristics (high-beta vs. low-beta stocks)

**Solution with Trailing**:
- **Multi-Strategy Approach**: Different trail types available for different market conditions
- **Real-Time Adaptation**: ATR-based trails automatically adjust to current volatility
- **Conditional Activation**: Trails can activate only when certain market conditions are met
- **Asset-Specific Optimization**: Trail parameters can be optimized per underlying symbol
- **Market Phase Recognition**: Can implement different trailing strategies for trending vs. ranging markets

### Concrete Examples of Limitation Solutions

#### Example 1: Extended Trend Capture
**Scenario**: AAPL CALL option, entry at $150 stock price, original TP at $160 (6.67% move)

**Current System**:
- Position exits at $160 regardless of further movement
- If AAPL continues to $175, profits from $160-175 range are missed
- Total profit: $160 - $150 = $10 per share move

**With Trailing TP**:
- Trailing TP follows price upward with 3% trail distance
- As AAPL moves: $160 → $170 → $175, TP trails to $157 → $165 → $170
- Position captures extended trend until reversal
- Total profit: $170 - $150 = $20 per share move (100% improvement)

#### Example 2: Volatility-Adaptive Risk Management
**Scenario**: SPY PUT option during high volatility period (VIX > 30)

**Current System**:
- Fixed 5% stop loss triggers on normal volatility noise
- During high volatility, 5% moves are common intraday
- Premature exits from positions that would ultimately be profitable

**With ATR-Based Trailing**:
- ATR-based trails adjust to current volatility (e.g., 8% trail distance during high VIX)
- Trails automatically tighten during low volatility periods (3% trail distance)
- Significantly reduces false exits while maintaining protection

#### Example 3: Profit Protection in Winning Trades
**Scenario**: TSLA CALL option gains 40% profit, then market reverses

**Current System**:
- Original stop loss still at -25% from entry
- Position could go from +40% to -25% (65 percentage point swing)
- No protection of accumulated profits

**With Trailing SL**:
- As position reaches +40%, trailing SL moves to breakeven or small profit
- Maximum loss from peak becomes limited to trail distance (e.g., 5%)
- Position protected against giving back large gains

#### Example 4: Multi-Timeframe Position Management
**Scenario**: Options with different expiration periods require different management

**Current System**:
- Same TP/SL strategy regardless of 1 DTE vs. 30 DTE options
- No consideration for time decay acceleration
- Suboptimal exits for different time horizons

**With Dynamic Trailing**:
- Trail distances automatically adjust based on time to expiration
- Tighter trails for near-expiration options (higher gamma risk)
- Looser trails for longer-dated options (more time for trends to develop)
- Greeks-aware trailing that considers delta changes

### Quantifiable Improvements Expected

#### Performance Metrics Enhancement
- **Extended Profit Capture**: 25-40% improvement in average winning trade profit
- **Risk Reduction**: 60-80% reduction in maximum adverse excursion from profitable positions
- **Win Rate Maintenance**: Maintain current win rate while significantly improving profit per trade
- **Drawdown Protection**: 30-50% reduction in portfolio drawdowns during market reversals

#### Operational Efficiency Gains
- **Monitoring Time**: Eliminate manual position monitoring (currently ~2-3 hours/day)
- **Decision Consistency**: 100% consistent application of exit strategies across all trades
- **Scalability**: Ability to manage 5-10x more positions simultaneously
- **Emotional Trading Elimination**: Remove fear and greed from exit decisions entirely

#### Risk Management Improvements
- **Capital Preservation**: Protect 80-90% of peak profits in winning trades
- **Volatility Adaptation**: Reduce false exits by 50-70% during high volatility periods
- **Time Decay Management**: Optimize exits for options approaching expiration
- **Market Regime Adaptation**: Different strategies for trending vs. ranging markets

#### Strategic Advantages
- **Trend Participation**: Capture full trend moves instead of fixed profit targets
- **Market Adaptation**: Automatic adjustment to changing market conditions
- **Greeks Integration**: Exit strategies that consider option Greeks changes
- **Multi-Asset Optimization**: Asset-specific trailing parameters for different underlyings

---

## Requirements Specification

### Functional Requirements

#### FR-1: Trailing Take Profit
- **FR-1.1**: Enable/disable trailing TP per play
- **FR-1.2**: Support multiple trail calculation methods (percentage, ATR, fixed)
- **FR-1.3**: Configurable activation threshold before trailing begins
- **FR-1.4**: Minimum profit lock-in protection
- **FR-1.5**: Trail distance adjustment based on market conditions

#### FR-2: Trailing Stop Loss
- **FR-2.1**: Enable/disable trailing SL per play
- **FR-2.2**: Support multiple trail calculation methods
- **FR-2.3**: Breakeven protection (move SL to entry price when profitable)
- **FR-2.4**: Maximum loss protection (never trail beyond max loss percentage)
- **FR-2.5**: Integration with existing contingency SL logic

#### FR-3: Trail Management
- **FR-3.1**: Real-time trail level updates during monitoring cycles
- **FR-3.2**: Persistent storage of current trail levels and history
- **FR-3.3**: Trail adjustment frequency controls (prevent over-trading)
- **FR-3.4**: Historical tracking of all trail adjustments

#### FR-4: User Interface
- **FR-4.1**: Trail configuration during play creation
- **FR-4.2**: Trail parameter editing for existing plays
- **FR-4.3**: Real-time trail level display during monitoring
- **FR-4.4**: Trail history reporting and analysis

### Non-Functional Requirements

#### NFR-1: Performance
- Trail calculations must complete within 100ms per play
- No impact on existing monitoring cycle times
- Efficient memory usage for trail history storage

#### NFR-2: Reliability
- Trail state persistence across system restarts
- Graceful handling of data feed interruptions
- No loss of trail levels during system maintenance

#### NFR-3: Integration
- Seamless integration with all current data providers
- Clean integration with existing play structure
- Consistent API design with current system patterns

---

## Technical Design

### Trail Calculation Engine

#### Core Components
```
TrailingManager
├── TrailingCalculator      # Core calculation logic
├── TrailStateManager       # Persistence and state management
├── TrailConfigValidator    # Configuration validation
└── TrailHistoryLogger      # Audit trail and history
```

#### Trail Types Implementation

##### 1. Percentage-Based Trailing
```pseudocode
FUNCTION calculate_percentage_trail(current_price, trail_percentage, trade_type, peak_price):
    IF trade_type == "CALL":
        trail_level = peak_price * (1 - trail_percentage/100)
    ELSE:  // PUT
        trail_level = peak_price * (1 + trail_percentage/100)
    RETURN trail_level
```

##### 2. ATR-Based Trailing
```pseudocode
FUNCTION calculate_atr_trail(symbol, atr_multiplier, atr_period, trade_type, peak_price):
    atr_value = get_atr(symbol, atr_period)
    trail_distance = atr_value * atr_multiplier
    
    IF trade_type == "CALL":
        trail_level = peak_price - trail_distance
    ELSE:  // PUT
        trail_level = peak_price + trail_distance
    RETURN trail_level
```

##### 3. Fixed Amount Trailing
```pseudocode
FUNCTION calculate_fixed_trail(fixed_amount, trade_type, peak_price):
    IF trade_type == "CALL":
        trail_level = peak_price - fixed_amount
    ELSE:  // PUT
        trail_level = peak_price + fixed_amount
    RETURN trail_level
```

### Trail Update Logic
```pseudocode
FUNCTION update_trailing_levels(play, current_stock_price, current_premium):
    // Update peak favorable price tracking
    IF should_update_peak_price(current_stock_price, play):
        update_peak_price(play, current_stock_price)
    
    // Check and update trailing TP
    IF trailing_tp_enabled(play):
        new_tp_level = calculate_new_trail_level(play.take_profit.trailing_config)
        IF new_tp_level != play.take_profit.current_trail_level:
            update_trail_level(play, "TP", new_tp_level)
            log_trail_adjustment(play, "TP", new_tp_level)
    
    // Check and update trailing SL
    IF trailing_sl_enabled(play):
        new_sl_level = calculate_new_trail_level(play.stop_loss.trailing_config)
        IF new_sl_level != play.stop_loss.current_trail_level:
            update_trail_level(play, "SL", new_sl_level)
            log_trail_adjustment(play, "SL", new_sl_level)
```

### Integration with Existing Condition Evaluation
```pseudocode
FUNCTION evaluate_closing_strategy_enhanced(symbol, play):
    // Existing static condition checks
    static_conditions = evaluate_static_conditions(symbol, play)
    
    // New trailing condition checks
    trailing_conditions = {
        'tp_triggered': false,
        'sl_triggered': false
    }
    
    IF trailing_tp_enabled(play):
        current_price = get_current_price(symbol)
        trailing_conditions.tp_triggered = check_trailing_tp_trigger(current_price, play)
    
    IF trailing_sl_enabled(play):
        trailing_conditions.sl_triggered = check_trailing_sl_trigger(current_price, play)
    
    // Combine conditions
    RETURN combine_conditions(static_conditions, trailing_conditions)
```

---

## Data Structure Modifications

### Enhanced Play Template Schema

#### Take Profit Extensions
```json
{
  "take_profit": {
    "TP_type": "Single|Multiple|Trailing",
    "trailing_config": {
      "enabled": false,
      "trail_type": "percentage|atr|fixed_amount",
      "trail_distance_pct": 2.0,
      "trail_distance_fixed": 0.0,
      "atr_multiplier": 2.0,
      "atr_period": 14,
      "activation_threshold_pct": 5.0,
      "min_profit_lock_pct": 2.0,
      "update_frequency_seconds": 30
    },
    "trail_state": {
      "current_trail_level": null,
      "highest_favorable_price": null,
      "last_update_timestamp": null,
      "trail_activated": false
    }
  }
}
```

#### Stop Loss Extensions
```json
{
  "stop_loss": {
    "SL_type": "STOP|LIMIT|CONTINGENCY|TRAILING",
    "trailing_config": {
      "enabled": false,
      "trail_type": "percentage|atr|fixed_amount",
      "trail_distance_pct": 3.0,
      "trail_distance_fixed": 0.0,
      "atr_multiplier": 1.5,
      "atr_period": 14,
      "breakeven_protection": true,
      "max_loss_pct": 15.0,
      "update_frequency_seconds": 30
    },
    "trail_state": {
      "current_trail_level": null,
      "highest_favorable_price": null,
      "last_update_timestamp": null,
      "breakeven_activated": false
    }
  }
}
```

#### Trail History Tracking
```json
{
  "trail_history": [
    {
      "timestamp": "2024-01-15T14:30:00Z",
      "trail_type": "TP|SL",
      "old_level": 150.50,
      "new_level": 152.75,
      "trigger_price": 155.00,
      "reason": "favorable_movement|activation|breakeven"
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Objective**: Establish core trailing infrastructure

#### Tasks:
1. **Data Structure Setup**
   - Extend play template with trailing fields
   - Implement data validation for trailing configs
   - Create default trailing configurations

2. **Core Classes Development**
   - `TrailingCalculator` base class
   - `TrailStateManager` for persistence
   - `TrailConfigValidator` for input validation

3. **Basic Trail Types**
   - Implement percentage-based trailing
   - Add fixed amount trailing
   - Create unit tests for calculations

#### Deliverables:
- Extended play template schema
- Core trailing calculation classes
- Unit test suite for basic functionality

### Phase 2: Integration (Week 3-4)
**Objective**: Integrate trailing logic with existing monitoring system

#### Tasks:
1. **Monitoring Enhancement**
   - Modify `monitor_and_manage_position()` to include trail updates
   - Enhance `evaluate_closing_strategy()` with trailing conditions
   - Add trail state persistence to save operations

2. **ATR Implementation**
   - Add ATR calculation utilities
   - Implement ATR-based trailing
   - Integration with existing technical indicators

3. **Safety Features**
   - Activation threshold logic
   - Breakeven protection implementation
   - Maximum loss protection

#### Deliverables:
- Enhanced monitoring system with trailing support
- ATR-based trailing implementation
- Safety feature implementation

### Phase 3: User Interface (Week 5-6)
**Objective**: Provide user interfaces for trailing configuration and monitoring

#### Tasks:
1. **Play Creation Enhancement**
   - Add trailing configuration to `play_creation_tool.py`
   - Input validation and user guidance
   - Template selection for common trailing strategies

2. **Play Editing Enhancement**
   - Extend `play-edit-tool.py` with trailing parameter editing
   - Safety checks for editing open positions
   - Trail history viewing functionality

3. **Monitoring Display**
   - Real-time trail level display in monitoring output
   - Trail distance and trigger proximity indicators
   - Alert system for trail activations

#### Deliverables:
- Enhanced play creation tool with trailing support
- Extended play editing capabilities
- Improved monitoring display with trail information

### Phase 4: Advanced Features (Week 7-8)
**Objective**: Implement advanced trailing capabilities and optimizations

#### Tasks:
1. **Multi-Level Trailing**
   - Support for multiple TP levels with different trail distances
   - Cascading trail tightening as profits increase
   - Complex trailing strategies

2. **Performance Optimization**
   - Efficient trail calculation algorithms
   - Batch processing for multiple plays
   - Memory optimization for trail history

3. **Analytics and Reporting**
   - Trail performance analysis tools
   - Historical trail effectiveness reports
   - Strategy comparison utilities

#### Deliverables:
- Advanced trailing strategies
- Performance-optimized trail calculations
- Analytics and reporting tools

---

## Integration Strategy

### Integration Points

#### 1. Core Monitoring Loop
```pseudocode
// In monitor_and_manage_position()
BEFORE condition evaluation:
    IF has_trailing_enabled(play):
        update_trailing_levels(play, current_price, current_premium)
        save_trail_state(play, play_file)
```

#### 2. Condition Evaluation
```pseudocode
// In evaluate_closing_strategy()
AFTER static condition checks:
    IF trailing_enabled:
        trail_conditions = evaluate_trailing_conditions(play, current_price)
        merge_conditions(static_conditions, trail_conditions)
```

#### 3. Order Execution
```pseudocode
// In close_position()
WHEN creating exit orders:
    IF trailing_triggered:
        use_trail_level_as_limit_price(play.trail_state.current_trail_level)
        log_trail_execution(play, "triggered")
```

### Implementation Strategy
- All trailing fields included in standard play template
- Default trailing configurations for common strategies
- Comprehensive validation for trailing parameters
- Clean separation between trailing and static exit logic

### Error Handling Strategy
- Trail calculation failures fall back to static levels
- Data feed interruptions pause trail updates, don't reset trails
- Invalid trail configurations disable trailing with warnings
- Trail state corruption recovery using last known good state

---

## Risk Management

### Technical Risks

#### Risk 1: Performance Impact
**Description**: Trail calculations may slow down monitoring loops
**Mitigation**: 
- Implement efficient algorithms with O(1) complexity
- Cache ATR values and other expensive calculations
- Optional trail update frequency controls

#### Risk 2: Data Persistence Failures
**Description**: Trail state loss during system crashes
**Mitigation**:
- Atomic save operations for trail state
- Backup trail state to secondary location
- Recovery procedures for corrupted trail data

#### Risk 3: Integration Complexity
**Description**: Complex integration with existing systems
**Mitigation**:
- Phased rollout with feature flags
- Extensive testing in development environment
- Rollback procedures for each phase

### Trading Risks

#### Risk 1: Over-Trading
**Description**: Frequent trail adjustments leading to excessive trading costs
**Mitigation**:
- Minimum trail adjustment thresholds
- Update frequency controls
- Cost-benefit analysis for trail adjustments

#### Risk 2: Premature Exits
**Description**: Tight trailing stops triggering on normal volatility
**Mitigation**:
- ATR-based trail distances for volatility adaptation
- Activation thresholds to prevent premature trailing
- Backtesting on historical data for validation

#### Risk 3: Breakeven Lock-In
**Description**: Moving to breakeven too early, missing further profits
**Mitigation**:
- Configurable breakeven activation thresholds
- Minimum profit requirements before breakeven activation
- Trail type selection based on market conditions

---

## Testing Strategy

### Unit Testing
- **Trail Calculations**: Test all trail types with various market scenarios
- **State Management**: Test trail state persistence and recovery
- **Configuration Validation**: Test input validation and error handling

### Integration Testing
- **Monitoring Loop**: Test trail updates during normal monitoring cycles
- **Condition Evaluation**: Test integration with existing condition logic
- **Order Execution**: Test trail-triggered order placement

### End-to-End Testing
- **Complete Trade Lifecycle**: Test from play creation through trail execution
- **Multiple Play Types**: Test with CALL and PUT options
- **Market Scenarios**: Test during trending and volatile market conditions

### Performance Testing
- **Load Testing**: Test with maximum expected number of plays
- **Stress Testing**: Test under high-frequency market data updates
- **Memory Testing**: Test trail history memory usage over time

### User Acceptance Testing
- **Play Creation**: User testing of trailing configuration interface
- **Monitoring Display**: User feedback on trail information presentation
- **Play Editing**: User testing of trail parameter modification

---

## Success Metrics

### Technical Metrics
- **Performance**: Trail calculations complete in <100ms per play
- **Reliability**: 99.9% uptime for trail functionality
- **Accuracy**: Zero trail calculation errors in production

### Trading Metrics
- **Profit Enhancement**: 15% improvement in average trade profit
- **Risk Reduction**: 20% reduction in maximum adverse excursion
- **Win Rate**: Maintain or improve current win rate percentage

### User Experience Metrics
- **Adoption Rate**: 60% of new plays use trailing functionality within 3 months
- **User Satisfaction**: 90% positive feedback on trailing interface
- **Error Rate**: <1% user configuration errors

### System Metrics
- **Monitoring Cycle Time**: No increase in average cycle time
- **Memory Usage**: <10% increase in memory footprint
- **Data Storage**: Efficient trail history storage with <1MB per play

---

## Timeline & Dependencies

### Critical Path
1. **Week 1-2**: Foundation development
2. **Week 3-4**: Core integration
3. **Week 5-6**: User interface development
4. **Week 7-8**: Advanced features and optimization

### Dependencies
- **Market Data Providers**: Reliable real-time data feeds
- **ATR Calculation**: Integration with existing technical analysis tools
- **Database/Storage**: Sufficient storage for trail history
- **Testing Environment**: Ability to simulate various market conditions

### Milestones
- **End of Week 2**: Basic trailing calculations working
- **End of Week 4**: Full integration with monitoring system
- **End of Week 6**: Complete user interface implementation
- **End of Week 8**: Production-ready trailing system

### Risk Buffer
- Additional 2 weeks allocated for integration challenges
- Fallback plan to implement basic percentage trailing first
- Contingency for extended testing period if needed

---

## Conclusion

This implementation plan provides a comprehensive roadmap for adding trailing take-profit and stop-loss functionality to the Goldflipper trading system. The phased approach ensures minimal disruption to existing functionality while delivering significant value through enhanced trade management capabilities.

Key success factors:
- Implementing robust trailing algorithms with multiple strategy types
- Developing comprehensive error handling and recovery mechanisms
- Providing intuitive user interfaces for configuration and monitoring
- Ensuring performance requirements are met throughout development
- Creating flexible, extensible architecture for future enhancements

The trailing functionality will transform Goldflipper from a static exit strategy system to a dynamic, trend-following position management platform, significantly enhancing its effectiveness in various market conditions.