from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793641161566_98c7b450.png')
print("Image size:", im.size)
w, h = im.size
pixels = im.load()

# Let's crop bottom right area
for y in range(h - 100, h, 2):
    row = ""
    for x in range(w - 200, w, 3):
        r, g, b, a = pixels[x, y]
        # background is dark (~30, 30, 40)
        # orange border is (~240, 180, 120)
        if r > 180 and g > 130 and b < 150: # orange border
            row += "O"
        elif r > 150 and g > 150 and b > 150: # glyph/bright
            row += "*"
        elif r > 60 or g > 60 or b > 60: # widget surface or dim border
            row += "#"
        else:
            row += "."
    if "O" in row or "*" in row or "#" in row:
        print(f"{y:3d}: {row}")

