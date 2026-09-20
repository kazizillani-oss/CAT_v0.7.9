@echo off
cd /d "c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\cat-cli"
echo === VSIX PACKAGE ===
npx vsce package --allow-missing-repository --skip-license 2>&1
echo PACKAGE_EXITCODE=%errorlevel%
