<#
.SYNOPSIS
    CAT — Coding Agent Terminal Quick Installer (PowerShell).
.DESCRIPTION
    Convenience wrapper that runs the Windows installer script or installs via pip.
.EXAMPLE
    irm https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.ps1 | iex
    powershell -ExecutionPolicy Bypass -File install.ps1 -Install
#>

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Check,
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\CAT"
)

$scriptPath = Join-Path $PSScriptRoot "installer\windows\scripts\install.ps1"
if (Test-Path $scriptPath) {
    & powershell -ExecutionPolicy Bypass -File $scriptPath -InstallDir $InstallDir @PSBoundParameters
} else {
    # If piped from web / irm
    $tempScript = Join-Path $env:TEMP "cat_install.ps1"
    $url = "https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/installer/windows/scripts/install.ps1"
    try {
        Invoke-WebRequest -Uri $url -OutFile $tempScript -UseBasicParsing
        & powershell -ExecutionPolicy Bypass -File $tempScript -InstallDir $InstallDir @PSBoundParameters
        Remove-Item -Path $tempScript -Force -ErrorAction SilentlyContinue
    } catch {
        # Fallback to direct pip install
        Write-Host "Downloading CAT CLI installer via pip..." -ForegroundColor Cyan
        & python -m pip install --upgrade cct-cli
    }
}
