[CmdletBinding()]
param()

# End-to-end live verification: direct and MCP calls to both Foundry models, then Cursor CLI -> MCP -> Foundry.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$onWindows = $IsWindows -or $env:OS -eq 'Windows_NT'
$python = if ($onWindows) { [IO.Path]::Combine($root, '.venv', 'Scripts', 'python.exe') } else { [IO.Path]::Combine($root, '.venv', 'bin', 'python') }
if (-not (Test-Path $python)) { throw 'Run ./scripts/Setup.ps1 first.' }
$smoke = Join-Path $PSScriptRoot 'smoke_test.py'

foreach ($transport in 'direct', 'mcp') {
    foreach ($model in 'openai', 'claude') {
        & $python $smoke --transport $transport --model $model
        if ($LASTEXITCODE -ne 0) { throw "Smoke test failed: transport=$transport model=$model." }
    }
}

Push-Location ([IO.Path]::Combine($root, 'demo'))
try {
    & agent mcp enable foundry-models
    if ($LASTEXITCODE -ne 0) { throw 'Approving the foundry-models MCP server failed.' }
    & agent mcp list-tools foundry-models
    if ($LASTEXITCODE -ne 0) { throw 'Cursor could not load the foundry-models MCP server.' }
    & $python (Join-Path $PSScriptRoot 'verify_cursor.py')
    if ($LASTEXITCODE -ne 0) { throw 'Cursor-to-Foundry verification failed.' }
} finally {
    Pop-Location
}
