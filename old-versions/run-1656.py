from goldflipper.core import execute_trade
import sys
import os
import logging

print(f"Python path in run.py: {sys.path}")
print(f"Current working directory in run.py: {os.getcwd()}")

def execute_all_plays():
    # Path to the plays directory
    plays_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'plays'))
    
    # Log the directory being used
    print(f"Looking for play files in directory: {plays_dir}")

    # Ensure the plays directory exists
    if not os.path.exists(plays_dir):
        print(f"Error: Plays directory does not exist at {plays_dir}")
        return
    
    # Iterate over all JSON files in the plays directory
    for play_file in os.listdir(plays_dir):
        if play_file.endswith(".json"):
            full_path = os.path.join(plays_dir, play_file)
            print(f"Executing play: {full_path}")
            
            # Execute the play
            try:
                execute_trade(full_path)
            except Exception as e:
                logging.error(f"Error executing play {full_path}: {e}")
                print(f"Error executing play {full_path}: {e}")

if __name__ == "__main__":
    execute_all_plays()
