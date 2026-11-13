from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793641161566_98c7b450.png')
print("Size:", im.size)
# Find all text-like content by sampling lines
w, h = im.size
pixels = im.load()

# Let's see what is at the top, middle, bottom
for y in range(0, h, 20):
    row = ""
    for x in range(0, w, 15):
        r, g, b, a = pixels[x, y]
        if r > 180 and g > 130 and b < 150:
            row += "O"
        elif r > 100 or g > 100 or b > 100:
            row += "*"
        else:
            row += "."
    print(f"{y:3d}: {row}")

