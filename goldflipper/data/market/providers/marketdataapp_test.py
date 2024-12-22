import asyncio
from goldflipper.data.market.providers.marketdataapp_provider import MarketDataAppProvider

async def fetch_option_data(option_symbol: str):
    """Fetch and display option data for a given symbol."""
    provider = MarketDataAppProvider()
    
    try:
        # Fetch option data
        option_data = provider.get_option_greeks(option_symbol)
        
        # Display the data in a human-readable format
        print(f"Option Data for {option_symbol}:")
        for key, value in option_data.items():
            print(f"{key.capitalize()}: {value}")
    
    except Exception as e:
        print(f"Error fetching data for {option_symbol}: {str(e)}")

def main():
    # Prompt user for option symbol
    option_symbol = input("Enter the option symbol: ").strip()
    
    # Run the async function
    asyncio.run(fetch_option_data(option_symbol))

if __name__ == "__main__":
    main()
