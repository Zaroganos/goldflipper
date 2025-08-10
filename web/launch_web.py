#!/usr/bin/env python3

import os
import sys
import yaml
import subprocess
from pathlib import Path
import traceback
from datetime import datetime

project_root = Path(__file__).parent.parent

# Load .env.bat if present to set GOLDFLIPPER_DATA_DIR; don't override if already set
env_bat = project_root.parent / '.env.bat'
try:
    if not os.getenv('GOLDFLIPPER_DATA_DIR') and env_bat.exists():
        # Use cmd to parse the bat and output the var
        import subprocess
        cmd = ["cmd.exe", "/c", f"call \"{env_bat}\" && echo %GOLDFLIPPER_DATA_DIR%"]
        out = subprocess.check_output(cmd, text=True).strip()
        if out:
            os.environ['GOLDFLIPPER_DATA_DIR'] = out
except Exception:
    pass

# Add project root to Python path
sys.path.insert(0, str(project_root))

def main():
    try:
        # Set up logging
        log_file = Path(__file__).parent / 'launch_debug.log'
        with open(log_file, 'w') as f:
            f.write(f"Starting launch_web.py at {datetime.now()}\n")
            

            # Default to hidden console
            show_console = False
            script_dir = Path(__file__).parent
            
            # Check if Poetry is installed
            try:
                subprocess.run(['poetry', '--version'], capture_output=True, check=True)
                f.write("Poetry is installed\n")
            except subprocess.CalledProcessError:
                f.write("Installing Poetry...\n")
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install", "poetry"], check=True)
                    f.write("Poetry installed successfully\n")
                except subprocess.CalledProcessError as e:
                    f.write(f"Error installing Poetry: {str(e)}\n")
                    return
            
            # Install dependencies using Poetry
            f.write("Installing dependencies with Poetry...\n")
            try:
                subprocess.run(['poetry', 'install'], check=True)
                f.write("Dependencies installed successfully\n")
            except subprocess.CalledProcessError as e:
                f.write(f"Error installing dependencies: {str(e)}\n")
                return
            
            # Launch Streamlit app
            f.write(f"Current working directory: {os.getcwd()}\n")
            f.write(f"Launching Streamlit app...\n")
            
            try:
                if show_console:
                    # For visible console, let Streamlit output directly
                    subprocess.Popen(['poetry', 'run', 'streamlit', 'run', str(script_dir / 'app.py')], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    # For hidden console, use Popen with CREATE_NO_WINDOW
                    subprocess.Popen(['poetry', 'run', 'streamlit', 'run', str(script_dir / 'app.py')], creationflags=subprocess.CREATE_NO_WINDOW)
                
                f.write("Streamlit app launched successfully\n")
            except Exception as e:
                f.write(f"Error launching Streamlit app: {str(e)}\n")
                print(f"Error launching Streamlit app: {str(e)}")
                return

    except Exception as e:
        with open(log_file, 'a') as f:
            f.write(f"\nError occurred:\n{str(e)}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")
        raise

if __name__ == "__main__":
    main() 