@echo off
cd /d "c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\cat-cli"
echo === UNIT TESTS ===
npx mocha test/catLauncher.test.js --ui tdd --timeout 30000 2>&1
echo UNIT_EXITCODE=%errorlevel%
