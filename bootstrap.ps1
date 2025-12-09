#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallPath = (Join-Path $env:USERPROFILE 'goldflipper'),
    [string]$Branch = 'multistrat',
    [switch]$NoLaunch
)

<#
TODO: Update the BRANCH to MAIN once the code is rebased. CRITICAL
And also:
Address the following concerns in Update-Repository function:

1. Non-git directory handling:
   - Currently, if the directory exists but is NOT a git repo, the script only prints a warning
     and continues execution. This can cause issues because:
     - Initialize-Venv may run on the wrong location
     - Initialize-Settings may create/overwrite files incorrectly
     - Start-App may launch from the wrong location
   - Should either: fail with clear error, or handle this case explicitly

2. Uncommitted changes:
   - git pull --ff-only will fail if there are uncommitted changes
   - Should handle: stash changes, warn user, or provide option to abort

3. Branch divergence:
   - git pull --ff-only will fail if local branch has diverged from remote
   - Should handle: merge, rebase, or warn user about divergence

4. Remote URL verification:
   - If directory exists and is a git repo but points to different remote URL,
     git fetch may fail or fetch from wrong repository
   - Should verify remote URL matches expected repository before updating

5. Error handling:
   - git operations may fail silently or with unclear errors
   - Should add proper error checking and user-friendly error messages
#>

function Write-Section {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Test-Admin {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-CommandExists {
    param([Parameter(Mandatory)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-WinGet {
    if (Test-CommandExists -Name 'winget') { return $true }
    Write-Host 'winget not found. On some Windows editions it may be missing. Falling back to Chocolatey if available.' -ForegroundColor Yellow
    return $false
}

function Install-Chocolatey {
    if (Test-CommandExists -Name 'choco') { return $true }
    if (-not (Test-Admin)) {
        Write-Host 'Chocolatey not found and admin rights not detected. Skipping Chocolatey install.' -ForegroundColor Yellow
        return $false
    }
    Write-Section 'Installing Chocolatey (requires admin privileges)'
    Set-ExecutionPolicy Bypass -Scope Process -Force | Out-Null
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    try {
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        return (Test-CommandExists -Name 'choco')
    }
    catch {
        Write-Host "Chocolatey installation failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Install-Program {
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$WingetId,
        [string]$ChocoId
    )

    if (Test-CommandExists -Name $Name) {
        return $true
    }

    $hasWinget = Test-WinGet
    if ($hasWinget -and $WingetId) {
        Write-Section "Installing $Name via winget"
        try {
            winget install --id $WingetId --silent --accept-source-agreements --accept-package-agreements -e
        }
        catch {
            Write-Host "Winget failed to install ${Name}: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        if (Test-CommandExists -Name $Name) { return $true }
    }

    $hasChoco = Install-Chocolatey
    if ($hasChoco -and $ChocoId) {
        Write-Section "Installing $Name via Chocolatey"
        try {
            choco install $ChocoId -y --no-progress
        }
        catch {
            Write-Host "Chocolatey failed to install ${Name}: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        if (Test-CommandExists -Name $Name) { return $true }
    }

    return $false
}

function Resolve-PythonInvoker {
    # Prefer py launcher for specific version, fallback to python on PATH
    $preferredMajMin = '3.12'
    if (Test-CommandExists -Name 'py') {
        try {
            py -$preferredMajMin -c "import sys; print(sys.version)" 1>$null 2>$null
            if ($LASTEXITCODE -eq 0) { return "py -$preferredMajMin" }
        } catch {}
        try {
            py -3 -c "import sys; print(sys.version)" 1>$null 2>$null
            if ($LASTEXITCODE -eq 0) { return 'py -3' }
        } catch {}
    }
    if (Test-CommandExists -Name 'python') { return 'python' }
    return $null
}

function Install-PythonIfMissing {
    $invoker = Resolve-PythonInvoker
    if ($invoker) { return $true }
    Write-Section 'Python not found, attempting to install it...'
    $ok = Install-Program -Name 'python' -WingetId 'Python.Python.3.12' -ChocoId 'python'
    if (-not $ok) {
        Write-Host 'Failed to install Python automatically. Please install Python and re-run.' -ForegroundColor Red
        return $false
    }
    return $true
}

function Install-GitIfMissing {
    if (Test-CommandExists -Name 'git') { return $true }
    Write-Section 'Git not found, attempting to install it...'
    $ok = Install-Program -Name 'git' -WingetId 'Git.Git' -ChocoId 'git'
    if (-not $ok) {
        Write-Host 'Failed to install Git automatically. Please install Git and re-run.' -ForegroundColor Red
        return $false
    }
    return $true
}

function Install-UvIfMissing {
    if (Test-CommandExists -Name 'uv') { return $true }
    Write-Section 'uv not found, attempting to install it...'
    try {
        powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    }
    catch {
        Write-Host "Failed to install uv automatically: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
    if (-not (Test-CommandExists -Name 'uv')) {
        Write-Host 'uv installation completed but the executable is still not available on PATH. Please restart the terminal or add $env:USERPROFILE\.cargo\bin to PATH.' -ForegroundColor Yellow
        return $false
    }
    return $true
}

function Update-Repository {
    param([string]$Path, [string]$Branch)
    $repoUrl = 'https://github.com/Zaroganos/goldflipper.git'
    if (-not (Test-Path $Path)) {
        Write-Section "Cloning repository into $Path"
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Push-Location (Split-Path $Path)
        try {
            git clone --branch $Branch --single-branch $repoUrl (Split-Path -Leaf $Path)
        } finally { Pop-Location }
    } else {
        if (Test-Path (Join-Path $Path '.git')) {
            Write-Section 'Updating repository...'
            Push-Location $Path
            try {
                git fetch --all --prune
                git checkout $Branch
                git pull --ff-only
            } finally { Pop-Location }
        } else {
            Write-Host "Target path already exists but it is not a git repository: $Path" -ForegroundColor Yellow
        }
    }
}

function Initialize-UvEnvironment {
    param([string]$RepoPath)
    Write-Section 'Installing dependencies with uv'
    Push-Location $RepoPath
    try {
        uv sync
        if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
    }
    finally {
        Pop-Location
    }
}

function Initialize-Settings {
    param([string]$RepoPath)
    # Always run first-run setup when installed via bootstrap
    # The setup wizard will detect existing settings and offer options
    Write-Section 'Launching Goldflipper first-run setup wizard'
    Push-Location $RepoPath
    try {
        uv run python -m goldflipper.first_run_setup
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Setup wizard was cancelled or failed. Settings will be created from template when TUI starts if needed.' -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Error running setup wizard: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host 'Settings profile will be created from template when Goldflipper starts if needed.' -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
}

function Start-App {
    param([string]$RepoPath)
    Write-Section 'Launching Goldflipper ...'

    Push-Location $RepoPath
    try {
        uv run goldflipper
    } finally {
        Pop-Location
    }
}

try {
    Write-Section 'Goldflipper setup starting...'
    if (-not (Install-GitIfMissing)) { throw 'Git is required but could not be installed.' }
    if (-not (Install-PythonIfMissing)) { throw 'Python is required but could not be installed.' }
    if (-not (Install-UvIfMissing)) { throw 'uv is required but could not be installed.' }

    Update-Repository -Path $InstallPath -Branch $Branch
    Initialize-UvEnvironment -RepoPath $InstallPath
    Initialize-Settings -RepoPath $InstallPath

    if (-not $NoLaunch) {
        Start-App -RepoPath $InstallPath
    } else {
        Write-Host "Setup complete. To launch later: `n`n  Push-Location `"$InstallPath`"`n  uv run goldflipper`n  Pop-Location`n" -ForegroundColor Green
    }
    Write-Section 'Done'
}
catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
