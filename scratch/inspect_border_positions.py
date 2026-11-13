from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793641161566_98c7b450.png')
w, h = im.size
pixels = im.load()

# Let's inspect rows 250, 260, 270, 280, 290, 300, 310, 320, 330
for y in [240, 255, 265, 275, 285, 295, 305, 315, 325]:
    # find where the border is on the left and right
    borders = []
    for x in range(w):
        r, g, b, a = pixels[x, y]
        if r > 180 and g > 130 and b < 150: # orange border
            borders.append(x)
    print(f"y={y}: borders at {borders[:5]} ... {borders[-5:] if len(borders) > 5 else ''}")

