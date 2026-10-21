"""アプリのアイコン (icon.ico) を作る。Pillow が必要。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "icon.ico"
SIZE = 256


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=56, fill=(20, 21, 24, 255))
    font = ImageFont.truetype("seguisym.ttf", 168)
    d.text((SIZE / 2, SIZE / 2 + 6), "♯", font=font, fill=(143, 212, 180, 255), anchor="mm")
    img.save(OUT, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
