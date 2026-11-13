from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793641161566_98c7b450.png')
pixels = im.load()

# Border O is around x = 586
for y in range(260, 310, 2):
    row = f"{y:3d}: "
    for x in range(570, 615):
        r, g, b, a = pixels[x, y]
        if r > 180 and g > 130 and b < 150: # border
            row += "|"
        elif r > 100 or g > 100 or b > 100: # glyph/bright
            row += "#"
        elif r > 40 or g > 40 or b > 40: # dim
            row += "."
        else:
            row += " "
    print(row)

