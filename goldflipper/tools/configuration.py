import os
import sys
import subprocess
import platform
import shutil

def open_settings():
    """Open settings.yaml file with the system's default editor."""
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = os.path.join(current_dir, 'config', 'settings.yaml')
    
    if not os.path.exists(settings_path):
        # Settings file doesn't exist - create it from template
        template_path = os.path.join(current_dir, 'config', 'settings_template.yaml')
        
        if not os.path.exists(template_path):
            print(f"Error: Template file not found at {template_path}")
            return False
            
        try:
            # Copy the template to settings.yaml
            shutil.copy2(template_path, settings_path)
            print(f"\nCreated new settings file from template.")
            print(f"Please review and update the settings with your API keys and preferences.")
        except Exception as e:
            print(f"Error creating settings file from template: {e}")
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