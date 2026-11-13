from PIL import Image

def inspect_image2():
    im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793700147837_474947b8.png')
    w, h = im.size
    print(f"Image 2 size: {w}x{h}")
    pixels = im.load()
    # Find bright green pixels (around y > 40)
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            # bright green
            if g > 150 and r < 180 and b < 150:
                # check where they are
                pass
    # Print bottom rows
    for y in range(h-20, h, 2):
        row = f"{y:2d}: "
        for x in range(0, w, 16):
            r, g, b, a = pixels[x, y]
            if g > 140 and r < 180 and b < 120:
                row += "G"
            elif r > 100 or g > 100 or b > 100:
                row += "*"
            else:
                row += "."
        print(row)

inspect_image2()

