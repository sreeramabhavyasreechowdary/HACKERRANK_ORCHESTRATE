$gitCmd = "C:\Users\Bhavyasree s\AppData\Local\github-copilot-git-2.53.0-4\cmd"
$gitBin = "C:\Users\Bhavyasree s\AppData\Local\github-copilot-git-2.53.0-4\mingw64\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")

$pathsToAdd = @($gitCmd, $gitBin)
$updated = $false
foreach ($p in $pathsToAdd) {
    if ($userPath -notlike "*$p*") {
        $userPath = $userPath.TrimEnd(";") + ";" + $p
        $updated = $true
    }
}

if ($updated) {
    [Environment]::SetEnvironmentVariable("Path", $userPath, "User")
    Write-Output "Successfully added Git to User PATH environment variable."
} else {
    Write-Output "Git paths already exist in User PATH."
}

$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
& git --version
