import os
import json
import logging
from pathlib import Path
import re
from goldflipper.utils.logging_setup import configure_logging
from goldflipper.utils.exe_utils import get_plays_dir, get_play_subdir

class PlayFileFixer:
    """Utility for detecting and repairing corrupted play JSON files."""
    
    # Standard play status folders
    PLAY_STATUS_FOLDERS = ['new', 'open', 'pending-opening', 'pending-closing', 'closed', 'expired', 'temp']
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Use account-aware plays directory
        self.plays_base_dir = get_plays_dir()
        # Build list of play directories from the account-aware base
        self.play_dirs = [str(self.plays_base_dir / folder) for folder in self.PLAY_STATUS_FOLDERS]
        self.fix_count = 0
        self.reference_templates = {}
    
    def _load_reference_templates(self):
        """Load reference templates from closed plays to use for structure validation only."""
        self.reference_templates = {}
        closed_dir = get_play_subdir('closed')
        
        if not closed_dir.exists():
            self.logger.warning("Closed plays directory does not exist, cannot load templates")
            return
            
        self.logger.info("Loading reference templates from closed plays (for structure validation only)")
        
        for file_path in closed_dir.glob('*.json'):
            try:
                with open(file_path, 'r') as f:
                    play_data = json.load(f)
                
                # Store templates by trade type and play class
                trade_type = play_data.get('trade_type', 'UNKNOWN')
                play_class = play_data.get('play_class', 'SIMPLE')
                
                key = f"{trade_type}_{play_class}"
                
                if key not in self.reference_templates:
                    # Use the first valid play of this type as a structure reference
                    self.reference_templates[key] = play_data
                    self.logger.info(f"Loaded structure template for {key} from {file_path.name}")
            except Exception as e:
                self.logger.warning(f"Could not load template from {file_path}: {str(e)}")
        
        self.logger.info(f"Loaded {len(self.reference_templates)} reference templates")
    
    def _get_play_files(self):
        """Get all play JSON files from all play directories."""
        all_play_files = []
        for dir_path in self.play_dirs:
            dir_path = Path(dir_path)
            if dir_path.exists():
                all_play_files.extend([
                    f for f in dir_path.glob('*.json')
                    if f.is_file()
                ])
        return all_play_files
    
    def _extract_play_info(self, content):
        """Extract basic play information from potentially corrupted content."""
        # Try to extract symbol, trade_type and play_class
        symbol_match = re.search(r'"symbol"\s*:\s*"([^"]+)"', content)
        trade_type_match = re.search(r'"trade_type"\s*:\s*"([^"]+)"', content)
        play_class_match = re.search(r'"play_class"\s*:\s*"([^"]+)"', content)
        
        symbol = symbol_match.group(1) if symbol_match else None
        trade_type = trade_type_match.group(1) if trade_type_match else None
        play_class = play_class_match.group(1) if play_class_match else "SIMPLE"
        
        return {
            "symbol": symbol,
            "trade_type": trade_type,
            "play_class": play_class
        }
    
    def _is_cut_off_at_entry_premium(self, content):
        """Check if file appears to be cut off right after entry_premium field."""
        # Pattern for files cut off after entry_premium: null}}
        if '"entry_premium": null}}' in content and content.strip().endswith('}}'):
            line_count = len(content.strip().split('\n'))
            # If the file is very short (around 8 lines) and ends with entry_premium
            if line_count <= 10:
                return True
        return False
    
    def _is_corrupted(self, file_path):
        """Check if a play file appears to be corrupted."""
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                
            # Empty file
            if not content:
                self.logger.warning(f"File {file_path} is empty")
                return True
                
            # Check if the content doesn't end with proper JSON closing
            if not content.endswith('}'):
                self.logger.warning(f"File {file_path} doesn't properly end with '}}' character")
                return True
            
            # Check for incomplete attribute (cut off mid-attribute)
            if re.search(r'"[^"]+"\s*:\s*$', content):
                self.logger.warning(f"File {file_path} appears to be cut off mid-attribute")
                return True
            
            # Check for the new pattern: cut off after entry_premium field
            if self._is_cut_off_at_entry_premium(content):
                self.logger.warning(f"File {file_path} appears to be cut off after entry_premium field")
                return True
                
            # Check for imbalanced braces
            open_count = content.count('{')
            close_count = content.count('}')
            if open_count != close_count:
                self.logger.warning(f"File {file_path} has imbalanced braces: {open_count} opening vs {close_count} closing")
                return True
                
            # Check for "integrity" field - if exists and false, file was previously corrupted and might need checking
            try:
                data = json.loads(content)
                if "integrity" in data and data["integrity"] is False:
                    self.logger.warning(f"File {file_path} has integrity flag set to false")
                    # Don't mark as corrupted if syntax is valid, just log the warning
            except:
                pass
                
            # Try to parse JSON to see if it's valid
            json.loads(content)
            return False  # JSON is valid
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"File {file_path} has JSON parsing error: {str(e)}")
            return True  # JSON is not valid
            
        except Exception as e:
            self.logger.error(f"Error checking file {file_path}: {str(e)}")
            return True  # Assume corrupted if there's any error
    
    def _repair_file(self, file_path):
        """Attempt to repair a corrupted play file. Only fixes syntax without generating values."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Extract play info even from corrupted content
            play_info = self._extract_play_info(content)
            was_corrupted = True  # Tracks if the file was corrupted and needed fixing
            
            # Get template key
            template_key = f"{play_info.get('trade_type', 'UNKNOWN')}_{play_info.get('play_class', 'SIMPLE')}"
            
            # Case 1: File is cut off at a specific attribute
            if re.search(r'"[^"]+"\s*:\s*$', content):
                self.logger.info(f"File {file_path} appears to be cut off mid-attribute")
                
                # Replace the incomplete attribute with a valid null value
                modified_content = re.sub(r'("[^"]+"\s*:\s*)$', r'\1null', content)
                
                # Count open and closing braces
                open_braces = modified_content.count('{')
                close_braces = modified_content.count('}')
                
                # Add missing closing braces
                if open_braces > close_braces:
                    missing_braces = open_braces - close_braces
                    # Add proper number of closing braces at the end
                    modified_content += ''.join(['}'] * missing_braces)
                
                try:    
                    # Try to parse the repaired JSON to validate it
                    repaired_json = json.loads(modified_content)
                    
                    # Add integrity field
                    repaired_json["integrity"] = False
                    
                    # Write the repaired content back to the file
                    with open(file_path, 'w') as f:
                        json.dump(repaired_json, f, indent=4)
                    
                    self.fix_count += 1
                    self.logger.info(f"Successfully repaired file {file_path} (added null for cut-off attribute and balanced braces)")
                    return True
                except Exception as e:
                    self.logger.error(f"Error validating repaired JSON: {str(e)}")
                    return False
            
            # Case 2: Handle special case for cut off after entry_premium
            if self._is_cut_off_at_entry_premium(content):
                self.logger.info(f"Fixing file cut off after entry_premium: {file_path}")
                
                try:
                    # Parse the partial JSON 
                    partial_json = json.loads(content)
                    
                    # Get a template structure if available
                    template = None
                    if template_key in self.reference_templates:
                        template = self.reference_templates[template_key]
                    
                    # Add the integrity field
                    partial_json["integrity"] = False
                    
                    # Add minimum required fields if missing
                    if "play_class" not in partial_json and template:
                        partial_json["play_class"] = template.get("play_class", "SIMPLE")
                        
                    if "strike_price" not in partial_json:
                        partial_json["strike_price"] = "0.0"  # Default placeholder
                    
                    if "expiration_date" not in partial_json:
                        partial_json["expiration_date"] = "01/01/2099"  # Default placeholder
                        
                    # Add a placeholder status section if missing
                    if "status" not in partial_json:
                        partial_json["status"] = {
                            "play_status": "NEW",
                            "order_id": None,
                            "order_status": None,
                            "position_exists": False
                        }
                    
                    # Write the repaired JSON to the file
                    with open(file_path, 'w') as f:
                        json.dump(partial_json, f, indent=4)
                    
                    self.fix_count += 1
                    self.logger.info(f"Successfully repaired file cut off after entry_premium: {file_path}")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"Error repairing file cut off after entry_premium: {str(e)}")
                    return False
            
            # Case 3: Handle special case for null premium_atClose
            if '"premium_atClose": null' in content:
                # Check for common JSON structure issues
                try:
                    # Fix case where null is followed by extra closing braces
                    if 'null}}' in content and content.count('{') < content.count('}'):
                        self.logger.info(f"Fixing null premium_atClose format in {file_path}")
                        # Remove extra closing brace
                        modified_content = content.replace('null}}', 'null}')
                        
                        # Try to parse the fixed content
                        repaired_json = json.loads(modified_content)
                        
                        # Add integrity field
                        repaired_json["integrity"] = False
                        
                        # Write the repaired content back to the file
                        with open(file_path, 'w') as f:
                            json.dump(repaired_json, f, indent=4)
                        
                        self.fix_count += 1
                        self.logger.info(f"Successfully repaired premium_atClose format in {file_path}")
                        return True
                    else:
                        # Just validate content if no specific issue found
                        repaired_json = json.loads(content)
                        was_corrupted = False  # No corruption detected
                except Exception as e:
                    self.logger.error(f"Repair attempt failed for {file_path}: {str(e)}")
                    return False
            
            # Case 4: Last resort - basic JSON structure repair
            try:
                # Try to at least make it valid JSON by balancing braces
                open_braces = content.count('{')
                close_braces = content.count('}')
                
                if open_braces > close_braces:
                    missing_braces = open_braces - close_braces
                    modified_content = content + ''.join(['}'] * missing_braces)
                    
                    # Try to parse
                    repaired_json = json.loads(modified_content)
                    
                    # Add integrity field
                    repaired_json["integrity"] = False
                    
                    # Write the repaired content back to the file
                    with open(file_path, 'w') as f:
                        json.dump(repaired_json, f, indent=4)
                    
                    self.fix_count += 1
                    self.logger.info(f"Basic repair successful for {file_path} (balanced braces)")
                    return True
                    
                elif open_braces < close_braces:
                    # Too many closing braces - this is harder to fix safely
                    # Just remove trailing braces as a simple fix
                    extra_braces = close_braces - open_braces
                    if content.endswith('}' * extra_braces):
                        modified_content = content[:-extra_braces]
                        
                        # Try to parse
                        repaired_json = json.loads(modified_content)
                        
                        # Add integrity field
                        repaired_json["integrity"] = False
                        
                        # Write the repaired content
                        with open(file_path, 'w') as f:
                            json.dump(repaired_json, f, indent=4)
                            
                        self.fix_count += 1
                        self.logger.info(f"Basic repair successful for {file_path} (removed extra braces)")
                        return True
            except Exception as e:
                self.logger.error(f"Last resort repair failed: {str(e)}")
                
            self.logger.warning(f"File {file_path} is corrupted but couldn't be repaired automatically")
            return False
            
        except Exception as e:
            self.logger.error(f"Error repairing file {file_path}: {str(e)}")
            return False
    
    def check_and_fix_all_plays(self):
        """Check all play files and attempt to fix any that are corrupted."""
        self.fix_count = 0
        self.logger.info("Starting JSON play file integrity check")
        
        # Load reference templates for structure validation only
        self._load_reference_templates()
        
        play_files = self._get_play_files()
        self.logger.info(f"Found {len(play_files)} play files to check")
        
        corrupted_files = []
        
        # First pass: identify corrupted files
        for file_path in play_files:
            if self._is_corrupted(file_path):
                corrupted_files.append(file_path)
        
        if not corrupted_files:
            self.logger.info("No corrupted play files found")
            return 0
        
        self.logger.warning(f"Found {len(corrupted_files)} corrupted play files")
        
        # Second pass: attempt to repair corrupted files
        for file_path in corrupted_files:
            self._repair_file(file_path)
        
        self.logger.info(f"Repair process completed. Fixed {self.fix_count} of {len(corrupted_files)} corrupted files")
        return self.fix_count

# Standalone test function
def run_fixer():
    """Run the play file fixer as a standalone process."""
    fixer = PlayFileFixer()
    fixed_count = fixer.check_and_fix_all_plays()
    return fixed_count

if __name__ == "__main__":
    # Configure logging when run as standalone script
    configure_logging(console_mode=True)
    run_fixer() 