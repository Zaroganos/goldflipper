# Goldflipper UI Migration Notes

## Dependencies Management
- [x] Migrate to uv for dependency and environment management:
  - Converted `pyproject.toml` to PEP 621 `[project]`
  - Added `[dependency-groups]` for development dependencies
  - Updated launch scripts to use `uv sync` and `uv run`
  - uv lockfile (`uv.lock`) ensures reproducible installs

- [ ] Dependency cleanup checklist:
  - [x] Removed `requirements.txt` (Poetry-only)
  - [x] Removed `setup.py` (deprecated)
  - [ ] Remove any remaining TUI (`textual`) dependencies
  - [x] Streamlit present in Poetry dependencies
  - [ ] Review version constraints for shared dependencies

## IDE Configuration
- [x] Set up VS Code for uv environments:
  - Recommend selecting the `.venv` created by `uv sync` as the interpreter
  - Configured Python analysis settings
  - Set up package indexing for goldflipper
  - Added workspace folder to Python path
  - Enabled type checking and auto-imports

## File Structure Changes
- [ ] Remove old UI files:
  - `goldflipper_tui.py`
  - `goldflipper_tui_NEW.py`
  - `first_run_setup.py` (replace with Streamlit-based setup)
  - Any other UI-specific files

- [ ] Update import paths in core files:
  - Update any imports referencing old UI components
  - Ensure all core functionality is properly exposed to web interface

## Configuration Changes
- [ ] Update `settings.yaml`:
  - Add web-specific settings (port, host, etc.)
  - Remove any TUI-specific settings
  - Add new UI preferences

## Launch Scripts
- [x] Update launch scripts for uv:
  - Modified `install_service.bat` to use uv
  - Updated `launch_web.py` to use uv environment
  - Added uv installation checks
  - Improved error handling and logging

- [ ] Update `launch_goldflipper.bat`:
  - Replace TUI launch with web interface launch
  - Add proper error handling
  - Add web browser auto-launch

- [ ] Create Linux launch script:
  - Create `launch_goldflipper.sh`
  - Add proper permissions handling
  - Add web browser auto-launch

## Service Integration
- [ ] Update Windows service:
  - Modify service to launch web interface instead of TUI
  - Update service dependencies
  - Add web server status monitoring

- [ ] Update Linux systemd service:
  - Create/modify service file
  - Add web server configuration
  - Add proper logging

## Packaging Changes
- [ ] Update PyInstaller spec:
  - Remove TUI-specific files
  - Add web interface files
  - Update data files list
  - Add web server dependencies

- [ ] Consider alternative packaging:
  - Evaluate py2exe vs PyInstaller
  - Consider Docker containerization
  - Plan for cross-platform distribution

## DuckDB with PyInstaller

- The packaged app runs from a read-only temp directory. Do not store the DuckDB database inside the bundle.
- Set `GOLDFLIPPER_DATA_DIR` to a writable location (for example `%LOCALAPPDATA%\\Goldflipper` on Windows, `~/Library/Application Support/Goldflipper` on macOS, or `$XDG_DATA_HOME/goldflipper`/`~/.local/share/goldflipper` on Linux).
- The code in `goldflipper/database/connection.py` respects `GOLDFLIPPER_DATA_DIR` and will create `db/goldflipper.db`, `db/backups`, and `db/temp` under that base directory.
- Ensure launch scripts (e.g., `.env.bat`, `launch_goldflipper.bat`) export `GOLDFLIPPER_DATA_DIR` before starting the app.
- Build from the project environment, e.g. `uv run pyinstaller your.spec`.
- Do not add the DuckDB database file with `--add-data`; it should live outside the bundled app and be writable at runtime.

## Testing Requirements
- [ ] Update test suite:
  - Add web interface tests
  - Add integration tests
  - Add performance tests
  - Add browser compatibility tests

## Documentation Updates
- [ ] Update user documentation:
  - Add web interface guide
  - Update installation instructions
  - Add troubleshooting guide
  - Update service management docs

## Deployment Strategy
- [ ] Plan deployment phases:
  1. Parallel deployment (both UIs)
  2. Gradual user transition
  3. Monitoring period
  4. Complete switchover

## Backup & Recovery
- [ ] Update backup procedures:
  - Add web interface state backup
  - Add session data backup
  - Update recovery procedures

## Security Considerations
- [ ] Add web security measures:
  - Add authentication
  - Add HTTPS support
  - Add rate limiting
  - Add input validation

## Performance Optimization
- [ ] Optimize web interface:
  - Add caching
  - Optimize data loading
  - Add lazy loading
  - Implement WebSocket for real-time updates

## Monitoring & Logging
- [ ] Update logging system:
  - Add web interface logs
  - Add access logs
  - Add performance metrics
  - Add error tracking

## Future Considerations
- [ ] Plan for future improvements:
  - Mobile responsiveness
  - Progressive Web App features
  - Offline capabilities
  - API development

## Lessons Learned
1. uv Integration:
   - uv provides fast dependency resolution and installation
   - Project environments are synced from `uv.lock` for reproducibility
   - Simple commands: `uv sync`, `uv run` replace multiple toolchains

2. IDE Configuration:
   - VS Code needs explicit configuration for Poetry environments
   - Package indexing depth needs to be set appropriately
   - Workspace folder needs to be added to Python path
   - Type checking and auto-imports improve development experience

3. Migration Strategy:
   - Keep old dependency files as backup during transition
   - Update scripts to use uv
   - Test each component after migration
   - Document all changes for team reference

4. Next Steps:
   - Complete removal of old UI files
   - Update import paths in core files
   - Migrate remaining scripts to Poetry
   - Update documentation for new setup

## Database UI Implementation
- [ ] Create Database Management Page:
  1. Overview Section:
     - Database statistics dashboard
     - Table structure visualization
     - System health indicators
     - Quick action buttons

  2. Data Browser:
     - Table selection interface
     - Advanced filtering
     - Data export capabilities
     - Bulk operations interface

  3. Monitoring Dashboard:
     - Real-time performance metrics
     - Query analysis tools
     - Resource utilization graphs
     - Alert configuration

  4. Administration Tools:
     - Backup management interface
     - User access control
     - Maintenance operations
     - Configuration management

- [ ] Integration with Core System:
  1. Database Connection:
     - Connection pool management
     - Error handling
     - Transaction management
     - Query optimization

  2. Data Access Layer:
     - Repository pattern implementation
     - Query builders
     - Data validation
     - Caching strategy

  3. Security Features:
     - Access control
     - Audit logging
     - Data encryption
     - Backup protection

  4. Performance Optimization:
     - Query optimization
     - Index management
     - Cache configuration
     - Connection pooling 