import os
import sys
import subprocess
import platform

def open_settings():
    """Open settings.yaml file with the system's default editor."""
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
    
    if not os.path.exists(settings_path):
        print(f"Error: Settings file not found at {settings_path}")
        return False
        
    try:
        if platform.system() == 'Windows':
            os.startfile(settings_path)  # Windows will use default application
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', settings_path])
        else:  # Linux and other Unix-like
            subprocess.run(['xdg-open', settings_path])
        
        print("\nSettings file opened in default editor.")
        print("Please save and close the editor when you're finished.")
        input("\nPress Enter when you're done editing...")
        return True
            
    except Exception as e:
        print(f"\nError opening settings file: {e}")
        return False

def main():
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Open settings file
    if not open_settings():
        print("\nUnable to configure settings. Please check the file permissions and try again.")
        sys.exit(1)
    
    print("\nConfiguration complete!")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 