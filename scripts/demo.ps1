param(
    [string]$BaseUrl = 'http://127.0.0.1:8000/api/v1',
    [string]$OutputPath = '.\postpony-orders.xlsx'
)
$ErrorActionPreference = 'Stop'
Invoke-RestMethod "$BaseUrl/health"
Invoke-RestMethod -Method Post "$BaseUrl/sync/mock"
$orders = Invoke-RestMethod "$BaseUrl/orders?shop_id=1&order_number=0001001"
if ($orders.total -ne 1) { throw 'Expected exactly one mock order in shop 1.' }
$payload = @{ order_ids = @($orders.items[0].id) } | ConvertTo-Json
$preview = Invoke-RestMethod -Method Post "$BaseUrl/exports/postpony/preview" -ContentType 'application/json' -Body $payload
if (-not $preview.valid) { throw 'Export preview failed.' }
$preview
Invoke-WebRequest -Method Post "$BaseUrl/exports/postpony" -ContentType 'application/json' -Body $payload -OutFile $OutputPath
Write-Output "Saved export: $OutputPath"
