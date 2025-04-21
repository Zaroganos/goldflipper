#!/usr/bin/env python
"""
Test script for the JSON play file fixer utility.
This script creates test files with various corruption patterns and tests the repair functionality.
"""

import os
import sys
import json
import logging
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from goldflipper.utils.json_fixer import PlayFileFixer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_environment():
    """Create a temporary test environment with play directories and files."""
    test_dir = Path(tempfile.mkdtemp())
    logger.info(f"Created test directory: {test_dir}")
    
    # Create directories structure
    play_dirs = [
        'plays/new',
        'plays/open',
        'plays/pending-opening',
        'plays/pending-closing',
        'plays/closed',
        'plays/expired',
        'plays/temp'
    ]
    
    for dir_path in play_dirs:
        (test_dir / dir_path).mkdir(parents=True, exist_ok=True)
    
    return test_dir

def create_template_play_file(path, trade_type="PUT", play_class="SIMPLE"):
    """Create a template play file for testing based on a complete play lifecycle."""
    template_play = {
        "symbol": "QQQ",
        "trade_type": trade_type,
        "entry_point": {
            "stock_price": 503.85,
            "order_type": "limit at bid",
            "entry_stock_price": 504.01,
            "entry_premium": 8.77
        },
        "strike_price": "499.0",
        "expiration_date": "03/21/2025",
        "contracts": 1,
        "option_contract_symbol": f"QQQ250321{trade_type[0]}00499000",
        "play_name": f"QQQ-{trade_type.lower()}-32-20250302-2210",
        "play_class": play_class,
        "conditional_plays": {
            "OCO_triggers": [
                f"QQQ-{trade_type.lower()}-14-20250302-2210.json"
            ],
            "OTO_triggers": []
        },
        "strategy": "Option Swings",
        "creation_date": "2025-03-02",
        "creator": "auto-ingestor",
        "status": {
            "play_status": "CLOSED",
            "order_id": "efcd22e8-86dd-41a8-889f-2a0319d25fc8",
            "order_status": "pending_new",
            "position_exists": False,
            "last_checked": None,
            "closing_order_id": "b14d9ee5-9322-4f44-835c-4614e578c122",
            "closing_order_status": "pending_new",
            "contingency_order_id": None,
            "contingency_order_status": None,
            "conditionals_handled": True
        },
        "play_expiration_date": "03/05/2025",
        "stop_loss": {
            "premium_pct": 35.0,
            "SL_type": "LIMIT",
            "order_type": "limit at mid",
            "SL_option_prem": 5.7005
        },
        "take_profit": {
            "premium_pct": 65.0,
            "order_type": "limit at mid",
            "TP_option_prem": 14.4705
        },
        "logging": {
            "delta_atOpen": -0.3433,
            "theta_atOpen": -0.3418,
            "datetime_atOpen": "2025-03-03T13:12:21",
            "price_atOpen": 504.01,
            "premium_atOpen": 8.77,
            "datetime_atClose": "2025-03-04T10:07:34",
            "price_atClose": 490.94,
            "premium_atClose": 15.5,
            "close_type": "TP",
            "close_condition": "premium_pct"
        }
    }
    
    with open(path, 'w') as f:
        json.dump(template_play, f, indent=4)
    
    return path

def create_valid_play_file(path, trade_type="PUT"):
    """Create a valid play file for testing."""
    valid_play = {
        "symbol": "QQQ",
        "trade_type": trade_type,
        "entry_point": {
            "stock_price": 503.85,
            "order_type": "limit at bid",
            "entry_stock_price": 504.01,
            "entry_premium": 8.77
        },
        "strike_price": "499.0",
        "expiration_date": "03/21/2025",
        "contracts": 1,
        "option_contract_symbol": f"QQQ250321{trade_type[0]}00499000",
        "play_name": f"QQQ-{trade_type.lower()}-32-20250302-2210",
        "play_class": "SIMPLE",
        "logging": {
            "delta_atOpen": -0.3433,
            "theta_atOpen": -0.3418,
            "datetime_atOpen": "2025-03-03T13:12:21",
            "price_atOpen": 504.01,
            "premium_atOpen": 8.77,
            "datetime_atClose": "2025-03-04T10:07:34",
            "price_atClose": 490.94,
            "premium_atClose": 15.5
        }
    }
    
    with open(path, 'w') as f:
        json.dump(valid_play, f, indent=4)
    
    return path

def create_corrupted_play_file(path, corruption_type, trade_type="PUT"):
    """Create a corrupted play file with specified corruption pattern."""
    valid_play = {
        "symbol": "QQQ",
        "trade_type": trade_type,
        "entry_point": {
            "stock_price": 503.85,
            "order_type": "limit at bid",
            "entry_stock_price": 504.01,
            "entry_premium": 8.77
        },
        "strike_price": "499.0",
        "expiration_date": "03/21/2025",
        "contracts": 1,
        "option_contract_symbol": f"QQQ250321{trade_type[0]}00499000",
        "play_name": f"QQQ-{trade_type.lower()}-32-20250302-2210",
        "play_class": "SIMPLE",
        "logging": {
            "delta_atOpen": -0.3433,
            "theta_atOpen": -0.3418,
            "datetime_atOpen": "2025-03-03T13:12:21",
            "price_atOpen": 504.01,
            "premium_atOpen": 8.77,
            "datetime_atClose": "2025-03-04T10:07:34",
            "price_atClose": 490.94
        }
    }
    
    # Convert to JSON string for most cases
    json_str = json.dumps(valid_play, indent=4)
    
    if corruption_type == "cut_at_attribute":
        # Simulate a file cut off at premium_atClose attribute
        # Make sure the play has a premium_atClose field
        valid_play["logging"]["premium_atClose"] = 15.5
        
        # Convert to JSON string
        json_str = json.dumps(valid_play, indent=4)
        
        with open(path, 'w') as f:
            # Build up to but cut off at premium_atClose
            lines = json_str.split('\n')
            # Find the line with premium_atClose
            premium_line_idx = 0
            for i, line in enumerate(lines):
                if '"premium_atClose":' in line:
                    premium_line_idx = i
                    break
                    
            # Write up to the premium_atClose attribute name
            for i in range(premium_line_idx):
                f.write(lines[i] + '\n')
            
            # Write only the attribute name without a value
            f.write('        "premium_atClose": ')
    
    elif corruption_type == "missing_closing_braces":
        # Simulate a file with missing closing braces
        cut_at = json_str.rfind('}')
        cut_str = json_str[:cut_at]
        with open(path, 'w') as f:
            f.write(cut_str)
    
    elif corruption_type == "null_premium_close":
        # Simulate the specific issue with null premium_atClose
        valid_play["logging"]["premium_atClose"] = None
        with open(path, 'w') as f:
            # Just save it with extra closing braces
            json_content = json.dumps(valid_play, indent=4)
            # Add an extra brace to create corruption
            f.write(json_content[:-1] + "}}}")
    
    elif corruption_type == "missing_close_info":
        # Missing complete closing information
        if "premium_atClose" in valid_play["logging"]:
            del valid_play["logging"]["premium_atClose"]
        if "datetime_atClose" in valid_play["logging"]:
            del valid_play["logging"]["datetime_atClose"]
        if "price_atClose" in valid_play["logging"]:
            del valid_play["logging"]["price_atClose"]
        with open(path, 'w') as f:
            json.dump(valid_play, f, indent=4)
    
    elif corruption_type == "empty":
        # Create an empty file
        with open(path, 'w') as f:
            f.write("")
    
    return path

def test_json_fixer():
    """Test the PlayFileFixer utility with various corrupted files."""
    test_dir = create_test_environment()
    
    try:
        # Create template files in the closed directory (for reference)
        template_file1 = test_dir / 'plays/closed/template_put.json'
        create_template_play_file(template_file1, trade_type="PUT")
        
        template_file2 = test_dir / 'plays/closed/template_call.json'
        create_template_play_file(template_file2, trade_type="CALL")
        
        # Create a valid file
        valid_file = test_dir / 'plays/open/valid.json'
        create_valid_play_file(valid_file)
        
        # Create corrupted files with different patterns
        corrupted_file1 = test_dir / 'plays/open/cut_at_attribute.json'
        create_corrupted_play_file(corrupted_file1, "cut_at_attribute", trade_type="PUT")
        
        corrupted_file2 = test_dir / 'plays/pending-closing/missing_braces.json'
        create_corrupted_play_file(corrupted_file2, "missing_closing_braces", trade_type="PUT")
        
        corrupted_file3 = test_dir / 'plays/new/null_premium.json'
        create_corrupted_play_file(corrupted_file3, "null_premium_close", trade_type="PUT")
        
        corrupted_file4 = test_dir / 'plays/pending-closing/missing_close_info.json'
        create_corrupted_play_file(corrupted_file4, "missing_close_info", trade_type="CALL")
        
        # Create our fixer class with a modified base path for testing
        class TestPlayFileFixer(PlayFileFixer):
            def __init__(self, test_dir):
                super().__init__()
                self.base_dir = test_dir
        
        fixer = TestPlayFileFixer(test_dir)
        
        # Run the fixer
        fixed_count = fixer.check_and_fix_all_plays()
        
        # Check results
        logger.info(f"Fixer attempted to fix {fixed_count} files")
        
        # Test if corrupted files are now valid
        fixed_files = []
        
        for test_file in [corrupted_file1, corrupted_file2, corrupted_file3, corrupted_file4]:
            try:
                with open(test_file, 'r') as f:
                    json.load(f)
                logger.info(f"File {test_file.name} is now valid JSON")
                fixed_files.append(test_file.name)
            except json.JSONDecodeError:
                logger.error(f"File {test_file.name} is still corrupted")
        
        logger.info(f"Successfully fixed files: {', '.join(fixed_files)}")
        
        return fixed_count
    
    finally:
        # Clean up
        logger.info(f"Cleaning up test directory: {test_dir}")
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    print("Testing PlayFileFixer utility with template-based repair...")
    fixed_count = test_json_fixer()
    print(f"Test completed. Fixed {fixed_count} files.")
    
    print("\nRunning against actual play files in the system...")
    from goldflipper.utils.json_fixer import run_fixer
    actual_fixed = run_fixer()
    print(f"Fixed {actual_fixed} actual play files.") 