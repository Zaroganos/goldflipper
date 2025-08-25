This is a list of tasks to do and features to implement for the goldflipper project.
Directions for AI: Place new tasks on top. Remember to use real current date when adding a to do or addressing it. Use a tool or MCP if you are unsure what the current date is.

### 2025-08-12
- [x] Migrated dependency management to uv
  - Converted `pyproject.toml` to PEP 621 `[project]` with `[dependency-groups]`
  - Switched build backend to Hatch (`hatchling`) and configured wheel packages
  - Replaced Poetry/pip usage in scripts with `uv sync` / `uv run`; added uv auto-install checks
  - Generated and committed `uv.lock` for reproducible installs
- [x] Updated documentation and messages to uv
  - `README.md`: Added “Migrating from Goldflipper Classic” with `uv run goldflipper-migrate`
  - `docs/developer_guide.md`, `web/MIGRATION_NOTES.md`: updated to uv
  - Replaced pip install tips with `uv pip install ...` in helper scripts/messages
- [x] Version resolution improvements
  - `database/connection.py`: read version from `[project].version` (fallback to Poetry), support normalized dist names
- [x] Validated environment
  - Ran `uv lock` and `uv sync`; basic import smoke test succeeded
- [ ] CI/CD (GitHub Actions) with uv
  - Research `astral-sh/setup-uv@v6`, caching, `uv sync --locked`, `uv run pytest`, lint/type checks, secrets
- [ ] Optional follow-ups
  - Review and clean any remaining Poetry references in historical notes
  - Consider adding explicit uv check to any other runner scripts if needed

### 2025-08-11
- [ ] Add a way to address log size. How to implement functional rotating log files? How to archive old ones?
 - [x] VIX WEM stabilization:
   - Implemented provider-guided Wednesday expiration selection with rule-based algorithm fallback
   - Robust ATM selection for VIX via min |call_mid − put_mid|
   - Denominator (Friday Close) priority: VX=F via yfinance → ^VIX via yfinance → direct Yahoo Chart API → parity proxy (last resort)
   - Added base source notes to Excel export; added “Clear WEM Cache” maintenance action
   - Deprecated vix_utils pricing; removed manager dependency on vix_utils for futures price

### 2025-08-10 Wrap-up (Delta-16 + Settings + VIX)

- **Delta-16 accuracy hardening (in progress)**: WEM now chooses the actual expiration date from provider listings (when available) before chain fetch. Remaining task: extract and enhance `validate_delta_16_quality()` into its own module with stronger checks (absolute-delta closeness per side, sign normalization, bounds/monotonicity, optional cross‑provider checks, theoretical‑delta fallback).
- **Strict DB-only settings migration**:
  - All market data configuration is now loaded from DuckDB `user_settings` only. No YAML fallbacks.
  - Settings UI (`web/pages/4_⚙️_Settings.py`) reads/writes keys under `market_data_providers.*` using DELETE→INSERT upserts with JSON-encoded values.
  - Fixed duplicate Streamlit element IDs; improved error messaging to list failing keys.
- **Unified database pathing**:
  - Default DB base dir now uses OS-standard path (Windows: `%LOCALAPPDATA%\\Goldflipper`; macOS: `~/Library/Application Support/Goldflipper`; Linux: `$XDG_DATA_HOME/goldflipper` or `~/.local/share/goldflipper`). Can be overridden via `GOLDFLIPPER_DATA_DIR` and `.env.bat`.
  - Added runtime support to change base dir (code supports `set_data_dir()`), pending UI.
- **MarketData.app integration**:
  - Implemented `get_option_chain` with explicit `side=call|put` and `expiration` per docs/Postman; `get_available_expirations` added.
  - `get_historical_data` handles index symbols (e.g., VIX) via `/indices/candles` first.
- **WEM fixes**:
  - Corrected metadata bug by using a single `calendar_next_friday` reference to avoid `UnboundLocalError` on `next_friday`.
  - Logging refined: if essential fields are missing, logs reflect partial/unsuccessful updates rather than success.
  - Excel export: highlight Delta-16 flagged cells in vertical layout when validation warns/errors.
- **VIX now works**:
  - Verified chain/historical retrieval via MarketData.app with correct endpoints and symbol handling.

Key paths/files:
- `goldflipper/web/pages/6_📊_WEM.py`: provider‑guided expiration, chain usage, Delta‑16 plumbing, metadata fix (`calendar_next_friday`).
- `goldflipper/web/pages/4_⚙️_Settings.py`: DB‑only settings UI, unique checkbox keys, robust upsert.
- `goldflipper/goldflipper/data/market/manager.py`: DB‑only config load; `get_available_expirations` entrypoint.
- `goldflipper/goldflipper/data/market/providers/marketdataapp_provider.py`: expirations, chain with side, indices candles.
- `.env.bat`, `web/launch_web.bat`, `launch_goldflipper.bat`: centralized env sourcing.

Open next steps:
- Extract and enhance Delta‑16 validation module; wire highlighting for horizontal layout.
- Add DB UI to change DB base directory (writes `.env.bat`, calls `set_data_dir()`).
- Implement expirations for Alpaca; bring yfinance chain as fallback; ensure symbol mapping coverage.


- [x] Fix WEM display and validation issues (2025-06-23):
      1. [x] Fixed WEM price source bug - mystery $305.95 vs correct Friday close $308.38
         - Root cause: WEM was making live API calls instead of using Friday close cache
         - Fixed: Ensured WEM ALWAYS uses previous Friday close price (never live API)
         - Fixed: Removed orphaned market_data.source reference causing errors
      2. [x] Improved number formatting in WEM table display
         - Added max_digits parameter (default 5) to limit display width
         - Always show minimum 2 decimal places for consistency
         - Use scientific notation for numbers exceeding max_digits
         - Added both sig_figs and max_digits controls in sidebar
      3. [x] Fixed Delta 16+/- validation system timing issue
         - Root cause: Validation config created AFTER Update WEM Data button
         - Fixed: Moved validation controls to top of sidebar (before button)
         - Added debug logging to track validation config usage
         - Validation now properly enables/disables based on user settings
      4. [x] Enhanced Friday close data source documentation
         - Confirmed proper data flow: cache → MarketDataApp historical API → fallback
         - Validated weekly caching strategy and cleanup procedures

- [x] Fix WEM Delta 16+/- calculation method (2025-01-14):
      1. [x] Identified incorrect method using arbitrary adjacent strikes as "Delta 16" values
      2. [x] Implemented proper delta-based lookup from deltas.py logic
      3. [x] Added calculate_delta_16_values() function for direct option chain lookup
      4. [x] Updated WEM calculation to find options with actual delta ≈ ±0.16
      5. [x] Removed invalid fallback logic that provided incorrect values
      6. [x] Added proper error handling when delta values unavailable (sets to None)
      7. [x] Added TODO placeholder for Black-Scholes Method 2 fallback implementation
      8. [x] Updated documentation to clarify WEM is primary, Delta 16 is secondary analysis
      9. [x] Enhanced logging to show actual delta values and calculation accuracy
      
      BEFORE: Delta 16+ = adjacent_strike_above_ATM (incorrect)
      AFTER: Delta 16+ = actual_option_with_0.16_delta.strike (correct)

- [ ] Fix WEM Streamlit deprecation warnings and data conversion issues:
      1. [ ] Fix FutureWarning: pandas read_json literal string deprecated (line 693)
         - Replace literal JSON string with StringIO object wrapper
      2. [ ] Fix DeprecationWarning: datetime.utcnow() deprecated (line 543)
         - Replace with datetime.now(datetime.UTC) for timezone-aware timestamps
      3. [ ] Fix pyarrow conversion error with percentage strings (SPY column)
         - Handle percentage string format in dataframe before pyarrow conversion
         - Consider keeping percentage values as numeric and formatting on display

- [x] Fix WEM calculation to use real market data:
      1. [x] Replace simulated random data with actual options market data
      2. [x] Implement proper ATM straddle calculation using real mid prices
      3. [x] Add OTM strangle calculation with 16-delta options
      4. [x] Calculate proper WEM values based on real market pricing
      5. [x] Add comprehensive logging and error handling

- [x] Fix WEM Streamlit module:
      1. [x] Fix WEM calculation and display in both vertical and horizontal layouts
      2. [x] Implement proper database integration with computed WEM values
      3. [x] Improve UI with better filtering and metric selection
      4. [x] Add data export functionality for CSV and Excel formats
      5. [x] Enhance error handling and logging throughout

- [x] Implement settings management in Streamlit UI:
      1. [x] Create Settings page in Streamlit UI
      2. [x] Add YAML file loading and parsing
      3. [x] Implement settings display and editing interface
      4. [x] Add save functionality for settings changes
      5. [ ] Complete database integration for settings storage
      6. [ ] Implement settings schema validation

- [~] Implement DuckDB integration for settings:
      1. [x] Create database migration for settings schema
      2. [x] Add settings_schema and user_settings tables
      3. [x] Implement SettingsManager class for DB interaction
      4. [x] Add YAML import/export functionality
      5. [ ] Fix remaining DuckDB compatibility issues
      6. [ ] Complete transaction handling and error recovery

- [ ] Implement uv + PyInstaller packaging workflow:
      1. [x] Convert pyproject to PEP 621 and uv groups
      2. [x] Update scripts to use `uv sync` and `uv run`
      3. [ ] Update PyInstaller spec for uv environment
      4. [ ] Test packaging with uv-managed dependencies
      5. [ ] Create uv-based deployment scripts

- [ ] CI/CD with uv (GitHub Actions):
      1. [ ] Research best practices for `astral-sh/setup-uv@v6` and caching strategy
      2. [ ] Add workflow steps: checkout → setup-uv → `uv sync --locked --dev` → `uv run pytest`
      3. [ ] Consider linting/type checks (`uv run ruff`, `uv run mypy`) and artifact uploads
      4. [ ] Ensure secrets handling for any integration tests (e.g., Alpaca sandbox)

- [ ] Clean up old dependency management:
      1. [x] Remove requirements.txt (now managed by uv)
      2. [x] Update documentation for uv usage
      3. [x] Test all scripts with uv environment

- [ ] Fix IDE import resolution:
      1. [ ] Update remaining import paths
      2. [ ] Fix circular dependencies
      3. [ ] Add type hints to improve IDE support
      4. [ ] Update package structure if needed

- [ ] Implement threading
- [ ] Implement locking

- [ ] Migrate UI to Streamlit for better performance and maintainability:
      1. [x] Set up Streamlit project structure:
         - [x] Create web/ directory with app.py and pages/
         - [x] Set up components/ directory for reusable UI elements
         - [x] Configure proper imports and dependencies
          - [x] Ensure Streamlit and dependencies are managed via uv
      
      2. [ ] Implement core dashboard:
         - [ ] Create main dashboard layout
         - [ ] Add account selection and status indicators
         - [ ] Implement quick action buttons
         - [ ] Add real-time status updates
         - [ ] Integrate with existing core functionality
      
      3. [ ] Migrate individual features:
         - [ ] Play creation and management
         - [ ] Trade logging and analysis
         - [ ] Market data visualization
         - [x] Configuration management
         - [x] Weekly Expected Moves (WEM) analysis
         - [ ] Chart viewing
      
      4. [ ] Testing and validation:
         - [ ] Add unit tests for new components
         - [ ] Implement integration tests
         - [ ] Perform performance testing
         - [ ] Conduct user acceptance testing
      
      5. [ ] Deployment and transition:
         - [ ] Create deployment scripts
         - [ ] Add documentation for new UI
         - [ ] Plan user transition strategy
         - [ ] Keep old UI as fallback during transition

- [?] Fix the problem with plays whose limit order is not filled and expires at the end of the day:
      1. [x] Implement atomic file operations for all play file writes
      2. [x] Add file backups before critical operations
      3. [x] Add validation checks before saving play data
      4. [x] Add integrity verification for play files
      5. [x] Implement proper error handling and recovery for corrupted files
      - Additional improvements:
        - Updated directory paths
        - Removed unnecessary order cancellation for GTD orders
        - Enhanced logging and error reporting

- [ ] Implement a packaging and installation system for the program:
      1. Create spec file for PyInstaller with all dependencies
      2. Add data files to spec (config files, templates, etc.)
      3. Set up proper file paths for packaged version
      4. Create separate builds for Windows and Linux
      5. Add version checking and auto-update capability
      6. Create installation scripts for each platform
      7. Set up proper logging paths for installed version
      8. Integrate PyInstaller packaging to create standalone executables and test on target platforms

- [ ] Implement service functionality and resilience features:
      1. Set up Windows Service / Linux Systemd service:
         - Create service configuration files
         - Implement proper service lifecycle hooks (start, stop, pause, resume)
         - Configure service dependencies (network, filesystem)
         - Set up appropriate user permissions and security context
      
      2. Add automatic restart capabilities:
         - Implement watchdog functionality to monitor program health
         - Set up crash detection and reporting
         - Configure automatic restart on failure
         - Add exponential backoff for restart attempts
      
      3. Implement state recovery mechanisms:
         - Add periodic state snapshots
         - Implement transaction logging
         - Create state recovery procedures
         - Add consistency checks for recovered state
      
      4. Add system integration features:
         - Configure startup with operating system
         - Set up proper logging to system log (Windows Event Log / syslog)
         - Implement health monitoring endpoints
         - Add administrative control interface
      
      5. Implement graceful shutdown handling:
         - Add proper cleanup procedures
         - Implement state preservation
         - Handle in-progress operations
         - Add shutdown notification system

      6. Create monitoring and alerting system:
         - Set up health metrics collection
         - Implement alert triggers for critical conditions
         - Add remote monitoring capability
         - Create status dashboard

-- Service Management Enhancements --

- Added a "Manage Service" button to the Goldflipper TUI (goldflipper_tui.py).
  - This button now presents a confirmation dialog with centered text.
  - The dialog clearly warns that administrative privileges are required and that changes (install/uninstall) will not take effect until a system reboot.

- For service installation:
  - The elevated process installs the service and automatically starts it (via a PowerShell command that executes "python -m goldflipper.run --mode install" followed by "net start GoldflipperService").

- For service uninstallation:
  - The elevated process stops the running service before uninstalling it (via a PowerShell command that executes "net stop GoldflipperService" followed by "python -m goldflipper.run --mode remove").

- These changes improve user clarity and ensure that service state actions are performed safely and with the proper permissions.

- [x] Add limit orders at the 'last' price to the execution flow and play creation:
      1. [x] Add price reference choice (bid/last) to play creation tool
      2. [x] Update play data structure to store price reference
      3. [x] Modify order execution logic to use selected price
      4. [x] Add price reference validation in core functions
      5. [x] Update logging to show price reference used
      6. [x] Maintain backward compatibility for existing plays


- [~] Implementation of DuckDB database and migration to usage from current workflow      
-- Core Tables (Initial Implementation)
1. [ ] Plays table
2. [ ] Play Status History table
3. [ ] Trade Logs table

-- Extended Database Implementation
1. [ ] Trading Strategy Management:
   - Create trading_strategies table
   - Implement strategy versioning
   - Add strategy validation
   - Migrate existing strategy files

2. [ ] Service State Management:
   - Create service_backups table
   - Implement backup rotation
   - Add state validation
   - Migrate existing state files

3. [ ] Enhanced Logging System:
   - Create log_entries table
   - Implement structured logging
   - Add trace ID system
   - Migrate existing logs

4. [~] Configuration Management:
   - [x] Create settings_schema table
   - [x] Create user_settings table
   - [x] Implement YAML-to-DB migration
   - [ ] Add schema validation
   - [ ] Implement complete DB-to-YAML sync
   - [ ] Fix DuckDB compatibility issues

5. [ ] System Monitoring:
   - Create watchdog_events table
   - Implement event tracking
   - Add resolution system
   - Set up monitoring dashboards

6. [ ] Chart Management:
   - Create chart_configurations table
   - Implement user preferences
   - Add indicator management
   - Migrate existing chart settings

7. [ ] Tool State Management:
   - Create tool_states table
   - Implement state persistence
   - Add configuration management
   - Migrate existing tool states

-- Database UI Implementation (Streamlit)
1. [ ] Create Database Overview Page:
   - Add table structure visualization
   - Implement data browsers
   - Add query interface
   - Create monitoring dashboard

2. [ ] Add Data Management Features:
   - Implement backup interface
   - Add data export tools
   - Create migration utilities
   - Add validation tools

3. [ ] Create Monitoring Interface:
   - Add performance metrics
   - Implement query analysis
   - Create health dashboard
   - Add alert configuration

4. [~] Implement Administration Tools:
   - [ ] Add user management
   - [ ] Create backup interface 
   - [ ] Implement maintenance tools
   - [x] Add settings configuration editor

