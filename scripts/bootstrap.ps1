<#
.SYNOPSIS
    Goldflipper bootstrap installer.

.DESCRIPTION
    Fetches the latest release manifest for a chosen channel from the
    Goldflipper distribution server, then downloads and launches either
    the MSI installer (default) or the portable EXE.

.USAGE
    # One-liner to distribute to end users:
    irm 'https://cloud.zimerguz.net/s/558TjEgMCdEjaLN/download' | iex

.NOTES
    - Requires PowerShell 5.1+ (Windows 10 / 11 built-in)
    - MSI per-user install needs no elevation (default scope in WixUI_Advanced)
    - MSI per-machine install will trigger a UAC prompt
    - version.json schema expected per channel (lives in Distribution/<channel>/version.json):
        {
            "version":      "0.2.5",
            "download_url": "https://cloud.zimerguz.net/s/osCCAY2Gm3mNKPK/download?path=/&files=goldflipper-0.2.5-x64.msi",
            "portable_url": "https://cloud.zimerguz.net/s/osCCAY2Gm3mNKPK/download?path=/&files=goldflipper-0.2.5-portable.exe",
            "notes":        "Human-readable release notes"
        }
      Each channel uses a single folder-level public share (token never changes).
      Only version.json content is updated on each release — no new shares needed.

    Share tokens (cloud.zimerguz.net / darktower):
      bootstrap.ps1  -> 558TjEgMCdEjaLN  (public, no password)
      multi/         -> osCCAY2Gm3mNKPK  (public, no password)
      stable/        -> goldflipper       (TBD)
      streamlit-wem/ -> streamlit-wem     (TBD)
#>

$ErrorActionPreference = 'Stop'

# ── Channel → folder share token ──────────────────────────────────────────────
# Each token is the Nextcloud public folder share for Distribution/<channel>/.
# Tokens never rotate; only version.json content changes on each publish.
$channelTokens = [ordered]@{
    multi           = 'osCCAY2Gm3mNKPK'   # Distribution/multi/   <- first live channel
    stable          = 'goldflipper'        # Distribution/stable/  (TBD)
    'streamlit-wem' = 'streamlit-wem'      # Distribution/streamlit-wem/ (TBD)
}
$ncBase = 'https://cloud.zimerguz.net'

# ── Nextcloud public-share WebDAV auth ────────────────────────────────────────
# Public (no-password) folder shares: WebDAV accepts token as username, empty pw.
function Get-NcHeader($token) {
    $bytes = [Text.Encoding]::ASCII.GetBytes("${token}:")
    @{ Authorization = 'Basic ' + [Convert]::ToBase64String($bytes) }
}

# ── Header ─────────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '  +--------------------------------------+' -ForegroundColor Cyan
Write-Host '  |   Goldflipper Bootstrap Installer   |' -ForegroundColor Cyan
Write-Host '  +--------------------------------------+' -ForegroundColor Cyan
Write-Host ''

# ── Channel selection ──────────────────────────────────────────────────────────
$keys      = @($channelTokens.Keys)
$defaultCh = $keys[0]
Write-Host '  Release channels:' -ForegroundColor White
for ($i = 0; $i -lt $keys.Count; $i++) {
    $tag = if ($keys[$i] -eq $defaultCh) { '  <- default' } else { '' }
    Write-Host "    [$($i + 1)] $($keys[$i])$tag"
}
Write-Host ''
$raw = Read-Host "  Select channel [Enter = $defaultCh]"
if (-not $raw -or $raw -notmatch '^\d+$' -or [int]$raw -lt 1 -or [int]$raw -gt $keys.Count) {
    $ch = $defaultCh
} else {
    $ch = $keys[[int]$raw - 1]
}
Write-Host "  -> Channel: $ch" -ForegroundColor Green
Write-Host ''

# ── Fetch version.json ─────────────────────────────────────────────────────────
$token = $channelTokens[$ch]
$ncHeader = Get-NcHeader $token
Write-Host '  Fetching release info...' -ForegroundColor DarkGray
$manifest = Invoke-RestMethod "$ncBase/public.php/webdav/version.json" -Headers $ncHeader
Write-Host "  Version : $($manifest.version)" -ForegroundColor Yellow
if ($manifest.notes) { Write-Host "  Notes   : $($manifest.notes)" }
Write-Host ''

# ── Install type: MSI (default) or Portable — 10-second timeout ───────────────
Write-Host '  Install type:' -ForegroundColor Cyan
Write-Host '    [M]  MSI Installer  - Start Menu, uninstaller, per-user or machine  (default)'
if ($manifest.portable_url) {
    Write-Host '    [P]  Portable EXE   - run from anywhere, no install required'
}
Write-Host ''

$installType = 'msi'
$deadline    = (Get-Date).AddSeconds(10)

# Drain any keys buffered from prior Read-Host calls (e.g. the channel-selection
# Enter) so they don't immediately trigger a false KeyAvailable hit.
# [Console]::KeyAvailable is used instead of $Host.UI.RawUI.KeyAvailable because
# the RawUI variant can return $true spuriously, causing ReadKey to block
# indefinitely and prevent the default from being selected after the timeout.
try { while ([Console]::KeyAvailable) { [Console]::ReadKey($true) | Out-Null } } catch { }

while ((Get-Date) -lt $deadline) {
    $remaining = [math]::Ceiling(($deadline - (Get-Date)).TotalSeconds)
    Write-Host "`r  Choose [$(if ($manifest.portable_url) {'M/P'} else {'M'})] ($remaining`s -> MSI): " -NoNewline -ForegroundColor Cyan
    $keyPressed = $false
    try { $keyPressed = [Console]::KeyAvailable } catch { }
    if ($keyPressed) {
        try {
            $key = [Console]::ReadKey($true)
            if ($key.KeyChar -match '^[Pp]$' -and $manifest.portable_url) {
                $installType = 'portable'
            }
        } catch { }
        break
    }
    Start-Sleep -Milliseconds 200
}
Write-Host "`r  -> $($installType.ToUpper())                        " -ForegroundColor Green
Write-Host ''

# ── Resolve download URL and output filename ───────────────────────────────────
if ($installType -eq 'msi') {
    $downloadUrl = $manifest.download_url
    $outFile     = "$env:TEMP\goldflipper-$($manifest.version)-$ch-x64.msi"
} else {
    $downloadUrl = $manifest.portable_url
    $outFile     = "$env:TEMP\goldflipper-$($manifest.version)-$ch-portable.exe"
}

if (-not $downloadUrl) {
    Write-Host '  ERROR: version.json is missing the download URL for this install type.' -ForegroundColor Red
    exit 1
}

# ── Download ──────────────────────────────────────────────────────────────────
$fileName = [System.IO.Path]::GetFileName($outFile)
Write-Host "  Downloading $fileName (this may take a minute)..." -ForegroundColor Cyan
$ProgressPreference = 'SilentlyContinue'   # suppress PS5.1 chunk-by-chunk noise, also speeds up download significantly
Invoke-WebRequest $downloadUrl -OutFile $outFile -UseBasicParsing -Headers $ncHeader
$ProgressPreference = 'Continue'
Write-Host '  Download complete.' -ForegroundColor Green
Write-Host ''

# ── Launch ────────────────────────────────────────────────────────────────────
if ($installType -eq 'msi') {
    Write-Host '  Launching MSI installer...' -ForegroundColor Cyan
    Start-Process msiexec.exe -ArgumentList "/i `"$outFile`"" -Wait
    Remove-Item $outFile -ErrorAction SilentlyContinue
    Write-Host '  Done.' -ForegroundColor Green
} else {
    Write-Host '  Launching Goldflipper (portable)...' -ForegroundColor Cyan
    Start-Process $outFile
    Write-Host '  Goldflipper is running.' -ForegroundColor Green
}
Write-Host ''
