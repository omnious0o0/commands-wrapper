$ErrorActionPreference = "Stop"

$PrimaryWrapper = "commands-wrapper"
$ShortAlias = "cw"

$StepTotal = 9
$StepCurrent = 0

function Invoke-RichUi {
    param(
        [string]$Mode,
        [string]$Message = "",
        [int]$Current = 0,
        [int]$Total = 0,
        [string]$Version = ""
    )

    $code = @'
import sys

from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
import pyfiglet

mode = sys.argv[1]
message = sys.argv[2]
current = int(sys.argv[3])
total = int(sys.argv[4])
version = sys.argv[5]

console = Console()

if mode == "logo":
    logo = pyfiglet.figlet_format("commands-wrapper", font="ansi_shadow")
    console.print(Panel(f"[bold cyan]{logo}[/bold cyan]", border_style="cyan", padding=(0, 2)))
elif mode == "step":
    console.print(f"[cyan][{current}/{total}][/cyan] [bold]{message}[/bold]")
    console.print(ProgressBar(total=total, completed=current, width=36, complete_style="cyan"))
elif mode == "ok":
    console.print("[green]✓[/green] [green]Done[/green]")
elif mode == "warn":
    console.print(f"[yellow]⚠[/yellow] [yellow]{message}[/yellow]")
elif mode == "error":
    console.print(f"[red]✗[/red] [red]{message}[/red]")
elif mode == "info":
    console.print(f"[cyan]{message}[/cyan]")
elif mode == "success-panel":
    body = "\n".join([
        f"[green]✓ commands-wrapper {version} installed[/green]",
        "",
        "[cyan]cw[/cyan]                 launch",
        "[cyan]cw --update[/cyan]        update",
        "[cyan]cw --help[/cyan]          all commands",
    ])
    console.print(Panel(body, border_style="green", padding=(1, 2)))
'@

    $args = @("-c", $code, $Mode, $Message, $Current.ToString(), $Total.ToString(), $Version)
    $uiOutput = $null
    $uiExitCode = $null
    $isExpectedOutput = {
        param(
            [string]$ModeValue,
            [string]$OutputText,
            [string]$Probe
        )

        switch ($ModeValue) {
            "step" { return $OutputText.Contains($Probe) }
            "warn" { return $OutputText.Contains($Probe) }
            "error" { return $OutputText.Contains($Probe) }
            "info" { return $OutputText.Contains($Probe) }
            "detail" { return $OutputText.Contains($Probe) }
            "ok" { return $OutputText.Contains("Done") -or $OutputText.Contains("✓") }
            "success-panel" { return $OutputText.Contains("cw --update") }
            default { return $OutputText.Length -gt 0 }
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        $uiOutput = & py -3 @args 2>$null
        $uiExitCode = $LASTEXITCODE
        if ($uiExitCode -eq 0 -and $uiOutput) {
            $outputText = ($uiOutput -join "`n")
            if (& $isExpectedOutput $Mode $outputText $Message) {
                $uiOutput | ForEach-Object { Write-Host $_ }
                return
            }
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $uiOutput = & python @args 2>$null
        $uiExitCode = $LASTEXITCODE
        if ($uiExitCode -eq 0 -and $uiOutput) {
            $outputText = ($uiOutput -join "`n")
            if (& $isExpectedOutput $Mode $outputText $Message) {
                $uiOutput | ForEach-Object { Write-Host $_ }
                return
            }
        }
    }

    switch ($Mode) {
        "logo" {
            Write-Host "commands-wrapper" -ForegroundColor Cyan
        }
        "step" {
            Write-Host "[$Current/$Total] $Message" -ForegroundColor Cyan
        }
        "ok" {
            Write-Host "Done" -ForegroundColor Green
        }
        "warn" {
            Write-Host "WARN: $Message" -ForegroundColor Yellow
        }
        "error" {
            Write-Host "ERROR: $Message" -ForegroundColor Red
        }
        "info" {
            Write-Host $Message -ForegroundColor Cyan
        }
        "success-panel" {
            Write-Host "commands-wrapper is installed and self-healed." -ForegroundColor Green
            Write-Host "Use 'cw' or 'commands-wrapper' from any directory." -ForegroundColor Gray
        }
        default {
            if ($Message) {
                Write-Host $Message
            }
        }
    }
}

function Ensure-UiRuntime {
    $checkCode = @'
import importlib.util
import sys

missing = [pkg for pkg in ("rich", "pyfiglet") if importlib.util.find_spec(pkg) is None]
raise SystemExit(1 if missing else 0)
'@

    $checkExit = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -c $checkCode | Out-Null
        $checkExit = $LASTEXITCODE
        if ($checkExit -eq 0) {
            return
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c $checkCode | Out-Null
        $checkExit = $LASTEXITCODE
        if ($checkExit -eq 0) {
            return
        }
    }

    try {
        Invoke-Python @("-m", "pip", "install", "rich", "pyfiglet", "--break-system-packages")
        return
    } catch {
        Invoke-Python @("-m", "pip", "install", "rich", "pyfiglet")
    }
}

function Write-Logo {
    Invoke-RichUi -Mode "logo"
}

function Start-Step {
    param([string]$Message)

    $script:StepCurrent += 1
    Invoke-RichUi -Mode "step" -Message $Message -Current $script:StepCurrent -Total $script:StepTotal
}

function Complete-Step {
    Invoke-RichUi -Mode "ok"
}

function Warn-Step {
    param([string]$Message)
    Invoke-RichUi -Mode "warn" -Message $Message
}

function Fail-Install {
    param([string]$Message)
    Invoke-RichUi -Mode "error" -Message $Message
    throw $Message
}

function Invoke-Python {
    param([string[]]$Args)

    $pyExitCode = $null
    $pythonExitCode = $null
    $errors = @()

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Args
        $pyExitCode = $LASTEXITCODE
        if ($pyExitCode -eq 0) {
            return
        }
        $errors += "'py -3' failed with exit code $pyExitCode"
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Args
        $pythonExitCode = $LASTEXITCODE
        if ($pythonExitCode -eq 0) {
            return
        }
        $errors += "'python' failed with exit code $pythonExitCode"
    }

    if ($errors.Count -gt 0) {
        throw ($errors -join "; ")
    }

    throw "Python 3 was not found in PATH."
}

function Invoke-PythonCapture {
    param([string[]]$Args)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        $output = & py -3 @Args 2>$null
        if ($LASTEXITCODE -eq 0) {
            return ($output | Select-Object -Last 1).ToString().Trim()
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $output = & python @Args 2>$null
        if ($LASTEXITCODE -eq 0) {
            return ($output | Select-Object -Last 1).ToString().Trim()
        }
    }

    return $null
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

    return Invoke-PythonCapture @("-c", $code)
}

function Get-UserConfigDir {
    $code = @'
import os

if os.name == "nt":
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    print(os.path.join(base, "commands-wrapper"))
else:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        print(os.path.join(os.path.expanduser(xdg), "commands-wrapper"))
    else:
        print(os.path.join(os.path.expanduser("~"), ".config", "commands-wrapper"))
'@

    return Invoke-PythonCapture @("-c", $code)
}

function Get-InstalledPackageVersion {
    $code = @'
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pip", "show", "commands-wrapper"],
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(0)

for line in result.stdout.splitlines():
    if line.startswith("Version:"):
        print(line.split(":", 1)[1].strip())
        break
'@

    return Invoke-PythonCapture @("-c", $code)
}

function Get-ProjectVersionFromPyproject {
    param([string]$RootPath)

    if (-not $RootPath) {
        return $null
    }

    $pyprojectPath = Join-Path $RootPath "pyproject.toml"
    if (-not (Test-Path $pyprojectPath)) {
        return $null
    }

    $code = @'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(0)

text = path.read_text(encoding="utf-8", errors="replace")
version = None

try:
    import tomllib
except Exception:
    tomllib = None

if tomllib is not None:
    try:
        data = tomllib.loads(text)
    except Exception:
        data = {}
    project = data.get("project") if isinstance(data, dict) else None
    if isinstance(project, dict):
        value = project.get("version")
        if isinstance(value, str) and value.strip():
            version = value.strip()

if version is None:
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        match = re.match(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', stripped)
        if match:
            version = match.group(1).strip()
            break

if version:
    print(version)
'@

    return Invoke-PythonCapture @("-c", $code, $pyprojectPath)
}

function Compare-PackageVersion {
    param(
        [string]$InstalledVersion,
        [string]$TargetVersion
    )

    if (-not $InstalledVersion -or -not $TargetVersion) {
        return "unknown"
    }

    $code = @'
import sys

installed = sys.argv[1]
target = sys.argv[2]

try:
    from packaging.version import Version
    installed_v = Version(installed)
    target_v = Version(target)
except Exception:
    if installed == target:
        print("eq")
    else:
        print("unknown")
    raise SystemExit(0)

if installed_v == target_v:
    print("eq")
elif installed_v > target_v:
    print("gt")
else:
    print("lt")
'@

    $result = Invoke-PythonCapture @("-c", $code, $InstalledVersion, $TargetVersion)
    if (-not $result) {
        return "unknown"
    }
    return $result
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

function Normalize-PathSafe {
    param([string]$PathValue)

    if (-not $PathValue -or $PathValue.Trim() -eq "") {
        return $null
    }

    try {
        return [System.IO.Path]::GetFullPath($PathValue)
    } catch {
        return $null
    }
}

function Ensure-UserPathContains {
    param([string]$PathEntry)

    if (-not $PathEntry) {
        return
    }

    $normalizedTarget = Normalize-PathSafe -PathValue $PathEntry
    if (-not $normalizedTarget) {
        Warn-Step "Could not normalize scripts directory path '$PathEntry'; skipping persistent PATH update."
        return
    }

    $userPath = ""
    $userPathSupported = $true
    try {
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    } catch {
        $userPathSupported = $false
    }
    $segments = @()
    if ($userPath) {
        $segments = $userPath.Split(";") | Where-Object { $_ -and $_.Trim() -ne "" }
    }

    $contains = $false
    foreach ($segment in $segments) {
        $normalizedSegment = Normalize-PathSafe -PathValue $segment
        if (-not $normalizedSegment) {
            continue
        }
        if ([string]::Equals($normalizedSegment, $normalizedTarget, [System.StringComparison]::OrdinalIgnoreCase)) {
            $contains = $true
            break
        }
    }

    if ($userPathSupported -and -not $contains) {
        $updatedSegments = @($normalizedTarget) + $segments
        try {
            [Environment]::SetEnvironmentVariable("Path", ($updatedSegments -join ";"), "User")
        } catch {
            $userPathSupported = $false
        }
    }

    $sessionSegments = @()
    if ($env:PATH) {
        $sessionSegments = $env:PATH.Split(";") | Where-Object { $_ -and $_.Trim() -ne "" }
    }
    $sessionContains = $false
    foreach ($segment in $sessionSegments) {
        $normalizedSegment = Normalize-PathSafe -PathValue $segment
        if (-not $normalizedSegment) {
            continue
        }
        if ([string]::Equals($normalizedSegment, $normalizedTarget, [System.StringComparison]::OrdinalIgnoreCase)) {
            $sessionContains = $true
            break
        }
    }
    if (-not $sessionContains) {
        $env:PATH = "$normalizedTarget;$env:PATH"
    }

    if (-not $userPathSupported) {
        Warn-Step "Could not persist user PATH permanently on this host; session PATH was repaired."
    }
}

function Invoke-WrapperSyncWithRetry {
    param([string]$WrapperCommand)

    $firstSyncOutput = & $WrapperCommand sync 2>&1
    $firstExitCode = $LASTEXITCODE
    if ($firstExitCode -eq 0) {
        return
    }

    Warn-Step "Initial wrapper sync failed; retrying with diagnostics."
    $secondSyncOutput = & $WrapperCommand sync 2>&1
    $secondExitCode = $LASTEXITCODE
    if ($secondExitCode -eq 0) {
        return
    }

    if ($firstSyncOutput) {
        Write-Host "Sync attempt output:" -ForegroundColor Red
        $firstSyncOutput | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    }
    if ($secondSyncOutput) {
        Write-Host "Retry sync output:" -ForegroundColor Red
        $secondSyncOutput | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    }
    throw "automatic wrapper sync failed after retry"
}

function Assert-CommandAvailable {
    param(
        [string]$Name,
        [string]$ExpectedDir
    )

    $commandInfo = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $commandInfo) {
        throw "global access check failed: '$Name' is not discoverable in PATH"
    }

    if (-not $ExpectedDir) {
        return
    }

    $normalizedExpectedDir = Normalize-PathSafe -PathValue $ExpectedDir
    if (-not $normalizedExpectedDir) {
        return
    }

    $commandPath = $commandInfo.Source
    if (-not $commandPath) {
        $commandPath = $commandInfo.Path
    }
    $normalizedCommandPath = Normalize-PathSafe -PathValue $commandPath
    if (-not $normalizedCommandPath) {
        throw "global access check failed: '$Name' resolves to a non-file command."
    }

    $commandDir = Split-Path -Parent $normalizedCommandPath
    if (-not [string]::Equals($commandDir, $normalizedExpectedDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "global access check failed: '$Name' resolves to '$normalizedCommandPath' instead of '$normalizedExpectedDir'."
    }
}

function Ensure-GlobalConfigTemplate {
    $configDir = Get-UserConfigDir
    if (-not $configDir) {
        throw "failed to determine global config directory"
    }

    New-Item -ItemType Directory -Force -Path $configDir | Out-Null

    $yaml = Join-Path $configDir "commands.yaml"
    $yml = Join-Path $configDir "commands.yml"
    if (-not (Test-Path $yaml) -and -not (Test-Path $yml)) {
@'
# command-name:
#   description: "What this command does"
#   steps 60:
#     - command: "shell command here"
#     - send: "text to type into process"
#     - press_key: "enter"
#     - wait: "2"
'@ | Out-File -Encoding utf8 $yaml
    }
}

Ensure-UiRuntime
Write-Logo
Invoke-RichUi -Mode "info" -Message "Installing commands-wrapper"

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
    Fail-Install "invalid COMMANDS_WRAPPER_SOURCE_SHA256 value"
}

Start-Step "Checking Python and pip availability"
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail-Install "Python 3 was not found in PATH."
}
Invoke-Python @("-m", "pip", "--version")
Complete-Step

Start-Step "Preparing installation source"
$tempArchive = $null
$installTargetRoot = $null
if ($repoSourceRoot) {
    $installTarget = $repoSourceRoot
    $installTargetRoot = $repoSourceRoot
} elseif ($cwdSourceRoot) {
    $installTarget = $cwdSourceRoot
    $installTargetRoot = $cwdSourceRoot
} else {
    if ($sourceSha256) {
        $tempArchive = Join-Path ([System.IO.Path]::GetTempPath()) ("commands-wrapper-" + [guid]::NewGuid().ToString() + ".tar.gz")
        Invoke-WebRequest -Uri $sourceUrl -OutFile $tempArchive
        $actualSha256 = (Get-FileHash -Path $tempArchive -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualSha256 -ne $sourceSha256) {
            Fail-Install "source archive checksum mismatch"
        }
        $installTarget = $tempArchive
    } else {
        $installTarget = $sourceUrl
    }
}
Complete-Step

Start-Step "Installing/updating package"
$installedVersion = Get-InstalledPackageVersion
$targetVersion = Get-ProjectVersionFromPyproject -RootPath $installTargetRoot
$relation = Compare-PackageVersion -InstalledVersion $installedVersion -TargetVersion $targetVersion
if ($relation -eq "eq") {
    Warn-Step "commands-wrapper $installedVersion is already installed; skipping package reinstall."
} elseif ($relation -eq "gt") {
    Warn-Step "installed version $installedVersion is newer than source $targetVersion; skipping downgrade."
} else {
    Invoke-Python @("-m", "pip", "install", "--upgrade", $installTarget)
}
Complete-Step

if ($tempArchive -and (Test-Path $tempArchive)) {
    Remove-Item $tempArchive -Force -ErrorAction SilentlyContinue
}

Start-Step "Resolving command locations"
$scriptsDir = Get-PythonScriptsDir
if (-not $scriptsDir) {
    Fail-Install "failed to resolve Python scripts directory"
}

$syncCommand = Resolve-WrapperSyncCommand -ScriptsDir $scriptsDir
if (-not $syncCommand) {
    Fail-Install "installed binary was not found in '$scriptsDir'"
}
Complete-Step

Start-Step "Synchronizing wrapper commands"
try {
    Invoke-WrapperSyncWithRetry -WrapperCommand $syncCommand
} catch {
    Fail-Install $_.Exception.Message
}

$cwCandidates = @(
    (Join-Path $scriptsDir "cw.cmd"),
    (Join-Path $scriptsDir "cw.ps1"),
    (Join-Path $scriptsDir "cw.exe"),
    (Join-Path $scriptsDir "cw")
)
if (-not ($cwCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1)) {
    Fail-Install "wrapper sync completed but no '$ShortAlias' wrapper was generated in '$scriptsDir'"
}
Complete-Step

Start-Step "Self-healing PATH for global command access"
Ensure-UserPathContains -PathEntry $scriptsDir
Assert-CommandAvailable -Name $PrimaryWrapper -ExpectedDir $scriptsDir
Assert-CommandAvailable -Name $ShortAlias -ExpectedDir $scriptsDir
Complete-Step

Start-Step "Ensuring global command config exists"
Ensure-GlobalConfigTemplate
Complete-Step

Start-Step "Running post-install launch preview"
$isInteractive = $false
try {
    $isInteractive = -not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected
} catch {
    $isInteractive = $false
}

if ($isInteractive -and -not $env:CI) {
    & $syncCommand
    if ($LASTEXITCODE -ne 0) {
        Fail-Install "post-install launch preview failed with exit code $LASTEXITCODE"
    }
} else {
    & $syncCommand list | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail-Install "post-install verification failed: 'commands-wrapper list' exited with code $LASTEXITCODE"
    }
}
Complete-Step

Start-Step "Final health check"
& $syncCommand --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail-Install "final health check failed: 'commands-wrapper --help' exited with code $LASTEXITCODE"
}
Complete-Step

$installedAfter = Get-InstalledPackageVersion
if (-not $installedAfter) {
    $installedAfter = "installed"
}
Invoke-RichUi -Mode "success-panel" -Version $installedAfter
