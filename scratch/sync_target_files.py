import os
import shutil

TARGET_DIRS = [
    r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\CAT_v0.7.4\calc_terminal",
    r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\build\lib\calc_terminal",
    r"C:\Users\ADMIN\AppData\Local\Programs\CAT\lib\calc_terminal",
    r"C:\Users\ADMIN\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages\calc_terminal",
    r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-cat-test\Lib\site-packages\calc_terminal",
    r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-package-test\Lib\site-packages\calc_terminal",
    r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-test\Lib\site-packages\calc_terminal",
    r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-test314\Lib\site-packages\calc_terminal",
]

SRC_DIR = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal"

FILES_TO_SYNC = [
    os.path.join("ui", "header.py"),
    os.path.join("ui", "app.py"),
    os.path.join("ui", "theme_css.py"),
    os.path.join("ui", "palette.py"),
    os.path.join("ui", "command_palette.py"),
    os.path.join("ui", "nav_screens.py"),
    os.path.join("ui", "sidebar.py"),
    os.path.join("ui", "composer.py"),
]

def sync_all():
    print("=" * 60)
    print("SYNCING MODIFIED FILES ACROSS ALL DISTRIBUTION TARGETS")
    print("=" * 60)
    
    for target in TARGET_DIRS:
        if not os.path.exists(target):
            print(f"[SKIP - Not Found] {target}")
            continue
        print(f"\n[TARGET] {target}")
        for rel_path in FILES_TO_SYNC:
            src_file = os.path.join(SRC_DIR, rel_path)
            dest_file = os.path.join(target, rel_path)
            if not os.path.exists(src_file):
                print(f"  [ERROR] Source missing: {src_file}")
                continue
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            shutil.copy2(src_file, dest_file)
            print(f"  -> Synced: {rel_path}")

    print("\n" + "=" * 60)
    print("ALL ACCESSIBLE TARGETS SYNCHRONIZED")
    print("=" * 60)

if __name__ == "__main__":
    sync_all()

