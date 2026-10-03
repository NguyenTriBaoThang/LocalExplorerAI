param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
foreach ($name in @("PGHOST", "PGDATABASE", "PGUSER")) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Set $name before running the backup. Keep credentials in environment variables, not command arguments."
    }
}
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) { throw "pg_dump is not installed or not on PATH." }
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssZ")
$backupPath = Join-Path $resolvedOutput ("local-explorer-{0}-{1}.dump" -f $env:PGDATABASE, $stamp)
if (Test-Path -LiteralPath $backupPath) { throw "Refusing to overwrite existing backup: $backupPath" }
$partialPath = "$backupPath.partial"
& pg_dump --format=custom --no-owner --no-acl --file $partialPath
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE; partial file retained at $partialPath" }
Move-Item -LiteralPath $partialPath -Destination $backupPath
Write-Output "Backup created: $backupPath"
