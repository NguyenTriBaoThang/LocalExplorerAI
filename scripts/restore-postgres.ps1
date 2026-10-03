param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [Parameter(Mandatory = $true)]
    [string]$TargetDatabase
)

$ErrorActionPreference = "Stop"
foreach ($name in @("PGHOST", "PGUSER")) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Set $name before running restore. Keep credentials in environment variables, not command arguments."
    }
}
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) { throw "pg_restore is not installed or not on PATH." }
$resolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
if ([System.IO.Path]::GetExtension($resolvedBackup) -ne ".dump") { throw "Expected a pg_dump custom-format .dump file." }
& pg_restore --list $resolvedBackup | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Backup archive validation failed; target database was not modified." }
$confirmation = Read-Host "This overwrites objects in '$TargetDatabase'. Type the exact database name to continue"
if ($confirmation -cne $TargetDatabase) { throw "Restore cancelled; confirmation did not match." }
$oldDatabase = $env:PGDATABASE
try {
    $env:PGDATABASE = $TargetDatabase
    & pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error $resolvedBackup
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE." }
    Write-Output "Restore completed to database '$TargetDatabase'. Verify migrations and application readiness before switching traffic."
} finally {
    $env:PGDATABASE = $oldDatabase
}
