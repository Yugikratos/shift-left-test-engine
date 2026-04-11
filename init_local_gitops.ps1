<#
.SYNOPSIS
Simulates an Enterprise GitOps Bootstrap by deploying ArgoCD into the local Kubernetes cluster.
#>

Write-Host "🚀 Bootstrapping Local GitOps Ecosystem (ArgoCD & Nexus Mock)" -ForegroundColor Cyan

# 1. Ensure Local Nexus Registry is up via Docker Compose
Write-Host "1. Starting Official Sonatype Nexus 3 via Docker Compose..." -ForegroundColor Yellow
docker-compose up -d local-nexus

Write-Host "⏳ Waiting for Sonatype Nexus UI to boot on port 8081 (Takes ~2 mins)..." -ForegroundColor Magenta
$nexusBooted = $false
for ($i = 0; $i -lt 15; $i++) {
    $response = try { Invoke-WebRequest -Uri "http://localhost:8081" -UseBasicParsing } catch { $null }
    if ($response.StatusCode -eq 200) {
        $nexusBooted = $true
        break
    }
    Start-Sleep -Seconds 15
}

Write-Host "Fetching Nexus admin password from container..." -ForegroundColor Cyan
$nexusPassword = docker exec $(docker-compose ps -q local-nexus) cat /nexus-data/admin.password
Write-Host "✨ Nexus Admin Login: admin" -ForegroundColor Green
Write-Host "✨ Nexus Admin Password: $nexusPassword" -ForegroundColor Green

# 2. Deploy ArgoCD into active K8s cluster
Write-Host "2. Deploying ArgoCD Core Components to Kubernetes..." -ForegroundColor Yellow
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

Write-Host "⏳ Waiting for ArgoCD Server to activate (this may take a minute)..." -ForegroundColor Magenta
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

# 3. Apply the ArgoCD Application definition
Write-Host "3. Applying GitOps Application Mapping (syncing k8s/)..." -ForegroundColor Yellow
kubectl apply -f argocd-application.yaml

Write-Host "✅ Enterprise GitOps Mock Deployed Successfully!" -ForegroundColor Green
Write-Host "To access the UI:"
Write-Host "  1. Run port-forward: kubectl port-forward svc/argocd-server -n argocd 8080:443"
Write-Host "  2. Open https://localhost:8080 in your browser."
Write-Host "  3. Get default admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath=`"{.data.password}`" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(`$_)) }"
