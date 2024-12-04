import yoptions as yo
import time
from requests.exceptions import HTTPError

def fetch_option_data(stock_ticker, option_type='c', expiration_date=None, dividend_yield=0, risk_free_rate=None, max_retries=3):
    """
    Fetches the option chain with Greeks for a given stock ticker.

    :param stock_ticker: The stock ticker symbol (e.g., 'AAPL')
    :param option_type: The type of options to fetch ('c' for calls, 'p' for puts)
    :param expiration_date: Optional specific expiration date in 'YYYY-MM-DD' format
    :param dividend_yield: The dividend yield of the stock
    :param risk_free_rate: The risk-free interest rate
    :param max_retries: Maximum number of retry attempts
    :return: A tuple containing (option_chain, stock_price, available_dates)
    """
    for attempt in range(max_retries):
        try:
            # Add a small delay between retries
            if attempt > 0:
                time.sleep(2)

            # Get available expiration dates
            expiration_dates = yo.get_expiration_dates(stock_ticker)
            
            # Fetch the option chain with Greeks
            if expiration_date:
                chain = yo.get_chain_greeks_date(
                    stock_ticker=stock_ticker,
                    dividend_yield=dividend_yield,
                    option_type=option_type,
                    expiration_date=expiration_date,
                    risk_free_rate=risk_free_rate
                )
            else:
                chain = yo.get_chain_greeks(
                    stock_ticker=stock_ticker,
                    dividend_yield=dividend_yield,
                    option_type=option_type,
                    risk_free_rate=risk_free_rate
                )
            
            # Get current stock price using the first option in the chain
            if not chain.empty:
                first_option = chain['Symbol'].iloc[0]
                stock_price = yo.get_underlying_price(first_option)
            else:
                stock_price = None
                
            return chain, stock_price, expiration_dates
            
        except HTTPError as e:
            if e.response.status_code == 401:
                print(f"Authentication error (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    print("Failed to authenticate with Yahoo Finance. This might be due to:")
                    print("1. Rate limiting")
                    print("2. IP restrictions")
                    print("3. Changes in Yahoo Finance's API")
            else:
                print(f"HTTP Error {e.response.status_code} occurred (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"An error occurred: {str(e)} (attempt {attempt + 1}/{max_retries})")
            if attempt == max_retries - 1:
                break
    
    return None, None, None

def main():
    # Example usage
    stock_ticker = 'AAPL'  # Replace with your desired stock ticker
    option_type = 'c'  # 'c' for call options, 'p' for put options
    expiration_date = None  # Optional: specify date in 'YYYY-MM-DD' format
    dividend_yield = 0  # Replace with the actual dividend yield if known
    risk_free_rate = None  # Replace with the actual risk-free rate if known

    option_data, stock_price, dates = fetch_option_data(
        stock_ticker, 
        option_type, 
        expiration_date,
        dividend_yield, 
        risk_free_rate
    )
    
    if option_data is not None:
        print(f"\nCurrent stock price: ${stock_price:.2f}")
        print("\nAvailable expiration dates:", dates)
        print("\nOption chain:")
        print(option_data.head().to_string())
    else:
        print("Failed to fetch option data.")

if __name__ == "__main__":
    main()
