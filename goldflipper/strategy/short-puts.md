## Strategy Parameters

The tastytrade approach recommends selling options with approximately 45 days to expiration (DTE), targeting options with around a 30 delta, taking profit when collecting 50% of the premium, and rolling positions at 21 DTE to manage gamma risk.

### Key Parameters:

1. **Days to Expiration (DTE):** 45 DTE
    
2. **Delta:** 30 delta
    
3. **Entry Conditions:** Sell options when implied volatility (IV) is high
    
4. **Profit Target:** Take profit when you collect 50% of the premium
    
5. **Roll/Exit:** Roll forward at 21 DTE without changing the strike price to reduce gamma risk
    
6. **Position Sizing:** Don't use more than 40-50% of available capital on overall portfolio and don't exceed 3x notional leverage
    

## Pseudocode

```
INITIALIZE:
    account_size = YOUR_ACCOUNT_SIZE
    max_capital_allocation = account_size * 0.50
    max_notional = account_size * 3.0
    
SCAN_FOR_ENTRY:
    underlying = SPY
    target_dte = 45  // Target 45 DTE (typically 35-49 range)
    target_delta = 0.30  // 30 delta put
    
    IF current_dte >= 35 AND current_dte <= 49:
        IF IV_rank >= 50:  // Only trade when IV is elevated
            
            // Find put option closest to 30 delta
            put_option = FIND_OPTION(
                underlying = SPY,
                option_type = PUT,
                dte = target_dte,
                delta = target_delta
            )
            
            credit_received = put_option.ask_price * 100
            buying_power_required = CALCULATE_BP_REQUIREMENT(put_option)
            
            // Position sizing checks
            IF buying_power_required <= max_capital_allocation:
                IF total_notional_exposure <= max_notional:
                    SELL_PUT(put_option)
                    RECORD:
                        entry_credit = credit_received
                        entry_date = TODAY
                        strike_price = put_option.strike
                        expiration_date = put_option.expiration
                        profit_target = credit_received * 0.50

MANAGE_POSITION:
    FOR EACH open_position IN portfolio:
        current_value = GET_CURRENT_PRICE(open_position)
        days_remaining = open_position.expiration - TODAY
        pnl = open_position.entry_credit - current_value
        
        // Profit target: 50% of credit
        IF pnl >= open_position.profit_target:
            BUY_TO_CLOSE(open_position)
            LOG("Profit target reached")
        
        // Roll at 21 DTE
        ELSE IF days_remaining <= 21:
            // Roll to next cycle, same delta
            new_option = FIND_OPTION(
                underlying = SPY,
                option_type = PUT,
                dte = 45,
                delta = 0.30
            )
            BUY_TO_CLOSE(open_position)
            SELL_PUT(new_option)
            LOG("Rolled to next expiration")
        
        // Optional: Stop loss if position doubles
        ELSE IF current_value >= (open_position.entry_credit * 2):
            BUY_TO_CLOSE(open_position)
            LOG("Stop loss triggered")

RISK_MANAGEMENT:
    // Monitor overall exposure
    total_bp_used = SUM(buying_power FOR EACH position)
    total_notional = SUM(strike_price * 100 FOR EACH position)
    
    IF total_bp_used > max_capital_allocation:
        ALERT("Exceeding capital allocation limit")
    
    IF total_notional > max_notional:
        ALERT("Exceeding notional leverage limit")

REPEAT daily
```