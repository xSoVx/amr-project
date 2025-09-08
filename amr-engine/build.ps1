# AMR Engine Docker Build Script (PowerShell)
# Run this from the amr-engine directory

Write-Host "🏗️  Building AMR Engine Docker image..." -ForegroundColor Cyan

try {
    # Build the main image
    docker build -f docker/Dockerfile -t amr-engine:latest .
    Write-Host "✅ AMR Engine image built successfully!" -ForegroundColor Green

    # Build the test image
    docker build -f docker/Dockerfile --target test -t amr-engine:test .
    Write-Host "✅ AMR Engine test image built successfully!" -ForegroundColor Green

    # List the images
    Write-Host "📦 Built images:" -ForegroundColor Yellow
    docker images | Where-Object { $_ -match "amr-engine" }

    Write-Host ""
    Write-Host "🚀 To run the application:" -ForegroundColor Green
    Write-Host "   docker run -p 8080:8080 amr-engine:latest" -ForegroundColor White
    Write-Host ""
    Write-Host "🧪 To run tests:" -ForegroundColor Green  
    Write-Host "   docker run amr-engine:test" -ForegroundColor White
    Write-Host ""
    Write-Host "📋 To run with docker-compose:" -ForegroundColor Green
    Write-Host "   docker-compose -f docker/docker-compose.yml up --build" -ForegroundColor White

} catch {
    Write-Host "❌ Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}