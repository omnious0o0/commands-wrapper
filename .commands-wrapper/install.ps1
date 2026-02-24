$ErrorActionPreference = "Stop"

function Invoke-Python {
    param([string[]]$Args)

    $pyExitCode = $null
    $pythonExitCode = $null

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Args
        $pyExitCode = $LASTEXITCODE
        if ($pyExitCode -eq 0) {
            return
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Args
        $pythonExitCode = $LASTEXITCODE
        if ($pythonExitCode -eq 0) {
            return
        }
    }

    if ($pyExitCode -ne $null -and $pythonExitCode -ne $null) {
        throw "Both 'py -3' (exit $pyExitCode) and 'python' (exit $pythonExitCode) failed."
    }
    if ($pyExitCode -ne $null) {
        throw "'py -3' failed with exit code $pyExitCode."
    }
    if ($pythonExitCode -ne $null) {
        throw "'python' failed with exit code $pythonExitCode."
    }

    throw "Python 3 was not found in PATH."
}

function Get-PythonScriptsDir {
    $code = @'
import os
import site
import sys
import sysconfig

in_venv = getattr(sys, "base_prefix", sys.prefix) != sys.prefix
scripts = None
if in_venv:
    scripts = sysconfig.get_path("scripts")
else:
    scheme = f"{os.name}_user"
    if scheme in sysconfig.get_scheme_names():
        scripts = sysconfig.get_path("scripts", scheme=scheme)

if not scripts:
    scripts = os.path.join(site.USER_BASE or os.path.expanduser("~"), "bin")

print(os.path.abspath(scripts))
'@

    $candidates = @(
        @{ exe = "py"; args = @("-3") },
        @{ exe = "python"; args = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.exe -ErrorAction SilentlyContinue)) {
            continue
        }

        $output = & $candidate.exe @($candidate.args + @("-c", $code)) 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            return ($output | Select-Object -Last 1).ToString().Trim()
        }
    }

    return $null
}

function Resolve-WrapperSyncCommand {
    param([string]$ScriptsDir)

    if (-not $ScriptsDir) {
        return $null
    }

    $candidates = @(
        "commands-wrapper.exe",
        "commands-wrapper",
        "commands-wrapper.cmd",
        "commands-wrapper.ps1"
    )

    foreach ($candidate in $candidates) {
        $path = Join-Path $ScriptsDir $candidate
        if (Test-Path $path) {
            return $path
        }
    }

    return $null
}

function Test-CommandsWrapperSourceRoot {
    param([string]$Root)

    if (-not $Root) {
        return $false
    }

    $pyproject = Join-Path $Root "pyproject.toml"
    $cliPath = Join-Path (Join-Path $Root ".commands-wrapper") "commands-wrapper"

    return (Test-Path $pyproject) -and (Test-Path $cliPath)
}

$repoRoot = $null
if ($MyInvocation.MyCommand.Path) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if ($scriptDir) {
        $repoRoot = Split-Path -Parent $scriptDir
    }
}

$cwdRoot = (Get-Location).Path
$repoSourceRoot = $null
if (Test-CommandsWrapperSourceRoot -Root $repoRoot) {
    $repoSourceRoot = $repoRoot
}
$cwdSourceRoot = $null
if (Test-CommandsWrapperSourceRoot -Root $cwdRoot) {
    $cwdSourceRoot = $cwdRoot
}
$sourceUrl = if ($env:COMMANDS_WRAPPER_SOURCE_URL) {
    $env:COMMANDS_WRAPPER_SOURCE_URL
} else {
    "https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz"
}
$sourceSha256 = if ($env:COMMANDS_WRAPPER_SOURCE_SHA256) {
    $env:COMMANDS_WRAPPER_SOURCE_SHA256.Trim().ToLowerInvariant()
} else {
    ""
}

if ($sourceSha256 -and $sourceSha256 -notmatch '^[0-9a-f]{64}$') {
    throw "invalid COMMANDS_WRAPPER_SOURCE_SHA256 value"
}

if ($repoSourceRoot) {
    Invoke-Python @("-m", "pip", "install", $repoSourceRoot)
} elseif ($cwdSourceRoot) {
    Invoke-Python @("-m", "pip", "install", $cwdSourceRoot)
} else {
    if ($sourceSha256) {
        $tempArchive = Join-Path ([System.IO.Path]::GetTempPath()) ("commands-wrapper-" + [guid]::NewGuid().ToString() + ".tar.gz")
        try {
            Invoke-WebRequest -Uri $sourceUrl -OutFile $tempArchive
            $actualSha256 = (Get-FileHash -Path $tempArchive -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualSha256 -ne $sourceSha256) {
                throw "source archive checksum mismatch"
            }

            Invoke-Python @("-m", "pip", "install", $tempArchive)
        }
        finally {
            if (Test-Path $tempArchive) {
                Remove-Item $tempArchive -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Invoke-Python @("-m", "pip", "install", $sourceUrl)
    }
}

$hasYaml = (Test-Path "commands.yaml") -or (Test-Path "commands.yml")
if (-not $hasYaml) {
@'
# command-name:
#   description: "What this command does"
#   steps 60:
#     - command: "shell command here"
#     - send: "text to type into process"
#     - press_key: "enter"
#     - wait: "2"
'@ | Out-File -Encoding utf8 "commands.yaml"
}

$syncWarning = "Installed, but wrapper sync needs a new shell session."
$scriptsDir = Get-PythonScriptsDir
$syncCommand = Resolve-WrapperSyncCommand -ScriptsDir $scriptsDir

if ($syncCommand) {
    try {
        & $syncCommand sync | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host $syncWarning -ForegroundColor Yellow
        }
    } catch {
        Write-Host $syncWarning -ForegroundColor Yellow
    }
} else {
    Write-Host $syncWarning -ForegroundColor Yellow
}

Write-Host "commands-wrapper installed." -ForegroundColor Green
Write-Host "Run 'commands-wrapper --help' to get started." -ForegroundColor Gray
