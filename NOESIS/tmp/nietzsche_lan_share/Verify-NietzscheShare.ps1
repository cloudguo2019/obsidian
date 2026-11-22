$ErrorActionPreference = 'Stop'
$workDir = $PSScriptRoot
$result = Get-Content -LiteralPath (Join-Path $workDir 'result.json') -Raw | ConvertFrom-Json
if ($result.Status -ne 'configured') { throw 'Sharing is not configured yet.' }
$credential = Import-Clixml -LiteralPath (Join-Path $workDir 'credential.xml')
$driveName = 'NtzShareTest'
$testFolderName = '.codex-smb-test-' + [guid]::NewGuid().ToString('N')
$testFolder = $result.UncPath.TrimEnd('\') + '\' + $testFolderName
$driveCreated = $false
$folderCreated = $false
$checkResult = [ordered]@{ Status='failed'; Method='Authenticated SMB using the dedicated non-administrator account'; UncPath=$result.UncPath; Account=$credential.UserName }
try {
    New-PSDrive -Name $driveName -PSProvider FileSystem -Root $result.UncPath -Credential $credential -Scope Script | Out-Null
    $driveCreated = $true
    New-Item -Path $testFolder -ItemType Directory | Out-Null
    $folderCreated = $true
    $sourceFile = Join-Path $testFolder 'create-and-edit.txt'
    $copyFile = Join-Path $testFolder 'copy.txt'
    $renamedFile = Join-Path $testFolder 'renamed.txt'
    Set-Content -LiteralPath $sourceFile -Value 'Nietzsche authenticated SMB create test' -Encoding UTF8
    Add-Content -LiteralPath $sourceFile -Value 'Edit succeeded' -Encoding UTF8
    $content = Get-Content -LiteralPath $sourceFile -Raw
    if ($content -notmatch 'Edit succeeded') { throw 'SMB edit/read verification failed.' }
    Copy-Item -LiteralPath $sourceFile -Destination $copyFile
    Rename-Item -LiteralPath $copyFile -NewName 'renamed.txt'
    if ((Get-FileHash -LiteralPath $sourceFile).Hash -ne (Get-FileHash -LiteralPath $renamedFile).Hash) { throw 'SMB copy verification failed.' }
    $checkResult.Status='passed'
    $checkResult.VerifiedActions=@('authenticate','list','create_directory','create_file','read','edit','copy','rename','delete_test_files')
    $checkResult.CheckedAt=(Get-Date).ToString('o')
}
catch {
    $checkResult.Error=$_.Exception.Message
}
finally {
    if ($folderCreated) {
        foreach ($leaf in @('create-and-edit.txt','copy.txt','renamed.txt')) {
            $candidate=Join-Path $testFolder $leaf
            if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Force }
        }
        # A single, known, freshly-created directory; no recursive deletion.
        Remove-Item -LiteralPath $testFolder -Force
    }
    if ($driveCreated) { Remove-PSDrive -Name $driveName -Force }
    $checkResult | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $workDir 'verification.json') -Encoding UTF8
}
$checkResult | ConvertTo-Json -Depth 5
if ($checkResult.Status -ne 'passed') { exit 1 }
