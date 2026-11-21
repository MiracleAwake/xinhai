param([string]$Target='qwen2.5vl:3b')
$ErrorActionPreference='Stop'
$before = @(ollama list 2>$null | Select-String -Pattern '^[^NAME]' | ForEach-Object { $_.Line.Trim().Split(' ')[0] } | Where-Object { $_ })
Write-Host "Allowed target: $Target"
Write-Host "Existing models: $($before -join ', ')"
Write-Host 'This script only invokes one explicit ollama pull. It does not install or request other models.'
ollama pull $Target
$after = @(ollama list 2>$null | Select-String -Pattern '^[^NAME]' | ForEach-Object { $_.Line.Trim().Split(' ')[0] } | Where-Object { $_ })
$unexpected = @($after | Where-Object { $_ -ne $Target -and $_ -notin $before })
if($unexpected.Count -gt 0){ throw "Unexpected model(s) appeared: $($unexpected -join ', ')" }
Write-Host "Download completed or target already existed: $Target"
