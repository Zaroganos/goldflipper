import json
import os

def load_play(filepath):
    """
    Loads a play from a JSON file and returns it as a dictionary.

    Parameters:
    - filepath (str): The path to the JSON file.

    Returns:
    - dict: The parsed JSON data.
    - None: If there is an error loading the file.
    """
    try:
        with open(filepath, 'r') as f:
            play_data = json.load(f)
            
        if not isinstance(play_data, dict):
            print(f"Play file {filepath} loaded but data is not a dictionary. Type: {type(play_data)}")
            return None
            
        # Validate required fields
        required_fields = ['symbol', 'expiration_date', 'trade_type', 'strike_price', 'status']
        missing_fields = [field for field in required_fields if field not in play_data]
        
        if missing_fields:
            print(f"Play file {filepath} missing required fields: {missing_fields}")
            return None
            
        # Ensure status is a dictionary
        if not isinstance(play_data.get('status'), dict):
            play_data['status'] = {
                'play_status': 'NEW',
                'order_id': None,
                'order_status': None,
                'position_exists': False,
                'last_checked': None,
                'closing_order_id': None,
                'closing_order_status': None,
                'contingency_order_id': None,
                'contingency_order_status': None,
                'conditionals_handled': False
            }
            
        return play_data
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {filepath}: {e}")
        return None
    except Exception as e:
        print(f"Error loading play from {filepath}: {e}")
        return None

# Example usage within the goldflipper project structure
if __name__ == "__main__":
    # Correct the path to the plays directory by ensuring the path is absolute
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plays_dir = os.path.abspath(os.path.join(script_dir, 'plays'))

    # Ensure the plays directory exists before trying to list files
    if not os.path.exists(plays_dir):
        print(f"Plays directory not found: {plays_dir}")
    else:
        # List all JSON files in the plays directory
        play_files = [os.path.join(plays_dir, f) for f in os.listdir(plays_dir) if f.endswith('.json')]

        # Load and print each play
        for play_file in play_files:
            play_data = load_play(play_file)
            if play_data:
                print("Loaded play:", play_data)
            else:
                print(f"Failed to load play from {play_file}")
