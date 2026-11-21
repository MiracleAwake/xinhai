param([ValidateSet('open','close','status')][string]$Action='status')
$rules=@('Block Ollama outbound (prevent auto model download)','Block Ollama App outbound (prevent auto model download)')
if($Action -eq 'status'){Get-NetFirewallRule -DisplayName $rules -ErrorAction Stop | Select DisplayName,Enabled,Action,Direction; exit}
$enabled=if($Action -eq 'open'){'False'}else{'True'}
foreach($r in $rules){Set-NetFirewallRule -DisplayName $r -Enabled $enabled}
Get-NetFirewallRule -DisplayName $rules | Select DisplayName,Enabled,Action,Direction
