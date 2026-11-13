param([ValidateSet('backend','frontend')][string]$Service='backend')
. "$PSScriptRoot/common.ps1"
Set-Location -LiteralPath $script:TalentRoot
$port = if ($Service -eq 'backend') { 8000 } else { 5173 }
if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $port is already in use. No existing process was stopped."
}
if ($Service -eq 'backend') {
    Invoke-TalentUv run --project backend uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
} else {
    Push-Location -LiteralPath frontend
    try { npm.cmd run dev -- --host 127.0.0.1 --port 5173; Assert-TalentExit } finally { Pop-Location }
}
