from PIL import Image

def analyze(name):
    p = f'C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/.user_uploaded/{name}'
    im = Image.open(p)
    print(f"=== {name} {im.size} ===")

analyze('media_1793700124831_87e65c1d.png')
analyze('media_1793700147837_474947b8.png')
analyze('media_1793700224334_ae1b32c2.png')

