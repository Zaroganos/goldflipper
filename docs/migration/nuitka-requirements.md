# Nuitka Build Requirements

## Entry Point
- Main module: `src/goldflipper/run.py`
- Entry function: `main()`
- CLI script: `goldflipper = goldflipper.run:main` (from `pyproject.toml`)

## Data Files to Include
- `goldflipper/config/settings_template.yaml`
- `goldflipper/reference/*.csv`
- `goldflipper/tools/play-template.json`
- Any additional package data discovered in `docs/migration/package-data-mapping.md`
- Batch/PowerShell helpers (`*.bat`, `*.ps1`) when distributing automation scripts

## Windows-Specific Dependencies
- `pywin32` for Windows service wrapper support
- `tkinterdnd2` for drag-and-drop UI workflows
- Any service-related modules under `src/goldflipper/service/`

## Plugin Requirements
- `matplotlib` triggers toolkit detection; enable `--enable-plugin=tk-inter`
- Ensure tkinter is available in the runtime environment before building
- Modern Nuitka automatically handles `pywin32`, so no plugin flag is required

## Hidden Imports / Special Handling
- Watch for dynamic imports in Textual/Rich components
- Verify trading adapters (e.g., Alpaca client) are detected
- Consider `--follow-imports` and `--prefer-source-code` flags
- Re-run with `--show-modules` if runtime ImportError appears

## Outstanding Checks
- [ ] Confirm final list of config/templates that must be embedded
- [ ] Verify `install_service.bat` / other scripts ship with the build
- [ ] Validate the executable on a clean Windows machine
- [ ] Re-run Nuitka build on a higher-power PC (current attempt cancelled)


