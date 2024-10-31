import os
import sys
import json

def display_license():
    """Display the license content and wait for user input."""
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    license_path = os.path.join(current_dir, "LICENSE")
    
    try:
        with open(license_path, 'r') as f:
            print(f.read())
    except FileNotFoundError:
        print("LICENSE file not found. Please contact Purpleaf LLC for licensing information.")
    
    input("\nBy proceeding, you acknowledge and agree to the terms of the license.\nPress Enter to continue...")

def get_trading_environment():
    """Get user choice for trading environment."""
    while True:
        choice = input("\nSelect trading environment:\n1. Paper Trading\n2. Live Trading\n\nChoice (1/2): ").strip()
        if choice == "1":
            return "paper", "https://paper-api.alpaca.markets"
        elif choice == "2":
            return "live", "https://api.alpaca.markets"
        print("Invalid choice. Please enter 1 or 2.")

def get_api_credentials():
    """Get API credentials from user."""
    print("\nPlease enter your Alpaca API credentials:")
    api_key = input("API Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    return api_key, secret_key

def update_config(api_key, secret_key, base_url):
    """Update the config.py file with new credentials."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                              'config', 'config.py')
    
    try:
        with open(config_path, 'r') as f:
            lines = f.readlines()
        
        # Update the relevant lines while preserving comments
        for i, line in enumerate(lines):
            if line.startswith('ALPACA_API_KEY'):
                lines[i] = f"ALPACA_API_KEY = '{api_key}'\n"
            elif line.startswith('ALPACA_SECRET_KEY'):
                lines[i] = f"ALPACA_SECRET_KEY = '{secret_key}'\n"
            elif line.startswith('ALPACA_BASE_URL'):
                lines[i] = f"ALPACA_BASE_URL = '{base_url}'  # Use the paper trading URL for testing\n"
        
        with open(config_path, 'w') as f:
            f.writelines(lines)
            
        print("\nConfiguration updated successfully!")
        
    except Exception as e:
        print(f"\nError updating configuration: {e}")

def main():
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Display license and wait for acknowledgment
    display_license()
    
    # Get trading environment choice
    env_type, base_url = get_trading_environment()
    
    # Get API credentials
    api_key, secret_key = get_api_credentials()
    
    # Update configuration
    update_config(api_key, secret_key, base_url)
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 