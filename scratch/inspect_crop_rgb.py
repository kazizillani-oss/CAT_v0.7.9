from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793641161566_98c7b450.png')
w, h = im.size
pixels = im.load()

# Let's crop x from 550 to 623, y from 260 to 340
# Save as a cropped png to inspect or print rgb
crop = im.crop((450, 240, w, h))
crop.save('scratch/crop_overflow.png')
print("Saved scratch/crop_overflow.png")

# Let's also print pixel colors for y=280 to 330, x from 550 to 620
for y in range(270, 325, 4):
    row = f"{y:3d}: "
    for x in range(540, 620, 2):
        r, g, b, a = pixels[x, y]
        row += f"({r:02x}{g:02x}{b:02x}) "
    print(row)

