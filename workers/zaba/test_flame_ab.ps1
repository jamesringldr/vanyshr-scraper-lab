# A/B: direct curl vs FlameProxies curl (same UA/headers)
# Run on serv-01: powershell -File C:\Users\scraper\zaba-scraper\test_flame_ab.ps1
$ErrorActionPreference = "Continue"
$envPath = "C:\Users\scraper\zaba-scraper\.env"
$lines = Get-Content $envPath
$fpKey = ($lines | Where-Object { $_ -match '^FLAMEPROXIES_API_KEY=' }) -replace '^FLAMEPROXIES_API_KEY=', ''
$pkg = ($lines | Where-Object { $_ -match '^FLAMEPROXIES_PACKAGE_ID=' }) -replace '^FLAMEPROXIES_PACKAGE_ID=', ''
if (-not $pkg) { $pkg = "2549" }
if (-not $fpKey) { Write-Host "NO_FLAME_KEY"; exit 1 }

Write-Host "flame_key_len=$($fpKey.Length) package_id=$pkg"

$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
$url = "https://www.zabasearch.com/people/james-oehring/missouri/cameron"

Write-Host "=== CONTROL direct (no proxy) ==="
$out1 = & curl.exe -sS -L -A $ua -o "$env:TEMP\zaba_direct.html" -w "status=%{http_code} size=%{size_download}" $url 2>&1
Write-Host $out1
$personDirect = 0
if (Test-Path "$env:TEMP\zaba_direct.html") {
  $m = Select-String -Path "$env:TEMP\zaba_direct.html" -Pattern 'class="person"' -AllMatches -ErrorAction SilentlyContinue
  if ($m) { $personDirect = ($m | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum).Sum }
}
Write-Host "person_divs=$personDirect"

Write-Host "=== generating FlameProxies ==="
$genBody = @{ package_id = [int]$pkg; country = "US" } | ConvertTo-Json
$headers = @{ Authorization = "Bearer $fpKey"; "Content-Type" = "application/json" }
try {
  $gen = Invoke-RestMethod -Uri "https://flameproxies.com/api/customer/proxies/generate" -Method POST -Headers $headers -Body $genBody -TimeoutSec 30
} catch {
  Write-Host "generate_failed: $($_.Exception.Message)"
  exit 2
}
$proxies = @($gen.proxies)
Write-Host "proxies_returned=$($proxies.Count)"

$max = [Math]::Min(5, $proxies.Count)
$ok = 0
$fail = 0
for ($i = 0; $i -lt $max; $i++) {
  $raw = $proxies[$i]
  $parts = $raw -split ":"
  if ($parts.Count -lt 4) { Write-Host "attempt $($i+1): bad format"; $fail++; continue }
  $hostName = $parts[0]
  $port = $parts[1]
  $user = $parts[2]
  $pass = ($parts[3..($parts.Count - 1)] -join ":")
  $proxyUrl = "http://${user}:${pass}@${hostName}:${port}"
  Write-Host "=== Flame attempt $($i+1)/$max host=${hostName}:${port} ==="
  $tmp = "$env:TEMP\zaba_flame_$i.html"
  $out = & curl.exe -sS -L --proxy $proxyUrl -A $ua -o $tmp -w "status=%{http_code} size=%{size_download}" --max-time 45 $url 2>&1
  Write-Host $out
  $n = 0
  if (Test-Path $tmp) {
    $m = Select-String -Path $tmp -Pattern 'class="person"' -AllMatches -ErrorAction SilentlyContinue
    if ($m) { $n = ($m | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum).Sum }
  }
  Write-Host "person_divs=$n"
  if ($out -match 'status=200' -and $n -gt 0) { $ok++ } else { $fail++ }
}

Write-Host "=== SUMMARY ok=$ok fail=$fail of $max flame attempts; direct person_divs=$personDirect ==="
