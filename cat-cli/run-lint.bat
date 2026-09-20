@echo off
cd /d "c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\cat-cli"
echo === ESLINT ===
npx eslint . --max-warnings=999
echo ESLINT_EXITCODE=%errorlevel%
