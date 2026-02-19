# Package Data Migration

## Source: `setup.py` `package_data`
```python
package_data = {
    "goldflipper": [
        "tools/play-template.json",
        "config/*.py",
        "config/settings_template.yaml",
    ],
}
```

## Source: `MANIFEST.in`
- `goldflipper/tools/play-template.json`
- `goldflipper/config/settings_template.yaml`
- `recursive-include goldflipper/config *.py`
- `recursive-include goldflipper/reference *.csv`
- Windows helper files (`*.bat`, `*.ps1`, `*.ico`)

## Target: `pyproject.toml`
```toml
[tool.hatch.build.targets.wheel.force-include]
"goldflipper/tools/play-template.json" = "goldflipper/tools/play-template.json"
"goldflipper/config/settings_template.yaml" = "goldflipper/config/settings_template.yaml"
"goldflipper/reference" = "goldflipper/reference"
```

## Notes & Verification
- `goldflipper/config/*.py` files are Python modules and ship automatically; no extra include required.
- CSV data under `goldflipper/reference` is bundled wholesale to preserve templates.
- Windows batch/PowerShell scripts reside at repository root and do not require special handling because `include-package-data = true` and MANIFEST rules remain in place for legacy builds.
- **To verify after build:**
  1. `uv build` (future) or `python -m build` once enabled.
  2. Inspect the generated wheel contents to confirm templates and CSV files exist.
  3. Install the wheel into a clean environment and run workflows that read the template files.
