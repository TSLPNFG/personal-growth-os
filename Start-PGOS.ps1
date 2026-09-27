param(
    [switch]$NoBrowser,
    [switch]$Demo,
    [int]$Port = 0
)
$ErrorActionPreference = 'Stop'
$pythonExecutable = $null
$pythonArguments = @()
$candidates = @()
if ($env:PGOS_PYTHON) { $candidates += @{ executable = $env:PGOS_PYTHON; arguments = @() } }
foreach ($name in @('py', 'python', 'python3')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*WindowsApps*') {
        $arguments = if ($name -eq 'py') { @('-3') } else { @() }
        $candidates += @{ executable = $command.Source; arguments = $arguments }
    }
}
if ($env:USERPROFILE) {
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) { $candidates += @{ executable = $bundled; arguments = @() } }
}
foreach ($candidate in $candidates) {
    try {
        $candidateArguments = $candidate.arguments
        & $candidate.executable @candidateArguments -B -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonExecutable = $candidate.executable
            $pythonArguments = $candidate.arguments
            break
        }
    } catch { continue }
}
if (-not $pythonExecutable) { throw 'Python 3.10+ is required. Install Python or set PGOS_PYTHON to its executable.' }
$appArguments = @('-B', '-m', 'app.server', '--port', $Port)
if ($NoBrowser) { $appArguments += '--no-browser' }
if ($Demo) { $appArguments += '--demo' }
Push-Location -LiteralPath $PSScriptRoot
try { & $pythonExecutable @pythonArguments @appArguments; exit $LASTEXITCODE }
finally { Pop-Location }
