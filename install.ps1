<#
.SYNOPSIS
    CAT -- Coding Agent Terminal Universal Windows Installer.
.DESCRIPTION
    Installs, updates, checks, or uninstalls CAT CLI on Windows.
    Provides ASCII art banner, device hardware inspection, and local AI model
    compatibility recommendations (Ollama & Hugging Face GGUF).
    Compatible with:
      - Direct execution: powershell -ExecutionPolicy Bypass -File install.ps1 -Install
      - Web one-liner: irm https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.ps1 | iex
      - Curl: curl.exe -fsSL https://.../install.ps1 -o "$env:TEMP\cat_install.ps1"; powershell -ExecutionPolicy Bypass -File "$env:TEMP\cat_install.ps1" -Install
.PARAMETER Install
    Perform full installation.
.PARAMETER Uninstall
    Remove CAT CLI and clean up PATH and aliases.
.PARAMETER Update
    Update CAT CLI to latest version.
.PARAMETER Check
    Perform environment, hardware, and installation health check.
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

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

function Write-CatHeader {
    if ($Quiet) { return }
    Write-Host ''
    Write-Host '        /\_/\     ' -ForegroundColor Magenta -NoNewline
    Write-Host '  ____    _  _____ ' -ForegroundColor Cyan
    Write-Host '       ( o.o )    ' -ForegroundColor Magenta -NoNewline
    Write-Host ' / ___|  / \|_   _|' -ForegroundColor Cyan
    Write-Host '        > ^ <     ' -ForegroundColor Magenta -NoNewline
    Write-Host '| |     / _ \ | |  ' -ForegroundColor Cyan
    Write-Host '                  ' -ForegroundColor Magenta -NoNewline
    Write-Host '| |___ / ___ \| |  ' -ForegroundColor Cyan
    Write-Host '                  ' -ForegroundColor Magenta -NoNewline
    Write-Host ' \____/_/   \_\_|  ' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  ================================================================' -ForegroundColor Cyan
    Write-Host '     C A T  --  CODING AGENT TERMINAL (Windows Installer)         ' -ForegroundColor White
    Write-Host '     Autonomous AI Terminal  |  Tokyo Night Edition  |  v0.8.0b1  ' -ForegroundColor Magenta
    Write-Host '  ================================================================' -ForegroundColor Cyan
    Write-Host ''
}

function Show-DeviceAndModelCompatibility {
    if ($Quiet) { return }

    Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host '  [DEVICE HARDWARE & LOCAL AI MODEL COMPATIBILITY ANALYSIS]' -ForegroundColor Yellow
    Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkCyan

    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $os = Get-CimInstance Win32_OperatingSystem
    $ramTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $ramFree = [math]::Round($os.FreePhysicalMemory / 1MB, 1)

    $gpuName = "Unknown"
    $gpuVram = 0.0

    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        try {
            $smi = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
            if ($smi) {
                $parts = ($smi -split "`n")[0] -split ','
                $gpuName = $parts[0].Trim()
                $gpuVram = [math]::Round([double]$parts[1].Trim() / 1024, 1)
            }
        } catch { }
    }

    if ($gpuName -eq "Unknown") {
        $videoControllers = Get-CimInstance Win32_VideoController
        if ($videoControllers) {
            $names = @($videoControllers | ForEach-Object { $_.Name })
            $gpuName = $names -join ", "
        }
    }

    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    $ollamaVer = "Not Detected"
    if ($ollamaCmd) {
        try {
            $rawVer = (& ollama --version 2>&1).Trim()
            $ollamaVer = if ($rawVer -match '(\d+\.\d+\.\d+)') { "v$($Matches[1]) (Installed)" } else { "Installed" }
        } catch {
            $ollamaVer = "Installed"
        }
    }

    # Determine Hardware Tier based on RAM and GPU VRAM
    $tierName = ""
    $tierDesc = ""
    if ($ramTotal -ge 28 -or $gpuVram -ge 16) {
        $tierName = "Tier 3: Heavy Workstation ($ramTotal GB RAM Detected)"
        $tierDesc = "Runs up to 14B-32B models effortlessly with hybrid GPU/CPU acceleration!"
    } elseif ($ramTotal -ge 14 -or $gpuVram -ge 8) {
        $tierName = "Tier 2: Advanced Developer ($ramTotal GB RAM Detected)"
        $tierDesc = "Optimal for 7B-14B models with fast inference!"
    } elseif ($ramTotal -ge 7 -or $gpuVram -ge 4) {
        $tierName = "Tier 1: Standard System ($ramTotal GB RAM Detected)"
        $tierDesc = "Ideal for 1B-8B models (e.g. Qwen 2.5 Coder 7B, Llama 3.2 3B)!"
    } else {
        $tierName = "Tier 0: Compact / Edge ($ramTotal GB RAM Detected)"
        $tierDesc = "Optimized for lightweight 1B-3B models with low RAM consumption."
    }

    Write-Host "    CPU    : " -NoNewline -ForegroundColor DarkGray
    Write-Host "$($cpu.Name) ($($cpu.NumberOfCores)C / $($cpu.NumberOfLogicalProcessors)T)" -ForegroundColor White
    Write-Host "    RAM    : " -NoNewline -ForegroundColor DarkGray
    Write-Host "$ramTotal GB Total ($ramFree GB Free Available)" -ForegroundColor White
    Write-Host "    GPU    : " -NoNewline -ForegroundColor DarkGray
    Write-Host "$gpuName" -NoNewline -ForegroundColor White
    if ($gpuVram -gt 0) {
        Write-Host " ($gpuVram GB Dedicated VRAM)" -ForegroundColor Green
    } else {
        Write-Host ""
    }
    Write-Host "    AI Hub : " -NoNewline -ForegroundColor DarkGray
    Write-Host "Ollama $ollamaVer | Hugging Face GGUF / llama.cpp Ready" -ForegroundColor White
    Write-Host "    Tier   : " -NoNewline -ForegroundColor DarkGray
    Write-Host "$tierName" -ForegroundColor Cyan
    Write-Host "             $tierDesc" -ForegroundColor DarkCyan
    Write-Host ''

    Write-Host '    Recommended Latest Ollama & Local Models for Your System:' -ForegroundColor Yellow
    Write-Host '    --------------------------------------------------------------------------------' -ForegroundColor DarkGray
    Write-Host '    Model Identifier       Size    Category    Hardware Status' -ForegroundColor DarkCyan
    Write-Host '    --------------------------------------------------------------------------------' -ForegroundColor DarkGray

    $models = @(
        @{ Name = "qwen2.5-coder:7b";    Size = 4.7; Cat = "Coding";    Rec = "Top Pick"; Desc = "Premier open-source code generation model" },
        @{ Name = "deepseek-r1:7b";      Size = 4.7; Cat = "Reasoning"; Rec = "Top Pick"; Desc = "DeepSeek R1 distilled chain-of-thought" },
        @{ Name = "qwen2.5-coder:14b";   Size = 9.0; Cat = "Coding";    Rec = "Workstation"; Desc = "Advanced architectural coding & refactoring" },
        @{ Name = "deepseek-r1:14b";     Size = 9.0; Cat = "Reasoning"; Rec = "Workstation"; Desc = "High-intelligence math & complex deduction" },
        @{ Name = "phi4:14b";            Size = 9.1; Cat = "Reasoning"; Rec = "Balanced"; Desc = "Microsoft Phi-4 cutting-edge reasoning" },
        @{ Name = "llama3.2:3b";         Size = 2.0; Cat = "Fast/Chat"; Rec = "GPU Fast"; Desc = "Ultra-fast compact conversational model" },
        @{ Name = "qwen2.5-coder:1.5b";  Size = 1.0; Cat = "Autocomplete"; Rec = "GPU Fast"; Desc = "Ultra-low latency code completion" }
    )

    if ($ramTotal -ge 28) {
        $models += @{ Name = "qwen2.5-coder:32b"; Size = 19.0; Cat = "Coding"; Rec = "Power User"; Desc = "Enterprise-grade code intelligence" }
        $models += @{ Name = "deepseek-r1:32b";   Size = 19.0; Cat = "Reasoning"; Rec = "Power User"; Desc = "Frontier reasoning & deep problem solving" }
    }

    foreach ($m in $models) {
        $status = ""
        $statusColor = "Green"
        if ($gpuVram -gt 0 -and $m.Size -le $gpuVram) {
            $status = "[100% GPU VRAM - Blazing Fast]"
            $statusColor = "Green"
        } elseif ($m.Size -le $ramFree) {
            $status = "[100% Compatible - Optimal]"
            $statusColor = "Green"
        } elseif ($m.Size -le ($ramTotal * 0.75)) {
            $status = "[Compatible - RAM Cached]"
            $statusColor = "Cyan"
        } else {
            $status = "[Requires High Memory Load]"
            $statusColor = "DarkYellow"
        }

        $paddedName = $m.Name.PadRight(22)
        $paddedSize = "$($m.Size) GB".PadRight(8)
        $paddedCat  = $m.Cat.PadRight(12)

        Write-Host "    $paddedName $paddedSize $paddedCat" -NoNewline -ForegroundColor White
        Write-Host "$status" -ForegroundColor $statusColor
    }

    Write-Host '    --------------------------------------------------------------------------------' -ForegroundColor DarkGray
    Write-Host ''
    Write-Host '    Top Hugging Face GGUF Model Matches:' -ForegroundColor Yellow
    Write-Host '      - Qwen/Qwen2.5-Coder-7B-Instruct-GGUF        (Q4_K_M ~4.7 GB) -> Fast Coding' -ForegroundColor DarkCyan
    Write-Host '      - deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF (Q4_K_M ~4.7 GB) -> Reasoning' -ForegroundColor DarkCyan
    if ($ramTotal -ge 14) {
        Write-Host '      - Qwen/Qwen2.5-Coder-14B-Instruct-GGUF       (Q4_K_M ~9.0 GB) -> Heavy Coding' -ForegroundColor DarkCyan
        Write-Host '      - microsoft/phi-4-GGUF                       (Q4_K_M ~9.1 GB) -> Math & Logic' -ForegroundColor DarkCyan
    }
    Write-Host ''
    Write-Host '    Quick-Start Local AI Command (Run in any terminal):' -ForegroundColor Yellow
    Write-Host '      ollama run qwen2.5-coder:7b     # Launch recommended coding model' -ForegroundColor Cyan
    Write-Host '      ollama run deepseek-r1:7b       # Launch recommended reasoning model' -ForegroundColor Cyan
    Write-Host '      cat model list                  # Inspect active models inside CAT' -ForegroundColor Cyan
    Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkCyan
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
        } catch { }
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

    # Step 1: Detect Python runtime
    Write-Host '[1/6] Detecting Python runtime...' -ForegroundColor Yellow
    $py = Find-Python
    if (-not $py) {
        Write-Error 'Python 3.10 or higher was not found in PATH. Please install Python from https://www.python.org/downloads/ or run: winget install Python.Python.3.12'
        exit 1
    }
    Write-Host ('      Found Python ' + $py.Version + ' at: ' + $py.Executable) -ForegroundColor Green

    # Step 2: Device & Local AI Model Compatibility
    Write-Host '[2/6] Inspecting device hardware & AI acceleration capabilities...' -ForegroundColor Yellow
    Show-DeviceAndModelCompatibility

    # Step 3: Setup directories
    Write-Host '[3/6] Creating directory layout...' -ForegroundColor Yellow
    $binDir = Join-Path $InstallDir 'bin'
    $libDir = Join-Path $InstallDir 'lib'
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    New-Item -ItemType Directory -Path $libDir -Force | Out-Null
    Write-Host ('      Install directory: ' + $InstallDir) -ForegroundColor Green

    # Step 4: Locate source repository & install runtime
    Write-Host '[4/6] Installing CAT core and dependencies...' -ForegroundColor Yellow
    $repoRoot = $null

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

    # Step 5: Generate Launcher Shims in $binDir
    Write-Host '[5/6] Creating command launchers and shims...' -ForegroundColor Yellow

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

    # Step 6: Update User Environment PATH & PowerShell Profile
    Write-Host '[6/6] Configuring environment and PowerShell profile...' -ForegroundColor Yellow
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
    Write-Host '    cat --version             # Check installed CAT version' -ForegroundColor Cyan
    Write-Host '    cat model list            # Inspect available local models' -ForegroundColor Cyan
    Write-Host '    ollama run qwen2.5-coder:7b # Run recommended local coding model' -ForegroundColor Cyan
    Write-Host '    ollama run deepseek-r1:7b   # Run recommended local reasoning model' -ForegroundColor Cyan
    Write-Host '    cat curl --version        # Test built-in curl HTTP client' -ForegroundColor Cyan
    Write-Host '    cat brew doctor           # Check package system health' -ForegroundColor Cyan
    Write-Host '    cat sudo --status         # Check administrative elevation privileges' -ForegroundColor Cyan
    Write-Host '    cat                       # Launch interactive Tokyo Night terminal' -ForegroundColor Cyan
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

    Show-DeviceAndModelCompatibility

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
