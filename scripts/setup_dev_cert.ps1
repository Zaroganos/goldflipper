# Fix PSModulePath contamination when launched via PS7->cmd->powershell chain.
# When Python spawns powershell.exe and the parent session was PS7, the inherited
# PSModulePath causes PS5.1 to try loading the PS7 Microsoft.PowerShell.Security
# module, which fails and leaves the Cert:\ PSDrive uninitialized.
# See: https://github.com/PowerShell/PowerShell/issues/18530
if ($PSVersionTable.PSVersion.Major -le 5) {
    $machinePath = [System.Environment]::GetEnvironmentVariable('PSModulePath', 'Machine')
    $userPath    = [System.Environment]::GetEnvironmentVariable('PSModulePath', 'User')
    $env:PSModulePath = ($machinePath, $userPath | Where-Object { $_ }) -join ';'
}

# Ensure Certificate PSProvider / Cert:\ drive is available
Import-Module Microsoft.PowerShell.Security -ErrorAction SilentlyContinue

# Check for existing certificate.
# Note: -CodeSigningCert switch was removed in PS7; use Where-Object filter instead.
$cert = Get-ChildItem -Path 'Cert:\CurrentUser\My' -ErrorAction SilentlyContinue | Where-Object {
    $_.Subject -like '*Goldflipper Development*' -and
    $_.EnhancedKeyUsageList.FriendlyName -contains 'Code Signing'
} | Select-Object -First 1

if ($null -eq $cert) {
    Write-Host 'Creating new self-signed certificate for Goldflipper Development...'
    $cert = New-SelfSignedCertificate -Type CodeSigningCert `
        -Subject 'CN=Goldflipper Development' `
        -KeyUsage DigitalSignature `
        -CertStoreLocation 'Cert:\CurrentUser\My' `
        -NotAfter (Get-Date).AddYears(5)
}

if ($null -ne $cert) {
    Write-Host "Certificate found: $($cert.Thumbprint)"
    return $cert.Thumbprint
} else {
    Write-Error 'Failed to find or create certificate.'
    exit 1
}
