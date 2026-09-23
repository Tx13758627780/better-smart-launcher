param(
    [string]$Directory = (Get-Location),
    [string]$Output = 'Smart-Launcher-6.6-021-cleaned-pinyin-search.apk'
)

$parts = Get-ChildItem -LiteralPath $Directory -Filter "$Output.b64.part-*" | Sort-Object Name
if ($parts.Count -eq 0) { throw 'No APK base64 parts found.' }
$base64 = ($parts | ForEach-Object { Get-Content -Raw -LiteralPath $_.FullName }).Trim()
[IO.File]::WriteAllBytes((Join-Path $Directory $Output), [Convert]::FromBase64String($base64))
Write-Output "Wrote $(Join-Path $Directory $Output)"
