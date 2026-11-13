param([string]$OutputName = ('talentgo-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump'))
. "$PSScriptRoot/common.ps1"
Set-Location -LiteralPath $script:TalentRoot
if ($OutputName -notmatch '^[A-Za-z0-9_.-]+\.dump$') { throw 'Provide a filename only, ending in .dump.' }
New-Item -ItemType Directory -Path database/backups -Force | Out-Null
$target = Join-Path $script:TalentRoot "database/backups/$OutputName"
if (Test-Path -LiteralPath $target) { throw 'Refusing to overwrite an existing backup.' }
$temporary = '/tmp/' + [guid]::NewGuid().ToString('N') + '.dump'
# Credentials remain inside the configured container; shell arguments contain no password.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p 6543 -Fc -f "$1"' -- $temporary
Assert-TalentExit
$container = docker compose ps -q db
Assert-TalentExit
docker cp "${container}:$temporary" $target
Assert-TalentExit
docker compose exec -T db rm -- $temporary
Assert-TalentExit
Write-Host "Backup saved under ignored database/backups/$OutputName"
