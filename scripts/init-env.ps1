$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectDirectory '.env'
if (Test-Path -LiteralPath $envFile) {
    Write-Output '.env already exists; nothing changed.'
    exit 0
}

function New-RandomHex([int]$Length) {
    $buffer = New-Object byte[] $Length
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($buffer) } finally { $generator.Dispose() }
    return [System.BitConverter]::ToString($buffer).Replace('-', '').ToLowerInvariant()
}

$databaseSecret = New-RandomHex 24
$tokenSecret = New-RandomHex 48
$content = @"
POSTGRES_DB=practicum
POSTGRES_USER=practicum
POSTGRES_PASSWORD=$databaseSecret
JWT_SECRET=$tokenSecret
ACCESS_TOKEN_EXPIRE_MINUTES=60
API_PORT=8010
"@
[System.IO.File]::WriteAllText($envFile, $content + [Environment]::NewLine)
Write-Output 'Created .env with random secrets.'

