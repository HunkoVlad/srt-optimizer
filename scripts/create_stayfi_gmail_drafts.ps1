param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate,

    [string]$CredentialsFile = "config\gmail_oauth_client.json",

    [string]$TokenFile = ".local\gmail_token.json",

    [string]$SenderEmail = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($RunDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "RunDate must use YYYY-MM-DD format."
    exit 1
}

$scriptRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $scriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "src"
    & $pythonExe -c "import googleapiclient.discovery; import google.auth; import google_auth_oauthlib.flow" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Missing Gmail API dependencies. Install them with: pip install google-api-python-client google-auth google-auth-oauthlib"
        exit 1
    }

    $argsList = @(
        "-m", "marketing.stayfi_gmail_drafts",
        "--run-date", $RunDate,
        "--credentials-file", $CredentialsFile,
        "--token-file", $TokenFile
    )
    if ($SenderEmail) {
        $argsList += @("--sender-email", $SenderEmail)
    }
    & $pythonExe @argsList
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

exit 0
