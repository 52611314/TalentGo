. "$PSScriptRoot/common.ps1"
Set-Location -LiteralPath $script:TalentRoot
Push-Location -LiteralPath backend
try { Invoke-TalentUv run --project . python -m pytest } finally { Pop-Location }
Invoke-TalentUv run --project backend alembic -c backend/alembic.ini check
Push-Location -LiteralPath frontend
try { npm.cmd run build; Assert-TalentExit } finally { Pop-Location }
Write-Host 'M3 engineering checks passed. Browser checks are recorded separately in the stage report.'
