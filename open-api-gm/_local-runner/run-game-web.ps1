# ================================
# Veinbreaker Dev Server Launcher
# ================================

$PROJECT_PATH = "D:\Code\VeinBreaker\open-api-gm"

Write-Host "Starting Veinbreaker servers..."
Write-Host "Project path: $PROJECT_PATH"
Write-Host ""

Set-Location $PROJECT_PATH

# Start FastAPI (port 8000)
Write-Host "Starting FastAPI server on http://localhost:8000"
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000"

# Start static HTML server (port 5173)
Write-Host "Starting static UI server on http://localhost:5173"
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command python -m http.server 5173"

Write-Host ""
Write-Host "Servers started."
Write-Host "Open: http://localhost:5173"
