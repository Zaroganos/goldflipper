#!/usr/bin/env python
"""
Standalone script to run the JSON play file fixer utility.
This tool can be used to check and repair corrupted play files.

Usage:
    python run_json_fixer.py [--verbose] [--fix-only-file FILENAME]
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from goldflipper.utils.json_fixer import PlayFileFixer
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.utils.logging_setup import configure_logging

def setup_logging(verbose=False):
    """Configure logging with rotation for this tool."""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_path = Path(__file__).parent.parent.parent / 'logs' / 'json_fixer.log'
    configure_logging(console_mode=False, service_mode=False, log_file=log_path, level_override=log_level)

def run_fixer(verbose=False, specific_file=None):
    """Run the JSON fixer with optional parameters."""
    display.header("JSON Play File Fixer Utility")
    display.info("Checking for corrupted play files...")
    
    fixer = PlayFileFixer()
    
    if specific_file:
        # Modify the PlayFileFixer to check only a specific file
        original_get_play_files = fixer._get_play_files
        
        def get_specific_file():
            all_files = original_get_play_files()
            # Filter for the specific file
            return [f for f in all_files if f.name == specific_file or str(f).endswith(specific_file)]
        
        # Override the method
        fixer._get_play_files = get_specific_file
    
    fixed_count = fixer.check_and_fix_all_plays()
    
    if fixed_count > 0:
        display.success(f"Fixed {fixed_count} corrupted play files")
    else:
        display.info("No corrupted play files found or fixed")
    
    return fixed_count

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='JSON Play File Fixer Utility')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Enable verbose logging')
    parser.add_argument('--fix-only-file', '-f', type=str,
                      help='Fix only a specific file (filename or path)')
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    
    try:
        fixed_count = run_fixer(
            verbose=args.verbose,
            specific_file=args.fix_only_file
        )
        
        sys.exit(0 if fixed_count >= 0 else 1)
    except Exception as e:
        logging.error(f"Error running JSON fixer: {str(e)}")
        display.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 