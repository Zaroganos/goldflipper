# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\test_migration.ps1
# (Run from the repo root; requires uv on PATH.)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "=== Goldflipper Modern Migration Tests ===" -ForegroundColor Cyan
Write-Host "Command: powershell -ExecutionPolicy Bypass -File scripts\\test_migration.ps1"
Write-Host ""

$ErrorCount = 0

function Invoke-Step {
    param(
        [string]$Description,
        [scriptblock]$Action,
        [switch]$WarnOnly
    )

    Write-Host $Description -ForegroundColor Yellow
    try {
        & $Action
        Write-Host "✓ Success`n" -ForegroundColor Green
    } catch {
        if ($WarnOnly) {
            Write-Host "⚠ Warning: $($_.Exception.Message)`n" -ForegroundColor Yellow
        } else {
            Write-Host "✗ Failed: $($_.Exception.Message)`n" -ForegroundColor Red
            $script:ErrorCount++
        }
    }
}

Invoke-Step "Step 1: Checking uv installation..." {
    if (-not (Get-Command uv -ErrorAction Stop)) {
        throw "uv not found in PATH"
    }
}

Invoke-Step "Step 2: Syncing dependencies (uv sync)..." {
    uv sync | Out-String | Write-Verbose
}

Invoke-Step "Step 3: Verifying Python version..." {
    $version = uv run python --version
    Write-Host "Interpreter: $version"
}

Invoke-Step "Step 4: Checking CLI availability (uv run goldflipper --help)..." {
    uv run goldflipper --help | Out-Null
}

Invoke-Step "Step 5: Running tests (uv run pytest)..." {
    uv run pytest --tb=short
}

Invoke-Step "Step 6: Ruff lint (warnings only)..." {
    uv run ruff check goldflipper tests
} -WarnOnly

Invoke-Step "Step 7: Ruff format check (warnings only)..." {
    uv run ruff format --check goldflipper tests
} -WarnOnly

Write-Host "=== Summary ===" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "All critical checks passed. Re-run anytime with:" -ForegroundColor Green
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\\test_migration.ps1"
    exit 0
} else {
    Write-Host "$ErrorCount critical failure(s) detected." -ForegroundColor Red
    exit 1
}

