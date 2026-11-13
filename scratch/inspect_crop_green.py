from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793700147837_474947b8.png')
w, h = im.size
pixels = im.load()

# Save a cropped area around the 3 green blocks
crop = im.crop((400, 40, 700, 66))
crop.save('scratch/image2_green_crop.png')
print("Saved scratch/image2_green_crop.png")

for y in range(48, 66, 2):
    row = f"{y:2d}: "
    for x in range(450, 650, 4):
        r, g, b, a = pixels[x, y]
        if g > 150 and r < 180:
            row += "G"
        elif r > 100 or g > 100 or b > 100:
            row += "#"
        else:
            row += "."
    print(row)

