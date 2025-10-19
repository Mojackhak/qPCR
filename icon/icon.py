#%%
from PIL import Image

# Load your PNG icon
img = Image.open("icon.png")

# Save as ICO (for Windows)
img.save("icon.ico", format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

# Save as ICNS (for macOS)
img.save("icon.icns", format='ICNS')
# %%
