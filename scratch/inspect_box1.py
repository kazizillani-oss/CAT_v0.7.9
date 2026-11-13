from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793700147837_474947b8.png')
pixels = im.load()

for y in range(54, 66):
    row = f"{y:2d}: "
    for x in range(430, 520, 2):
        r, g, b, a = pixels[x, y]
        if g > 150 and r < 180:
            row += "G"
        else:
            row += "."
    print(row)

