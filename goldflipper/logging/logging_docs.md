GOLDFLIPPER TRADING LOGGER DOCUMENTATION
=======================================

1. OVERVIEW
-----------
The Goldflipper Trading Logger is a comprehensive system for tracking, analyzing, and visualizing options trading plays. It consists of two main components:
- A core logging system (trade_logger.py)
- A user interface (trade_logger_ui.py)

2. SYSTEM ARCHITECTURE
---------------------

2.1 Core Logger (trade_logger.py)
    The PlayLogger class serves as the foundation for all logging operations.

    Key Components:
    - CSV-based persistent storage
    - Web dashboard using Dash
    - Excel/CSV export capabilities
    - Real-time trade tracking

2.2 User Interface (trade_logger_ui.py)
    Provides both a tkinter-based desktop interface and a web dashboard.
    
    Features:
    - Summary statistics display
    - Export functionality
    - Export history viewer with open CSV/Excel/directory actions
    - Save-to-Desktop option for exports
    - Enable Data Backfill toggle (fetch missing Greeks for closed plays)
    - Interactive data visualization
    - Real-time updates

3. DATA STRUCTURE
----------------

3.1 Play Data Format
    The logger tracks plays based on the template structure defined in play-template.json.
    Key fields logged:
    - Basic trade information (symbol, type, strike, expiration)
    - Entry/exit points
    - Greeks
    - P/L calculations
    - Status tracking

3.2 Logged Metrics
    a) Basic Trade Information
       - Symbol
       - Trade Type (CALL/PUT)
       - Strike Price
       - Expiration Date
       - Contract Count

    b) Performance Metrics
       - Entry Price/Premium
       - Exit Price/Premium
       - P/L
       - Greeks at Open (Delta, Theta)

    c) Timing Data
       - Entry Time
       - Exit Time
       - Hold Duration

4. USAGE GUIDE
-------------

4.1 Basic Logging
    Example:
    from goldflipper.logging.trade_logger import PlayLogger
    logger = PlayLogger()
    logger.log_play(play_data)

4.2 Accessing the Interface
    - Via TUI: Click "Trade Logger" button
    - Direct Launch: Run trade_logger_ui.py

4.3 Exporting Data
    - CSV: logger.export_to_spreadsheet(format='csv')
    - Excel: logger.export_to_spreadsheet(format='excel')

4.4 Data Backfill Behavior
    - Backfill targets missing Greeks at open (delta/theta) for CLOSED plays only.
    - Requirements for backfill: the play must include option_contract_symbol and logging.datetime_atOpen.
    - EXPIRED plays never opened and are included in logs without backfill.
    - When enabled in the UI, backfill calls the configured market data provider (MarketDataApp) for historical option quotes on the opening date.

5. EXTENSION POINTS
-----------------

5.1 Adding New Metrics
    1. Update _create_empty_log() columns
    2. Modify log_play() to include new data
    3. Update visualization methods as needed

5.2 Custom Visualizations
    Create new visualization methods in PlayLogger class:
    def create_custom_chart(self):
        """Add custom visualization logic"""
        pass

5.3 Additional Export Formats
    Extend export_to_spreadsheet() with new formats:
    elif format == 'new_format':
        # Implement new export logic
        return export_path

6. DATABASE SCHEMA
----------------
Current CSV columns:
- play_name (str)
- symbol (str)
- trade_type (str)
- strike_price (float)
- expiration_date (str)
- contracts (int)
- date_atOpen (str, yyyy-mm-dd)
- time_atOpen (str, HH:MM:SS)
- date_atClose (str, yyyy-mm-dd)
- time_atClose (str, HH:MM:SS)
- price_atOpen (float)
- price_atClose (float)
- premium_atOpen (float)
- premium_atClose (float)
- delta_atOpen (float)
- theta_atOpen (float)
- close_type (str)
- close_condition (str)
- profit_loss_pct (float)
- profit_loss (float)
- status (str)

7. WEB DASHBOARD
--------------
Features:
1. Summary Statistics
   - Total trades
   - Win rate
   - P/L metrics
   - Performance trends

2. Trade History Chart
   - P/L visualization
   - Entry/exit points
   - Performance trends

3. Detailed Trade Log
   - Sortable columns
   - Filtering capabilities
   - Export options

Access: http://localhost:8050 when running

8. BEST PRACTICES
---------------

8.1 Data Consistency
    - Always use log_play() for logging
    - Don't modify CSV directly
    - Use provided export methods
    - Validate data before logging

8.2 Error Handling
    - Implement try-except blocks
    - Validate data before logging
    - Check file permissions
    - Log errors appropriately

8.3 Performance
    - Use batch operations for multiple logs
    - Consider data archiving for large datasets
    - Implement data cleanup routines
    - Monitor file sizes

9. FUTURE ENHANCEMENTS
--------------------

9.1 Planned Features
    - Google Sheets integration
    - Advanced analytics dashboard
    - Real-time notifications
    - Performance reporting
    - Machine learning insights
    - Portfolio analytics

9.2 Integration Points
    - API endpoints for external tools
    - Database migration options
    - Custom metric plugins
    - Third-party analytics integration

10. TROUBLESHOOTING
-----------------

10.1 Common Issues
     - File permission errors
       Solution: Check directory permissions
     
     - Data format inconsistencies
       Solution: Validate JSON structure
     
     - Dashboard connection issues
       Solution: Verify port availability

10.2 Debug Tools
     - Check log files
     - Verify CSV structure
     - Monitor system resources
     - Use provided test functions

11. CONTRIBUTING
--------------
To extend the logger:
1. Fork the repository
2. Create feature branch
3. Follow coding standards
4. Submit pull request

Guidelines:
- Follow PEP 8 style guide
- Include documentation
- Add unit tests
- Update DOCUMENTATION.md

12. SUPPORT
----------
For issues or enhancements:
1. Check existing documentation
2. Review error logs
3. Submit detailed bug reports

Include in bug reports:
- System configuration
- Error messages
- Steps to reproduce
- Expected vs actual behavior

13. DEPENDENCIES
--------------
Required packages:
- pandas
- plotly
- dash
- tkinter
- numpy
- datetime

14. FILE STRUCTURE
----------------
goldflipper/logging/
├── data_backfill_helper.py # Backfills missing cells where possible
├── trade_logger.py       # Core logging functionality
├── trade_logger_ui.py    # User interface
├── DOCUMENTATION.md      # This file
└── __init__.py          # Package initialization

15. VERSION HISTORY
-----------------
v1.0.0 - Initial release
- Basic logging functionality
- CSV/Excel export
- Web dashboard
- TUI integration

16. SECURITY CONSIDERATIONS
------------------------
- Data encryption (planned)
- Access control
- Backup procedures
- Data validation

17. PERFORMANCE METRICS
--------------------
Logging system monitors:
- Trade execution time
- System response time
- Data processing speed
- Storage efficiency

18. BACKUP AND RECOVERY
---------------------
- Automatic backups
- Data recovery procedures
- Version control
- Archive management

19. CODING STANDARDS
------------------
Follow:
- PEP 8
- Type hints
- Docstrings
- Comments for complex logic

20. TESTING
----------
Areas covered:
- Unit tests
- Integration tests
- Performance tests
- UI/UX testing

END OF DOCUMENTATION 