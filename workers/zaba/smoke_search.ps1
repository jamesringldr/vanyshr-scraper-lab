# Smoke test Zaba search on loopback (prints summary only; never echoes token)
$ErrorActionPreference = 'Stop'
$envPath = 'C:\Users\scraper\zaba-scraper\.env'
$token = (
  Get-Content $envPath |
  Where-Object { $_ -match '^\s*ZABA_SERVICE_TOKEN\s*=' } |
  ForEach-Object { ($_ -split '=', 2)[1].Trim() }
) | Select-Object -First 1
if (-not $token) { throw 'ZABA_SERVICE_TOKEN missing from .env' }

$body = @{ first_name = 'James'; last_name = 'Oehring'; city = 'Cameron'; state = 'MO' } | ConvertTo-Json
$headers = @{
  Authorization  = "Bearer $token"
  'Content-Type' = 'application/json'
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
  $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8788/v1/zaba/search' -Method POST -Headers $headers -Body $body -TimeoutSec 180
  $sw.Stop()
  Write-Output ("elapsed_ms=" + $sw.ElapsedMilliseconds)
  Write-Output ("success=" + $r.success)
  $count = 0
  if ($null -ne $r.profiles) { $count = @($r.profiles).Count }
  Write-Output ("profile_count=" + $count)
  if ($count -gt 0) {
    $p = $r.profiles[0]
    Write-Output ("name=" + $p.name + " age=" + $p.age)
  }
  if ($r.error) { Write-Output ("error=" + $r.error) }
  if ($r.message) { Write-Output ("message=" + $r.message) }
  # surface any fetch-path fields without dumping phones
  $props = $r.PSObject.Properties.Name -join ','
  Write-Output ("response_keys=" + $props)
} catch {
  $sw.Stop()
  Write-Output ("elapsed_ms=" + $sw.ElapsedMilliseconds)
  Write-Output ("HTTP_ERR=" + $_.Exception.Message)
  if ($_.ErrorDetails.Message) { Write-Output $_.ErrorDetails.Message }
  exit 1
}
