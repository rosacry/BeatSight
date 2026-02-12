@echo off
REM ============================================================
REM BeatSight - Delete Old Data from C: Drive
REM Run this ONLY after verifying F: drive has all data!
REM ============================================================

echo ============================================================
echo WARNING: This will PERMANENTLY DELETE data from C: drive!
echo ============================================================
echo.
echo The following will be deleted:
echo   - C:\temp_dataset\feature_cache_v5    (~512 GB)
echo   - C:\temp_dataset\prod_v5_fixed_20251212  (~391 GB)
echo   - C:\temp_dataset\augmented_rare_classes  (~10 MB)
echo   - C:\datasets\                        (~7 GB)
echo.
echo Make sure you have verified F: drive contains all this data!
echo.
echo Press Ctrl+C to CANCEL, or
pause

echo.
echo [1/4] Deleting C:\temp_dataset\feature_cache_v5...
rmdir /s /q "C:\temp_dataset\feature_cache_v5"
echo Done.

echo.
echo [2/4] Deleting C:\temp_dataset\prod_v5_fixed_20251212...
rmdir /s /q "C:\temp_dataset\prod_v5_fixed_20251212"
echo Done.

echo.
echo [3/4] Deleting C:\temp_dataset\augmented_rare_classes...
rmdir /s /q "C:\temp_dataset\augmented_rare_classes"
echo Done.

echo.
echo [4/4] Deleting C:\datasets...
rmdir /s /q "C:\datasets"
echo Done.

echo.
echo ============================================================
echo CLEANUP COMPLETE!
echo ============================================================
echo.
echo Freed approximately ~910 GB on C: drive.
echo.
echo NOTE: C:\github\BeatSight\data\dataset_index was NOT deleted
echo       (it's in your git repo - you may want to keep it or
echo        update .gitignore and remove it separately)
echo.
pause
