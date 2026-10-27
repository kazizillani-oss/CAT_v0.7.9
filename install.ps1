<#
.SYNOPSIS
    CAT — Coding Agent Terminal Universal Windows Installer.
.DESCRIPTION
    Installs, updates, checks, or uninstalls CAT CLI on Windows.
    Compatible with:
      - Direct execution: powershell -ExecutionPolicy Bypass -File install.ps1 -Install
      - Web one-liner: irm https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.ps1 | iex
      - Curl: curl.exe -fsSL https://.../install.ps1 -o install.ps1; powershell -ExecutionPolicy Bypass -File .\install.ps1 -Install
.PARAMETER Install
    Perform full installation.
.PARAMETER Uninstall
    Remove CAT CLI and clean up PATH and aliases.
.PARAMETER Update
    Update CAT CLI to latest version.
.PARAMETER Check
    Perform environment and installation health check.
.PARAMETER InstallDir
    Target installation directory (default: %LOCALAPPDATA%\Programs\CAT).
.PARAMETER Force
    Force reinstall even if already installed.
.PARAMETER Quiet
    Suppress interactive prompts and verbose output.
#>

[CmdletBinding(DefaultParameterSetName = 'Install')]
param(
    [Parameter(ParameterSetName = 'Install')]
    [switch]$Install,

    [Parameter(ParameterSetName = 'Uninstall')]
    [switch]$Uninstall,

    [Parameter(ParameterSetName = 'Update')]
    [switch]$Update,

    [Parameter(ParameterSetName = 'Check')]
    [switch]$Check,

    [Parameter()]
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\CAT",

    [Parameter()]
    [switch]$Force,

    [Parameter()]
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

function Write-CatHeader {
    if ($Quiet) { return }
    Write-Host ''
    Write-Host '  ================================================================' -ForegroundColor Cyan
    Write-Host '     CAT — Coding Agent Terminal (Windows Installer)              ' -ForegroundColor Magenta
    Write-Host '     Version: 0.8.0b1 | Tokyo Night Edition                       ' -ForegroundColor DarkCyan
    Write-Host '  ================================================================' -ForegroundColor Cyan
    Write-Host ''
}

function Find-Python {
    $candidates = @('python', 'py -3', 'python3')
    foreach ($cand in $candidates) {
        try {
            $parts = $cand -split ' '
            $cmd = $parts[0]
            $cmdArgs = if ($parts.Length -gt 1) { $parts[1..($parts.Length - 1)] } else { @() }
            $res = & $cmd @cmdArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $res) {
                $verParts = $res.Trim() -split '\.'
                if ($verParts.Length -ge 2) {
                    $major = [int]$verParts[0]
                    $minor = [int]$verParts[1]
                    if ($major -ge 3 -and $minor -ge 10) {
                        $exePath = & $cmd @cmdArgs -c "import sys; print(sys.executable)" 2>$null
                        return @{
                            Command = $cmd
                            Args = $cmdArgs
                            Version = $res.Trim()
                            Executable = $exePath.Trim()
                        }
                    }
                }
            }
        } catch {
            # Continue checking next candidate
        }
    }
    return $null
}

function Copy-CleanModules([string]$source, [string]$destination) {
    if (-not (Test-Path $destination)) {
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
    }
    Get-ChildItem -Path $source -Recurse -Force | ForEach-Object {
        $rel = $_.FullName.Substring($source.Length).TrimStart('\', '/')
        if ($rel -match '__pycache__' -or $rel -match '\.pytest_cache' -or $rel -match '\.sqlite-(shm|wal)$') {
            return
        }
        $target = Join-Path $destination $rel
        if ($_.PSIsContainer) {
            if (-not (Test-Path $target)) {
                New-Item -ItemType Directory -Path $target -Force | Out-Null
            }
        } else {
            try {
                Copy-Item -Path $_.FullName -Destination $target -Force -ErrorAction SilentlyContinue
            } catch { }
        }
    }
}

function Get-ShimCmd([string]$module, [string]$pythonExe) {
    $lines = @(
        '@echo off',
        'setlocal enabledelayedexpansion',
        'set "CAT_INSTALL_DIR=%~dp0.."',
        'if exist "%CAT_INSTALL_DIR%\lib\calc_terminal" (',
        '    set "PYTHONPATH=%CAT_INSTALL_DIR%\lib;!PYTHONPATH!"',
        ')',
        ('"' + $pythonExe + '" -m ' + $module + ' %*')
    )
    return ($lines -join "`r`n")
}

function Install-Cat {
    Write-CatHeader
    Write-Host '[1/5] Detecting Python runtime...' -ForegroundColor Yellow

    $py = Find-Python
    if (-not $py) {
        Write-Error 'Python 3.10 or higher was not found in PATH. Please install Python from https://www.python.org/downloads/ or run: winget install Python.Python.3.12'
        exit 1
    }
    Write-Host ('      Found Python ' + $py.Version + ' at: ' + $py.Executable) -ForegroundColor Green

    # Setup directories
    Write-Host '[2/5] Creating directory layout...' -ForegroundColor Yellow
    $binDir = Join-Path $InstallDir 'bin'
    $libDir = Join-Path $InstallDir 'lib'
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    New-Item -ItemType Directory -Path $libDir -Force | Out-Null
    Write-Host ('      Install directory: ' + $InstallDir) -ForegroundColor Green

    # Locate source repository safely (handles irm | iex where $PSScriptRoot is null/empty)
    Write-Host '[3/5] Installing CAT core and dependencies...' -ForegroundColor Yellow
    $repoRoot = $null

    # Check potential repository directories
    $possibleDirs = @()
    if ($PSScriptRoot -and (Test-Path $PSScriptRoot)) {
        $possibleDirs += $PSScriptRoot
        $possibleDirs += (Join-Path $PSScriptRoot '..')
        $possibleDirs += (Join-Path $PSScriptRoot '..\..\..')
    }
    $curr = (Get-Location).Path
    if ($curr -and (Test-Path $curr)) {
        $possibleDirs += $curr
        $possibleDirs += (Join-Path $curr '..')
    }

    foreach ($cand in $possibleDirs) {
        try {
            if (Test-Path $cand) {
                $resolved = (Resolve-Path $cand).Path
                if ((Test-Path (Join-Path $resolved 'pyproject.toml')) -and (Test-Path (Join-Path $resolved 'calc_terminal'))) {
                    $repoRoot = $resolved
                    break
                }
            }
        } catch { }
    }

    if ($repoRoot) {
        Write-Host ('      Found local CAT repository at: ' + $repoRoot) -ForegroundColor DarkGray

        # Synchronize local calc_terminal to lib directory cleanly
        $calcSrc = Join-Path $repoRoot 'calc_terminal'
        if (Test-Path $calcSrc) {
            $calcDst = Join-Path $libDir 'calc_terminal'
            Copy-CleanModules -source $calcSrc -destination $calcDst
            Write-Host ('      Synchronized local runtime modules to: ' + $calcDst) -ForegroundColor Green
        }

        # Fast package registration
        try {
            & $py.Executable -m pip install -e "$repoRoot" --no-deps --no-build-isolation --no-warn-script-location 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host '      Installed cct-cli package via pip successfully.' -ForegroundColor Green
            }
        } catch {
            Write-Host '      Pip install notice: continuing with standalone runtime shims.' -ForegroundColor DarkYellow
        }
    } else {
        # Standalone install: try PyPI first, then GitHub repository fallback
        Write-Host '      Installing cct-cli package into Python environment...' -ForegroundColor DarkGray
        $pipSuccess = $false
        try {
            & $py.Executable -m pip install --upgrade cct-cli 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $pipSuccess = $true
                Write-Host '      Installed cct-cli from PyPI successfully.' -ForegroundColor Green
            }
        } catch { }

        if (-not $pipSuccess) {
            try {
                Write-Host '      PyPI package pending release; installing latest build from GitHub...' -ForegroundColor DarkYellow
                & $py.Executable -m pip install --upgrade git+https://github.com/kazizillani-oss/CAT_v0.7.9.git 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $pipSuccess = $true
                    Write-Host '      Installed latest CAT build from GitHub successfully.' -ForegroundColor Green
                }
            } catch { }
        }
    }

    # Generate Launcher Shims in $binDir
    Write-Host '[4/5] Creating command launchers and shims...' -ForegroundColor Yellow

    # cat.cmd
    Set-Content -Path (Join-Path $binDir 'cat.cmd') -Value (Get-ShimCmd 'calc_terminal.cli' $py.Executable) -Encoding ASCII

    # catx.cmd (bypass shell alias collisions)
    Set-Content -Path (Join-Path $binDir 'catx.cmd') -Value (Get-ShimCmd 'calc_terminal.cli' $py.Executable) -Encoding ASCII

    # cct.cmd (legacy alias)
    Set-Content -Path (Join-Path $binDir 'cct.cmd') -Value (Get-ShimCmd 'calc_terminal.cli' $py.Executable) -Encoding ASCII

    # cat-curl.cmd (HTTP & REST Client)
    Set-Content -Path (Join-Path $binDir 'cat-curl.cmd') -Value (Get-ShimCmd 'calc_terminal.commands.curl_cmd' $py.Executable) -Encoding ASCII

    # cat-brew.cmd (Universal Homebrew / Formula Manager)
    Set-Content -Path (Join-Path $binDir 'cat-brew.cmd') -Value (Get-ShimCmd 'calc_terminal.commands.brew_cmd' $py.Executable) -Encoding ASCII

    # cat-sudo.cmd (Administrative Elevation)
    Set-Content -Path (Join-Path $binDir 'cat-sudo.cmd') -Value (Get-ShimCmd 'calc_terminal.commands.sudo_cmd' $py.Executable) -Encoding ASCII

    # PowerShell direct function helper
    $linesPs1 = @(
        '$ErrorActionPreference = "Stop"',
        '$installDir = Split-Path -Parent $PSScriptRoot',
        'if (Test-Path (Join-Path $installDir "lib\calc_terminal")) {',
        '    $env:PYTHONPATH = (Join-Path $installDir "lib") + ";" + $env:PYTHONPATH',
        '}',
        ('& "' + $py.Executable + '" -m calc_terminal.cli @args')
    )
    $catPs1 = $linesPs1 -join "`r`n"
    Set-Content -Path (Join-Path $binDir 'cat.ps1') -Value $catPs1 -Encoding ASCII

    Write-Host ('      Created command shims in ' + $binDir + ':') -ForegroundColor Green
    Write-Host '        - cat.cmd / cat.ps1       (CAT CLI launch)' -ForegroundColor DarkCyan
    Write-Host '        - catx.cmd                (PowerShell collision-safe alias)' -ForegroundColor DarkCyan
    Write-Host '        - cct.cmd                 (Classic alias)' -ForegroundColor DarkCyan
    Write-Host '        - cat-curl.cmd            (Native HTTP/REST client)' -ForegroundColor DarkCyan
    Write-Host '        - cat-brew.cmd            (Universal package bridge)' -ForegroundColor DarkCyan
    Write-Host '        - cat-sudo.cmd            (Universal privilege elevation)' -ForegroundColor DarkCyan

    # Update User Environment PATH
    Write-Host '[5/5] Configuring environment and PowerShell profile...' -ForegroundColor Yellow
    $userPath = [Environment]::GetEnvironmentVariable('Path', [EnvironmentVariableTarget]::User)
    if ($userPath -notlike ('*' + $binDir + '*')) {
        $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $binDir } else { $userPath.TrimEnd(';') + ';' + $binDir }
        [Environment]::SetEnvironmentVariable('Path', $newUserPath, [EnvironmentVariableTarget]::User)
        Write-Host ('      Added ' + $binDir + ' to User PATH.') -ForegroundColor Green
    } else {
        Write-Host ('      ' + $binDir + ' is already present in User PATH.') -ForegroundColor DarkGray
    }

    # Update current session path immediately
    if ($env:Path -notlike ('*' + $binDir + '*')) {
        $env:Path = $binDir + ';' + $env:Path
    }

    # Configure PowerShell Profile so 'cat' invokes CAT instead of Get-Content
    try {
        $profilePath = $PROFILE.CurrentUserCurrentHost
        if ($profilePath) {
            $profileParent = Split-Path -Parent $profilePath
            if (-not (Test-Path $profileParent)) {
                New-Item -ItemType Directory -Path $profileParent -Force | Out-Null
            }
            $aliasMarker = '# === CAT CLI Profile Integration ==='
            $aliasLines = @(
                $aliasMarker,
                ('if (Get-Command "' + $binDir + '\cat.cmd" -ErrorAction SilentlyContinue) {'),
                '    Remove-Item Alias:cat -Force -ErrorAction SilentlyContinue',
                ('    function global:cat { & "' + $binDir + '\cat.cmd" @args }'),
                '}',
                '# ==================================='
            )
            $aliasBlock = $aliasLines -join "`r`n"
            $existingProfile = if (Test-Path $profilePath) { Get-Content $profilePath -Raw } else { '' }
            if ($existingProfile -notlike ('*' + $aliasMarker + '*')) {
                Add-Content -Path $profilePath -Value ("`r`n" + $aliasBlock)
                Write-Host ('      Added PowerShell profile alias helper to: ' + $profilePath) -ForegroundColor Green
            }
        }
        # In current session:
        Remove-Item Alias:cat -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host '      Notice: Could not update profile automatically. You can always use catx or cat.cmd.' -ForegroundColor DarkYellow
    }

    Write-Host ''
    Write-Host '  ================================================================' -ForegroundColor Green
    Write-Host '     [SUCCESS] CAT CLI Installed Successfully!                    ' -ForegroundColor Green
    Write-Host '  ================================================================' -ForegroundColor Green
    Write-Host ''
    Write-Host '  Try running in any terminal:' -ForegroundColor Yellow
    Write-Host '    cat --version        # Check installed version' -ForegroundColor Cyan
    Write-Host '    cat curl --version   # Test built-in curl HTTP client' -ForegroundColor Cyan
    Write-Host '    cat brew doctor      # Check package system health' -ForegroundColor Cyan
    Write-Host '    cat sudo --status    # Check administrative elevation privileges' -ForegroundColor Cyan
    Write-Host '    cat                  # Launch interactive Tokyo Night terminal' -ForegroundColor Cyan
    Write-Host ''
}

function Uninstall-Cat {
    Write-CatHeader
    Write-Host ('Uninstalling CAT CLI from ' + $InstallDir + '...') -ForegroundColor Yellow

    if (Test-Path $InstallDir) {
        Remove-Item -Path $InstallDir -Recurse -Force
        Write-Host ('Removed directory: ' + $InstallDir) -ForegroundColor Green
    }

    $binDir = Join-Path $InstallDir 'bin'
    $userPath = [Environment]::GetEnvironmentVariable('Path', [EnvironmentVariableTarget]::User)
    if ($userPath -like ('*' + $binDir + '*')) {
        $parts = $userPath -split ';' | Where-Object { $_ -and $_ -ne $binDir }
        $newUserPath = $parts -join ';'
        [Environment]::SetEnvironmentVariable('Path', $newUserPath, [EnvironmentVariableTarget]::User)
        Write-Host ('Removed ' + $binDir + ' from User PATH.') -ForegroundColor Green
    }

    Write-Host '[SUCCESS] CAT CLI has been uninstalled.' -ForegroundColor Green
}

function Check-Cat {
    Write-CatHeader
    Write-Host 'Running CAT CLI Environment Health Check...' -ForegroundColor Yellow
    $py = Find-Python
    if ($py) {
        Write-Host (' [OK] Python ' + $py.Version + ' found at ' + $py.Executable) -ForegroundColor Green
    } else {
        Write-Host ' [FAIL] Python 3.10+ not found in PATH' -ForegroundColor Red
    }

    $binDir = Join-Path $InstallDir 'bin'
    $catShim = Join-Path $binDir 'cat.cmd'
    if (Test-Path $catShim) {
        Write-Host (' [OK] CAT launcher found at ' + $catShim) -ForegroundColor Green
    } else {
        Write-Host (' [INFO] CAT launcher not found in ' + $binDir) -ForegroundColor DarkGray
    }

    $userPath = [Environment]::GetEnvironmentVariable('Path', [EnvironmentVariableTarget]::User)
    if ($userPath -like ('*' + $binDir + '*')) {
        Write-Host (' [OK] User PATH includes ' + $binDir) -ForegroundColor Green
    } else {
        Write-Host (' [WARN] User PATH does not include ' + $binDir) -ForegroundColor Yellow
    }
}

# Entry point logic
if ($Uninstall) {
    Uninstall-Cat
} elseif ($Check) {
    Check-Cat
} elseif ($Update) {
    Install-Cat
} else {
    Install-Cat
}
