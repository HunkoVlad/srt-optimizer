param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),

    [string]$CredentialsFile = "config\gmail_oauth_client.json",

    [string]$TokenFile = ".local\gmail_token.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$recoveryMessage = "Gmail OAuth token is expired or revoked. Rename/delete .local/gmail_token.json, rerun the script manually, and complete Google authorization in the browser. For unattended weekly sending, move the Google OAuth app from Testing to In production in Google Cloud Console."

$resolvedProjectRoot = Resolve-Path -LiteralPath $ProjectRoot
$credentialsPath = Join-Path $resolvedProjectRoot $CredentialsFile
$tokenPath = Join-Path $resolvedProjectRoot $TokenFile
$pythonExe = Join-Path $resolvedProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

Write-Host "Gmail OAuth status check"
Write-Host "Project root: $resolvedProjectRoot"
Write-Host "Credentials file: $credentialsPath"
Write-Host "Token file: $tokenPath"
Write-Host "Safety: this check never sends email."

if (-not (Test-Path $credentialsPath)) {
    Write-Error "Missing Gmail OAuth client credentials: $credentialsPath"
    exit 2
}

if (-not (Test-Path $tokenPath)) {
    Write-Warning "Missing Gmail OAuth token: $tokenPath"
    Write-Host $recoveryMessage
    exit 3
}

Push-Location $resolvedProjectRoot
try {
    $env:PYTHONPATH = "src"
    & $pythonExe -c "import googleapiclient.discovery; import google.auth; import google_auth_oauthlib.flow" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Missing Gmail API dependencies. Install them with: pip install google-api-python-client google-auth google-auth-oauthlib"
        exit 1
    }

    & $pythonExe -m marketing.stayfi_gmail_send `
        --run-date (Get-Date -Format "yyyy-MM-dd") `
        --credentials-file $CredentialsFile `
        --token-file $TokenFile `
        --validate-oauth-only 2>&1 | ForEach-Object {
            Write-Host $_
        }
    $validationExitCode = $LASTEXITCODE
    if ($null -eq $validationExitCode) {
        $validationExitCode = 0
    }
    if ($validationExitCode -eq 3) {
        Write-Host $recoveryMessage
        exit 3
    }
    if ($validationExitCode -ne 0) {
        Write-Error "Gmail OAuth validation failed with exit code $validationExitCode."
        exit $validationExitCode
    }

    Write-Host "Gmail OAuth token appears usable. No emails were sent."
}
finally {
    Pop-Location
}

exit 0
