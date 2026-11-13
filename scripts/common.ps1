$ErrorActionPreference = 'Stop'
$script:TalentRoot = Split-Path -Parent $PSScriptRoot

function Invoke-TalentUv {
    $bootstrapUv = Join-Path $script:TalentRoot '.tools/bootstrap/Scripts/uv.exe'
    if (Test-Path -LiteralPath $bootstrapUv) {
        & $bootstrapUv @args
    } elseif (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv @args
    } else {
        throw 'Run scripts/setup.ps1 first to install the local uv bootstrap.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'uv command failed.' }
}

function Assert-TalentCommand {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "Missing command: $Name" }
}

function Assert-TalentExit {
    if ($LASTEXITCODE -ne 0) { throw 'Previous command failed. Check its output.' }
}
