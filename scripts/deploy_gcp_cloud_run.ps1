# ==============================================================================
# Google Cloud Run Deployment Script for UPPCL Monitoring Container
# ==============================================================================
# Deploys as an always-on 24/7 background worker container in GCP region asia-south1 (Mumbai)

param (
    [string]$ProjectId = "",
    [string]$Region = "asia-south1",
    [string]$ServiceName = "uppcl-x-complaint-monitor"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Google Cloud SDK (gcloud) is not installed on PATH." -ForegroundColor Yellow
    Write-Host "    Install via: winget install Google.CloudSDK or visit https://cloud.google.com/sdk/docs/install"
    exit 1
}

if (-not $ProjectId) {
    $ProjectId = (gcloud config get-value project 2>$null)
    if (-not $ProjectId) {
        Write-Host "Please provide your GCP Project ID: .\scripts\deploy_gcp_cloud_run.ps1 -ProjectId your-gcp-project-id" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[*] Target GCP Project: $ProjectId" -ForegroundColor Cyan
Write-Host "[*] Target Region:      $Region" -ForegroundColor Cyan
Write-Host "[*] Target Service:     $ServiceName" -ForegroundColor Cyan

# Ensure required GCP APIs are enabled
Write-Host "[*] Enabling Cloud Run & Artifact Registry APIs..." -ForegroundColor Cyan
gcloud services enable run.googleapis.com artifactregistry.googleapis.com --project $ProjectId

# Build and Deploy directly from source
Write-Host "[*] Building container and deploying to Cloud Run (Always-On mode)..." -ForegroundColor Cyan
gcloud run deploy $ServiceName `
    --source . `
    --region $Region `
    --project $ProjectId `
    --platform managed `
    --no-allow-unauthenticated `
    --min-instances 1 `
    --max-instances 1 `
    --no-cpu-throttling `
    --memory 512Mi `
    --cpu 1 `
    --env-vars-file .env.yaml `
    --timeout 3600

Write-Host "[+] Cloud Run deployment completed successfully!" -ForegroundColor Green
Write-Host "    The container is now running 24/7 in Google Cloud (asia-south1)."
