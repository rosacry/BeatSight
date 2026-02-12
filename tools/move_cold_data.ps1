# Move Cold Data from F: (SSD) to D: (HDD)
# Run as: powershell -ExecutionPolicy Bypass -File move_cold_data.ps1

$ErrorActionPreference = "Stop"

$coldStorage = "D:\cold_storage"
$datasets = "D:\cold_storage\datasets"

# Create destination directories
Write-Host "Creating destination directories..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $coldStorage | Out-Null
New-Item -ItemType Directory -Force -Path $datasets | Out-Null

# Define what to move (source -> destination)
$moves = @(
    @{ Source = "F:\datasets\star_drums"; Dest = "$datasets\star_drums"; Size = "506.28 GB" }
    @{ Source = "F:\datasets\lakh_midi"; Dest = "$datasets\lakh_midi"; Size = "7.98 GB" }
    @{ Source = "F:\datasets\fsd50k"; Dest = "$datasets\fsd50k"; Size = "5.15 GB" }
    @{ Source = "F:\datasets\star_drums_extracted"; Dest = "$datasets\star_drums_extracted"; Size = "995 MB" }
    @{ Source = "F:\datasets\augmented_rare_classes"; Dest = "$datasets\augmented_rare_classes"; Size = "9.7 MB" }
    @{ Source = "F:\datasets\lakh_synthesized_splash"; Dest = "$datasets\lakh_synthesized_splash"; Size = "2.0 MB" }
    @{ Source = "F:\datasets\lakh_synthesized"; Dest = "$datasets\lakh_synthesized"; Size = "1.9 MB" }
    @{ Source = "F:\datasets\soundfonts"; Dest = "$datasets\soundfonts"; Size = "~0 MB" }
)

Write-Host "`n=== Cold Data Migration Plan ===" -ForegroundColor Yellow
Write-Host "Source: F: (Samsung 990 EVO Plus SSD)"
Write-Host "Dest:   D: (Seagate 2TB HDD)"
Write-Host "Total:  ~520 GB to move`n"

foreach ($item in $moves) {
    Write-Host "  $($item.Size.PadLeft(12)) : $($item.Source)" -ForegroundColor Gray
}

Write-Host "`nPress Enter to start, or Ctrl+C to cancel..." -ForegroundColor Green
Read-Host

$totalMoved = 0
$startTime = Get-Date

foreach ($item in $moves) {
    $src = $item.Source
    $dst = $item.Dest
    $size = $item.Size
    
    if (-not (Test-Path $src)) {
        Write-Host "[SKIP] $src does not exist" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "`n[MOVING] $src ($size)" -ForegroundColor Cyan
    Write-Host "     -> $dst"
    
    $itemStart = Get-Date
    
    # Use robocopy for reliable move with progress
    # /MOVE = move files (delete from source after copy)
    # /E = include subdirectories including empty
    # /MT:2 = 2 threads (conservative - avoids resource exhaustion on long ops)
    # /R:3 = 3 retries
    # /W:10 = 10 second wait between retries
    # /NP = no progress percentage (cleaner output)
    # /NFL /NDL = no file/dir listing (less spam)
    # /J = unbuffered I/O (reduces memory pressure for large files)
    
    $robocopyArgs = @(
        "`"$src`"",
        "`"$dst`"",
        "/MOVE", "/E", "/MT:2", "/R:3", "/W:10", "/NP", "/NFL", "/NDL", "/J"
    )
    
    $process = Start-Process -FilePath "robocopy" -ArgumentList $robocopyArgs -Wait -PassThru -NoNewWindow
    
    # Robocopy exit codes: 0-7 are success, 8+ are errors
    if ($process.ExitCode -lt 8) {
        $elapsed = (Get-Date) - $itemStart
        Write-Host "[DONE] Completed in $($elapsed.ToString('hh\:mm\:ss'))" -ForegroundColor Green
        $totalMoved++
    } else {
        Write-Host "[ERROR] Robocopy failed with code $($process.ExitCode)" -ForegroundColor Red
    }
}

$totalElapsed = (Get-Date) - $startTime
Write-Host "`n=== Migration Complete ===" -ForegroundColor Green
Write-Host "Moved $totalMoved items in $($totalElapsed.ToString('hh\:mm\:ss'))"

# Show disk space after
Write-Host "`n=== Disk Space After ===" -ForegroundColor Yellow
Get-PSDrive F, D | Select-Object Name, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,1)}}, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,1)}}

Write-Host "`nDone! Cold data is now on D:\cold_storage" -ForegroundColor Green
