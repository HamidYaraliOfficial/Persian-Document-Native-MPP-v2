@echo off
setlocal
cd /d "%~dp0"
where dotnet >nul 2>nul
if errorlevel 1 (
  echo [ERROR] .NET 8 SDK is required for native MPP generation.
  echo Install: https://dotnet.microsoft.com/download/dotnet/8.0
  pause
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found.
  pause
  exit /b 1
)
if not exist "native_writer\bin\Release\net8.0\native_mpp_writer.dll" (
  echo Building native MPP engine...
  dotnet build native_writer\native_mpp_writer.csproj -c Release --nologo
  if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
  )
)
start "Persian Doc to MPP" cmd /k "python -m uvicorn persian_doc_to_mpp.api:app --host 127.0.0.1 --port 8080"
timeout /t 2 >nul
start "" http://127.0.0.1:8080
endlocal
