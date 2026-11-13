. "$PSScriptRoot/common.ps1"
Set-Location -LiteralPath $script:TalentRoot
Assert-TalentCommand python
Assert-TalentCommand npm.cmd
Assert-TalentCommand docker
python scripts/configure_local.py
Assert-TalentExit
$bootstrapPython = Join-Path $script:TalentRoot '.tools/bootstrap/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $bootstrapPython)) {
    python -m venv .tools/bootstrap
    Assert-TalentExit
}
if (-not (Test-Path -LiteralPath (Join-Path $script:TalentRoot '.tools/bootstrap/Scripts/uv.exe'))) {
    & $bootstrapPython -m pip install uv
    Assert-TalentExit
}
Invoke-TalentUv sync --project backend --frozen
Push-Location -LiteralPath frontend
try { npm.cmd ci; Assert-TalentExit } finally { Pop-Location }
docker compose up -d --wait db
Assert-TalentExit
Invoke-TalentUv run --project backend alembic -c backend/alembic.ini upgrade head
Invoke-TalentUv run --project backend python scripts/create_test_db.py
Write-Host 'TalentGo setup complete. Start scripts/start-dev.ps1 in one terminal and scripts/start-dev.ps1 -Service frontend in another.'
