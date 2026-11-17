[CmdletBinding()]
param([switch]$UpdateLock)

# Creates .venv, installs pinned dependencies and writes demo/.cursor/mcp.json for this machine.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$onWindows = $IsWindows -or $env:OS -eq 'Windows_NT'
$venv = Join-Path $root '.venv'
$python = if ($onWindows) { [IO.Path]::Combine($venv, 'Scripts', 'python.exe') } else { [IO.Path]::Combine($venv, 'bin', 'python') }
if (-not (Test-Path $python)) {
    $basePython = if ($onWindows) { 'python' } else { 'python3' }
    & $basePython -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Python virtual environment failed.' }
}
$lock = Join-Path $root 'requirements.lock.txt'
$requirements = if ($UpdateLock -or -not (Test-Path $lock)) { Join-Path $root 'requirements.txt' } else { $lock }
& $python -m pip install --quiet --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Installing dependencies failed.' }
if ($UpdateLock) {
    $windowsOnly = @('colorama', 'pywin32')
    $freeze = & $python -m pip freeze
    if ($LASTEXITCODE -ne 0) { throw 'Recording installed dependencies failed.' }
    $freeze | ForEach-Object {
        if ($windowsOnly -contains ($_ -split '==')[0].ToLowerInvariant()) { "$_; sys_platform == ""win32""" } else { $_ }
    } | Set-Content $lock -Encoding utf8
}
$mcpConfig = @{
    mcpServers = @{
        'foundry-models' = @{
            type = 'stdio'
            command = $python
            args = @([IO.Path]::Combine($root, 'scripts', 'foundry_mcp.py'))
        }
    }
}
$mcpConfig | ConvertTo-Json -Depth 6 | Set-Content ([IO.Path]::Combine($root, 'demo', '.cursor', 'mcp.json')) -Encoding utf8
if (-not (Test-Path ([IO.Path]::Combine($root, 'config', 'foundry.json')))) {
    Write-Warning 'config/foundry.json is missing. Copy config/foundry.example.json and fill in your values.'
}
Write-Output 'Python environment is ready and demo/.cursor/mcp.json was written.'
