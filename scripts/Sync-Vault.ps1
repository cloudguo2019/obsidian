param(
    [string]$Message = "vault sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

$ErrorActionPreference = 'Stop'
$vaultRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath (Join-Path $vaultRoot '.git'))) {
    throw "Not an Obsidian Git vault: $vaultRoot"
}

Push-Location $vaultRoot
try {
    $branch = git branch --show-current
    if (-not $branch) { throw 'Cannot sync a detached HEAD.' }

    git pull --rebase --autostash origin $branch
    if ($LASTEXITCODE -ne 0) { throw 'git pull failed; resolve the conflict before pushing.' }

    git add --all
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m $Message
        if ($LASTEXITCODE -ne 0) { throw 'git commit failed.' }
    }

    git push origin $branch
    if ($LASTEXITCODE -ne 0) { throw 'git push failed.' }
}
finally {
    Pop-Location
}

