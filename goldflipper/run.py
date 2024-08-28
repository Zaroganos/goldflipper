from goldflipper.core import execute_trade
import sys
import os

print(f"Python path in run.py: {sys.path}")
print(f"Current working directory in run.py: {os.getcwd()}")

if __name__ == "__main__":
    # Specify the path to the sample play
    play_file = r"C:\Users\Iliya\Documents\GitHub\goldflipper\plays\sample_play.json"
    execute_trade(play_file)


# import sys
# import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'goldflipper')))
# from goldflipper.core import execute_trade

# if __name__ == "__main__":
#    execute_trade()