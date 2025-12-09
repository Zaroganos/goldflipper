# Migration Testing Checklist (Modern Stack)

> Scope: uv-based workflow, launcher-based Nuitka build, modern tooling. Legacy pip/setup.py paths intentionally excluded.

## Environment Verification

- [x] `uv sync` completes on a fresh clone (no cached venv present).  
  - 2025-11-29: `uv sync` + `uv sync --all-extras` both succeeded after removing cached venv.
- [x] `uv run python --version` reports an approved interpreter (3.11–3.13).  
  - Result: Python 3.11.12.
- [x] `uv run goldflipper --help` prints the CLI options without errors.
- [ ] `uv run goldflipper --mode console` reaches the TUI welcome screen.  
  - Pending manual check (Textual UI requires interactive session).

## Configuration & First-Run UX

- [ ] `uv run python -m goldflipper.first_run_setup` launches the wizard.
- [ ] Settings template is created automatically when missing.
- [ ] The launcher (`uv run goldflipper`) invokes the first-run wizard once and then opens the TUI on subsequent runs.
- [ ] Desktop shortcut creation succeeds when requested.

## Developer Tooling

- [ ] `uv run ruff format --check goldflipper tests` passes.  
  - 2025-11-29: Fails; 80 files would be reformatted (legacy formatting backlog).
- [ ] `uv run ruff check goldflipper tests` passes (or only known waivers).  
  - Fails with 3,841 issues (2,354 auto-fixable); backlog predates migration work.
- [ ] `uv run pyright goldflipper` passes.  
  - Fails with 431 errors; primarily due to untyped config/logging plumbing.
- [x] `uv run pytest` passes or reports only acknowledged flaky tests.  
  - 2025-11-29: `tests/test_market_data.py::test_market_data` passed (warning from `websockets` deprecation only).
  - 2025-12-08: Full multi-strategy test suite passes (41 tests total):
    * `test_orchestrator_unit.py`: 16 passed
    * `test_dry_run_mode.py`: 9 passed
    * `test_parallel_execution.py`: 4 passed
    * `test_strategy_evaluation.py`: 12 passed

## Runtime Functionality

- [ ] TUI buttons launch their respective helper scripts (spot-check critical ones: trading monitor, configuration editor, play ingestion).
- [ ] Watchdog toggles according to config and logs heartbeats.
- [ ] Monitor loop runs at least one full cycle without crashing.
- [ ] Logging output appears under the configured log directory.

## Packaging (Nuitka)

- [ ] `uv run python scripts/build_nuitka.py` completes.
- [ ] `dist/goldflipper.exe --help` runs on the build machine.
- [ ] Executable on a clean Windows VM launches the first-run wizard when settings are absent.
- [ ] After setup, the executable opens the TUI and accesses template/config files (no missing-file errors).
- [x] Included resources configured: `goldflipper/config`, `goldflipper/reference`, `goldflipper/tools/play-template.json`, `goldflipper.ico`.  
  - 2025-12-01: Build scripts updated with multi-strategy resources:
    * `goldflipper/tools/templates/` - Strategy-specific play templates (JSON)
    * `goldflipper/strategy/playbooks/` - Strategy playbooks (YAML configs)
  - **Deferred:** Actual build test pending (requires sufficient CPU/memory).

## Documentation & Scripts

- [ ] README quick-start commands (`uv sync`, `uv run goldflipper`, dev scripts) match actual behavior.
- [ ] `scripts/dev.bat` routes commands correctly (run/test/lint/format/check).
- [ ] `bootstrap.ps1` provisions uv, runs setup wizard, and launches the app.

## Observations / Notes

- `uv run goldflipper --mode console` and first-run wizard verification require an interactive terminal/GUI; leaving for manual validation.
- Ruff and Pyright failures reflect historical debt; documenting counts here rather than remediating immediately.

## Recent Updates

### 2025-12-08: Legacy Code Cleanup
- Removed `fallback_to_legacy` config option from orchestrator.py, system_status.py, settings_template.yaml
- Orchestration is now REQUIRED (no legacy fallback mode)
- All 41 multi-strategy tests pass after cleanup


