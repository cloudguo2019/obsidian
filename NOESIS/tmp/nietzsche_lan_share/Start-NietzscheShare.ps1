$ErrorActionPreference = 'Stop'
$workDir = $PSScriptRoot
$resultPath = Join-Path $workDir 'result.json'
try {
    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if ($result.Status -ne 'configured') {
        Write-Host 'Windows administrator approval is required to create the account, SMB share and LAN firewall rule.' -ForegroundColor Cyan
        $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + (Join-Path $workDir 'Configure-NietzscheShare.ps1') + '" -WorkDir "' + $workDir + '"'
        $process = Start-Process -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Verb RunAs -WindowStyle Hidden -ArgumentList $arguments -Wait -PassThru
        $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        if ($result.Status -ne 'configured') { throw ($result | ConvertTo-Json -Depth 5) }
    }
    Write-Host 'Checking authenticated file creation, editing, copying, renaming and removal...' -ForegroundColor Cyan
    & (Join-Path $workDir 'Verify-NietzscheShare.ps1')
    $verification = Get-Content -LiteralPath (Join-Path $workDir 'verification.json') -Raw | ConvertFrom-Json
    if ($verification.Status -ne 'passed') { throw $verification.Error }
    $credential = Import-Clixml -LiteralPath (Join-Path $workDir 'credential.xml')
    Write-Host ''
    Write-Host 'SHARING READY - AUTHENTICATED FILE OPERATIONS VERIFIED' -ForegroundColor Green
    Write-Host 'Windows address: \\192.168.2.217\Nietzsche'
    Write-Host 'macOS / phone SMB address: smb://192.168.2.217/Nietzsche'
    Write-Host ('Username: ' + $credential.UserName)
    Write-Host ('Password: ' + $credential.GetNetworkCredential().Password)
    Write-Host 'Account access: read, edit, copy, rename and delete files in the Nietzsche share.'
    Write-Host 'Allowed network: 192.168.2.0/24 on the physical Ethernet adapter.'
    Write-Host 'The dedicated account cannot sign in at the console or via Remote Desktop.'
    Write-Host 'This test ran through the local SMB server; connectivity from a second LAN device is not yet tested.'
}
catch {
    Write-Host ''
    Write-Host ('SETUP NOT COMPLETED: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Detailed state: ' + $resultPath)
}
Read-Host 'Press Enter to close this window'
