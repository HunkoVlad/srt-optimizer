param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate
)

$ErrorActionPreference = "Stop"

if ($RunDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "RunDate must use YYYY-MM-DD format."
    exit 1
}

$env:PYTHONPATH = "src"

python -m pricelabs.transform.run --config config\pricelabs.single-listing.example.toml --run-date $RunDate
if ($LASTEXITCODE -ne 0) {
    Write-Error "PriceLabs V1 transform failed."
    exit $LASTEXITCODE
}

Write-Host "PriceLabs V1 transform complete."
Write-Host "Expected outputs:"
Write-Host "  standardized/future_daily_pricing_$RunDate.csv"
Write-Host "  manifest.json"
