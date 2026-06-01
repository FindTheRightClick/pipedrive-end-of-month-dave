$TeamsCardHeader = "RC Pipedrive-End-of-Month-Dave Deployment Status"
$WebhookUri = "https://defaultb577482832674f088a03a9b98feca9.95.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/ad0c19e6adf74f258e1d15bb5a10ef86/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=kCy5DKB_vs-0qZVcqLEOqATvQCsluUL94XGWycJcDnU"

function Send-TeamsCard {
    param ([string]$TeamsCardHeader, [string]$Status, [string]$Color, [string]$Message)

    $body = @{
        type    = "AdaptiveCard"
        version = "1.4"
        body    = @(
            @{
                type   = "TextBlock"
                text   = $TeamsCardHeader
                weight = "Bolder"
                size   = "Medium"
                color  = $Color
            }
            @{
                type  = "FactSet"
                facts = @(
                    @{ title = "Status";      value = $Status }
                    @{ title = "Message";     value = $Message }
                    @{ title = "Environment"; value = "Production" }
                    @{ title = "Deployed by"; value = "GitHub Runner: Pulse-Web01" }
                    @{ title = "Time";        value = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") }
                )
            }
        )
    } | ConvertTo-Json -Depth 10

    try {
        Invoke-RestMethod -Uri $WebhookUri -Method Post -ContentType "application/json" -Body $body
    } catch {
        Write-Warning "Teams notification failed: $_"
    }
}

# --- Start notification ---
Send-TeamsCard -TeamsCardHeader $TeamsCardHeader -Status "In Progress" -Color "Accent" -Message "Deploy started."

$Source = $env:GITHUB_WORKSPACE
$destination = "C:\Python\pipedrive-end-of-month-dave\"
$sleepTimer = 1

try
{
    if (Test-Path $destination) {
        Write-Host "Removing from $destination"
        Remove-Item -Path $destination\* -Recurse -Force
    }
    
    #New-Item -ItemType Directory -Path "$destination\output" -Force
    
    Write-Host "Deploying from $Source to $destination"
    Copy-Item -Path $Source\* -Destination $destination -Recurse -Force
    
    Write-Host "Deploy complete.."
    Send-TeamsCard -TeamsCardHeader $TeamsCardHeader -Status "Success" -Color "Good" -Message "Deploy completed successfully."
} catch {
    Write-Error $_
    Send-TeamsCard -TeamsCardHeader $TeamsCardHeader -Status "Failed" -Color "Attention" -Message $_.ToString()
    exit 1
}
