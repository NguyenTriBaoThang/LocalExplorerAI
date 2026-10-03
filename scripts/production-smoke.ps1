param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")
foreach ($path in @("/health", "/ready")) {
    $response = Invoke-WebRequest -Uri "$base$path" -TimeoutSec 15
    if ($response.StatusCode -ne 200) { throw "$path returned HTTP $($response.StatusCode)" }
    Write-Output "$path OK"
}

# Requires PowerShell 7 for SkipHttpErrorCheck.
$guestResponse = Invoke-WebRequest -Uri "$base/api/ops/status" -SkipHttpErrorCheck -TimeoutSec 15
if ($guestResponse.StatusCode -notin @(401, 403)) {
    throw "Unauthenticated operations endpoint should return 401/403, got $($guestResponse.StatusCode)."
}
Write-Output "Operations endpoint rejects unauthenticated access"

if (-not [string]::IsNullOrWhiteSpace($env:LOCAL_EXPLORER_ADMIN_KEY)) {
    $headers = @{ "X-Admin-Key" = $env:LOCAL_EXPLORER_ADMIN_KEY }
    $ops = Invoke-RestMethod -Uri "$base/api/ops/status" -Headers $headers -TimeoutSec 15
    if ($null -eq $ops.notifications -or $null -eq $ops.worker) { throw "Operations status response is missing health fields." }
    Write-Output "Authenticated operations status OK"
} else {
    Write-Output "Set LOCAL_EXPLORER_ADMIN_KEY to verify the authenticated operations view."
}
