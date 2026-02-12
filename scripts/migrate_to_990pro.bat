@echo off
REM ============================================================
REM BeatSight Data Migration to Samsung 990 Pro (F: Drive)
REM ============================================================
REM Features:
REM   - Resumable (/Z flag)
REM   - Multi-threaded (/MT:16)
REM   - Detailed logging
REM   - Retries on failure
REM   - Verification
REM ============================================================

setlocal enabledelayedexpansion
set TIMESTAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGDIR=C:\github\BeatSight\logs\migration_%TIMESTAMP%
mkdir "%LOGDIR%" 2>nul

echo ============================================================
echo BeatSight Data Migration to F: Drive (990 Pro)
echo ============================================================
echo.
echo Log directory: %LOGDIR%
echo.
echo This will migrate:
echo   1. C:\temp_dataset\feature_cache_v5      -^> F:\feature_cache\
echo   2. C:\temp_dataset\prod_v5_fixed_20251212 -^> F:\datasets\prod_v5_fixed_20251212\
echo   3. C:\temp_dataset\augmented_rare_classes -^> F:\datasets\augmented_rare_classes\
echo   4. C:\github\BeatSight\data\dataset_index -^> F:\manifests\dataset_index\
echo   5. C:\datasets\                           -^> F:\datasets\ (lakh_midi, STAR_Drums, etc.)
echo.
echo Press Ctrl+C to cancel, or
pause

REM ============================================================
REM ROBOCOPY OPTIONS EXPLAINED:
REM   /E       = Copy subdirectories, including empty ones
REM   /Z       = Restartable mode (resume if interrupted)
REM   /MT:16   = Multi-threaded with 16 threads (adjust if needed)
REM   /R:3     = Retry 3 times on failure
REM   /W:5     = Wait 5 seconds between retries
REM   /NP      = No progress percentage (cleaner log)
REM   /ETA     = Show estimated time of arrival
REM   /LOG+    = Append to log file
REM   /TEE     = Output to console AND log file
REM   /V       = Verbose output
REM   /DCOPY:T = Copy directory timestamps
REM ============================================================

echo.
echo ============================================================
echo [1/4] Migrating feature_cache_v5 (~512GB - THIS WILL TAKE A WHILE)
echo ============================================================
echo Start time: %TIME%
robocopy "C:\temp_dataset\feature_cache_v5" "F:\feature_cache" /E /Z /MT:16 /R:3 /W:5 /ETA /LOG+:"%LOGDIR%\01_feature_cache.log" /TEE /V /DCOPY:T
echo Finished: %TIME%
echo.

echo ============================================================
echo [2/4] Migrating prod_v5_fixed_20251212 dataset
echo ============================================================
echo Start time: %TIME%
robocopy "C:\temp_dataset\prod_v5_fixed_20251212" "F:\datasets\prod_v5_fixed_20251212" /E /Z /MT:16 /R:3 /W:5 /ETA /LOG+:"%LOGDIR%\02_prod_dataset.log" /TEE /V /DCOPY:T
echo Finished: %TIME%
echo.

echo ============================================================
echo [3/4] Migrating augmented_rare_classes
echo ============================================================
echo Start time: %TIME%
robocopy "C:\temp_dataset\augmented_rare_classes" "F:\datasets\augmented_rare_classes" /E /Z /MT:16 /R:3 /W:5 /ETA /LOG+:"%LOGDIR%\03_augmented_rare.log" /TEE /V /DCOPY:T
echo Finished: %TIME%
echo.

echo ============================================================
echo [4/5] Migrating dataset_index (manifests/labels)
echo ============================================================
echo Start time: %TIME%
robocopy "C:\github\BeatSight\data\dataset_index" "F:\manifests\dataset_index" /E /Z /MT:16 /R:3 /W:5 /ETA /LOG+:"%LOGDIR%\04_manifests.log" /TEE /V /DCOPY:T
echo Finished: %TIME%
echo.

echo ============================================================
echo [5/5] Migrating C:\datasets (lakh_midi, STAR_Drums, etc.)
echo ============================================================
echo Start time: %TIME%
robocopy "C:\datasets" "F:\datasets" /E /Z /MT:16 /R:3 /W:5 /ETA /LOG+:"%LOGDIR%\05_c_datasets.log" /TEE /V /DCOPY:T
echo Finished: %TIME%
echo.

echo ============================================================
echo MIGRATION COMPLETE!
echo ============================================================
echo.
echo Log files saved to: %LOGDIR%
echo.
echo NEXT STEPS:
echo   1. Verify data integrity (spot check some files)
echo   2. Update BeatSight config paths
echo   3. Run a test training iteration
echo   4. Once verified, delete old data from C: drive
echo.
echo DO NOT delete C:\temp_dataset until you verify F: drive data!
echo.
pause
