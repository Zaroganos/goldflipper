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
            play = json.load(f)
        return play
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
