import yoptions as yo

# Chain of all FORD MOTOR COMPANY call options for next expiration date
# Chain of all FORD MOTOR COMPANY put options that expire on January 21, 2022

chain = yo.get_chain_greeks_date(stock_ticker='F', dividend_yield=0, option_type='p', 
                                 expiration_date='2022-01-21',risk_free_rate=None)
print(chain.head().to_string())