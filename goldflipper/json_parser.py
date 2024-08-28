import json
import os
import logging

# ==================================================
# JSON PLAY PARSING AND VALIDATION
# ==================================================
# This module handles reading and validating JSON files that define trading plays.
# The plays are defined according to a template provided by your strategist.

def load_play(file_path):
    """
    Load and validate a JSON play file.

    Parameters:
    - file_path (str): The path to the JSON file containing the play.

    Returns:
    - dict: The parsed play as a dictionary, if valid.
    """
    logging.info(f"Loading play from {file_path}...")
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return None

    try:
        with open(file_path, 'r') as file:
            play_data = json.load(file)
            logging.info("Play loaded successfully.")
            # Optionally: validate the structure here
            return play_data
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {e}")
        return None
