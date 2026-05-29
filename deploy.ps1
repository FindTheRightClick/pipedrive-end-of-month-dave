$Source = $env:GITHUB_WORKSPACE
$destination = "C:\Python\pipedrive-end-of-month-dave\"
$sleepTimer = 1

if (Test-Path $destination) {
    Write-Host "Removing from $destination"
    Remove-Item -Path $destination\* -Recurse -Force
}

#New-Item -ItemType Directory -Path "$destination\output" -Force

Write-Host "Deploying from $Source to $destination"
Copy-Item -Path $Source\* -Destination $destination -Recurse -Force

Write-Host "Deploy complete.."
