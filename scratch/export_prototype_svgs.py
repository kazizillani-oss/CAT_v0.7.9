import asyncio
from calc_terminal.ui import theme_css, app as cct_app
from scratch.prototype_new_composer import PrototypeApp

async def main():
    for w in [100, 50]:
        app = PrototypeApp()
        async with app.run_test(size=(w, 20)) as pilot:
            await pilot.pause(0.05)
            svg = app.export_screenshot()
            with open(f"scratch/prototype_{w}.svg", "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"Exported scratch/prototype_{w}.svg")

if __name__ == "__main__":
    asyncio.run(main())
