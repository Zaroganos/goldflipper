#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallPath = (Join-Path $env:USERPROFILE 'goldflipper'),
    [string]$Branch = 'main',
    [switch]$NoLaunch
)

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
    Write-Host 'winget not found. On some Windows 10 editions it may be missing. Falling back to Chocolatey if available.' -ForegroundColor Yellow
    return $false
}

function Install-Chocolatey {
    if (Test-CommandExists -Name 'choco') { return $true }
    if (-not (Test-Admin)) {
        Write-Host 'Chocolatey not found and admin rights not detected. Skipping Chocolatey install.' -ForegroundColor Yellow
        return $false
    }
    Write-Section 'Installing Chocolatey (requires admin)'
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
            Write-Host "winget failed to install ${Name}: $($_.Exception.Message)" -ForegroundColor Yellow
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
    Write-Section 'Python not found; attempting installation'
    $ok = Install-Program -Name 'python' -WingetId 'Python.Python.3.12' -ChocoId 'python'
    if (-not $ok) {
        Write-Host 'Failed to install Python automatically. Please install Python 3.10+ and re-run.' -ForegroundColor Red
        return $false
    }
    return $true
}

function Install-GitIfMissing {
    if (Test-CommandExists -Name 'git') { return $true }
    Write-Section 'Git not found; attempting installation'
    $ok = Install-Program -Name 'git' -WingetId 'Git.Git' -ChocoId 'git'
    if (-not $ok) {
        Write-Host 'Failed to install Git automatically. Please install Git and re-run.' -ForegroundColor Red
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
            Write-Section 'Updating repository'
            Push-Location $Path
            try {
                git fetch --all --prune
                git checkout $Branch
                git pull --ff-only
            } finally { Pop-Location }
        } else {
            Write-Host "Target path exists but is not a git repo: $Path" -ForegroundColor Yellow
        }
    }
}

function Initialize-Venv {
    param([string]$RepoPath)
    $venvPath = Join-Path $RepoPath '.venv'
    $python = Resolve-PythonInvoker
    if (-not $python) { throw 'Python invoker not found after installation.' }
    Write-Section 'Creating virtual environment'
    if (-not (Test-Path $venvPath)) {
        & $env:ComSpec /c "${python} -m venv `"$venvPath`""
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment.' }
    }
    # Activate for current process
    $scriptsPath = Join-Path $venvPath 'Scripts'
    $env:VIRTUAL_ENV = $venvPath
    $env:Path = "$scriptsPath;$($env:Path)"

    Write-Section 'Upgrading pip and installing requirements'
    python -m pip install --upgrade pip wheel
    if (Test-Path (Join-Path $RepoPath 'requirements.txt')) {
        python -m pip install -r (Join-Path $RepoPath 'requirements.txt')
    } else {
        python -m pip install -e $RepoPath
    }
}

function Initialize-Settings {
    param([string]$RepoPath)
    $cfgDir = Join-Path $RepoPath 'goldflipper\config'
    $template = Join-Path $cfgDir 'settings_template.yaml'
    $settings = Join-Path $cfgDir 'settings.yaml'
    if ((Test-Path $template) -and -not (Test-Path $settings)) {
        Write-Section 'Creating initial settings.yaml from template'
        Copy-Item $template $settings -Force
    }
}

function Start-App {
    param([string]$RepoPath)
    Write-Section 'Launching Goldflipper TUI'
    Push-Location $RepoPath
    try {
        python .\goldflipper\goldflipper_tui.py
    } finally {
        Pop-Location
    }
}

try {
    Write-Section 'Goldflipper bootstrap starting'
    if (-not (Install-GitIfMissing)) { throw 'Git is required but could not be installed.' }
    if (-not (Install-PythonIfMissing)) { throw 'Python is required but could not be installed.' }

    Update-Repository -Path $InstallPath -Branch $Branch
    Initialize-Venv -RepoPath $InstallPath
    Initialize-Settings -RepoPath $InstallPath

    if (-not $NoLaunch) {
        Start-App -RepoPath $InstallPath
    } else {
        Write-Host "Bootstrap complete. To launch later: `n`n  `"$InstallPath\\.venv\\Scripts\\python.exe`" `"$InstallPath\\goldflipper\\goldflipper_tui.py`"`n" -ForegroundColor Green
    }
    Write-Section 'Done'
}
catch {
    Write-Host "Bootstrap failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
