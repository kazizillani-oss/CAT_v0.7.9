from PIL import Image

im = Image.open('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/media_1793700147837_474947b8.png')
w, h = im.size
pixels = im.load()

# Let's inspect the text inside the 3 green boxes (x from 450 to 650, y from 50 to 66)
crop = im.crop((440, 48, 640, 66))
crop.save('scratch/crop_three_boxes.png')

# Let's see the characters line by line
for y in range(54, 66):
    row = f"{y:2d}: "
    for x in range(480, 640, 2):
        r, g, b, a = pixels[x, y]
        # if pixel is black/dark inside the green box
        if r < 50 and g < 50 and b < 50:
            row += " "
        elif g > 150: # green background
            row += "G"
        else:
            row += "#"
    print(row)

