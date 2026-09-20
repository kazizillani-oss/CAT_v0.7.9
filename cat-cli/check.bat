@echo off
cd /d "c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\cat-cli"
node -e "const p=require('./package.json'); console.log('JSON valid'); console.log('main:', p.main); console.log('activationEvents:', JSON.stringify(p.activationEvents)); console.log('views:', JSON.stringify(p.contributes.views)); console.log('viewsContainers:', JSON.stringify(p.contributes.viewsContainers)); console.log('keybindings:', JSON.stringify(p.contributes.keybindings));"
