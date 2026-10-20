"""Genera arte original y ligero para la biblioteca de perfiles incluida.

No descarga imágenes ni utiliza logotipos de juegos. Todas las portadas son
composiciones geométricas creadas por Team Nikaido para evitar dependencias y
mantener el paquete redistribuible.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter

WIDTH, HEIGHT = 1200, 520
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "profile_library"


def gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), top)
    pixels = image.load()
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        for x in range(WIDTH):
            side = x / max(1, WIDTH - 1)
            vignette = 1.0 - 0.25 * abs(side - 0.5) * 2
            pixels[x, y] = tuple(
                max(0, min(255, round((a * (1 - t) + b * t) * vignette)))
                for a, b in zip(top, bottom)
            )
    return image


def add_noise(image: Image.Image, seed: int, strength: int = 14) -> None:
    rnd = random.Random(seed)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(1400):
        x = rnd.randrange(WIDTH)
        y = rnd.randrange(HEIGHT)
        value = rnd.randrange(90, 220)
        alpha = rnd.randrange(4, strength)
        draw.point((x, y), fill=(value, value, value, alpha))
    image.paste(Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB"))


def glow_layer(image: Image.Image, painter: Callable[[ImageDraw.ImageDraw], None], blur: int = 28) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    painter(ImageDraw.Draw(layer))
    glow = layer.filter(ImageFilter.GaussianBlur(blur))
    merged = Image.alpha_composite(image.convert("RGBA"), glow)
    merged = Image.alpha_composite(merged, layer)
    image.paste(merged.convert("RGB"))


def speed_lines(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int], seed: int) -> None:
    rnd = random.Random(seed)
    for _ in range(34):
        y = rnd.randint(70, HEIGHT - 30)
        x = rnd.randint(-100, WIDTH - 250)
        length = rnd.randint(150, 460)
        width = rnd.randint(2, 7)
        draw.line((x, y, x + length, y - rnd.randint(5, 32)), fill=color, width=width)


def warzone() -> Image.Image:
    image = gradient((20, 13, 52), (4, 10, 26))
    def paint(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((420, 70, 960, 610), outline=(122, 87, 255, 120), width=8)
        draw.ellipse((515, 165, 865, 515), outline=(43, 210, 255, 170), width=5)
        draw.line((690, 30, 690, 500), fill=(126, 94, 255, 150), width=5)
        draw.line((390, 300, 1010, 300), fill=(43, 210, 255, 120), width=5)
        for x in range(90, 1200, 130):
            draw.line((x, 340, x + 80, 220), fill=(111, 69, 200, 35), width=3)
    glow_layer(image, paint, 34)
    add_noise(image, 11)
    return image


def forza() -> Image.Image:
    image = gradient((4, 28, 58), (7, 8, 24))
    glow_layer(image, lambda d: speed_lines(d, (38, 185, 255, 170), 22), 18)
    glow_layer(image, lambda d: speed_lines(d, (255, 55, 93, 130), 27), 24)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # Silueta original de auto deportivo, deliberadamente genérica.
    d.polygon([(330, 335), (430, 255), (760, 240), (930, 310), (1025, 365), (250, 365)], fill=(8, 12, 24, 225))
    d.line([(280, 350), (420, 280), (735, 270), (910, 325)], fill=(58, 205, 255, 210), width=8)
    d.ellipse((350, 330, 470, 450), fill=(5, 6, 13, 255), outline=(255, 71, 100, 190), width=8)
    d.ellipse((810, 330, 930, 450), fill=(5, 6, 13, 255), outline=(58, 205, 255, 190), width=8)
    image.paste(Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB"))
    add_noise(image, 12)
    return image


def resident() -> Image.Image:
    image = gradient((57, 8, 18), (7, 7, 15))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle((410, 150, 850, 520), fill=(8, 8, 15, 245), outline=(161, 38, 57, 180), width=8)
    d.polygon([(360, 170), (630, 30), (900, 170)], fill=(12, 10, 18, 250), outline=(170, 42, 58, 160))
    for x in (485, 675):
        d.rectangle((x, 220, x + 85, 330), fill=(89, 16, 27, 220))
        d.line((x + 8, 225, x + 75, 325), fill=(211, 70, 71, 110), width=3)
    d.rectangle((585, 315, 700, 520), fill=(23, 10, 18, 255), outline=(129, 30, 52, 190), width=5)
    # ramas
    rnd = random.Random(13)
    for side in (0, 1):
        base_x = 80 if side == 0 else 1120
        for _ in range(22):
            y = rnd.randint(40, 430)
            length = rnd.randint(70, 260)
            end_x = base_x + length if side == 0 else base_x - length
            d.line((base_x, y, end_x, y - rnd.randint(20, 80)), fill=(64, 22, 33, 150), width=rnd.randint(2, 7))
    merged = Image.alpha_composite(image.convert("RGBA"), layer)
    image.paste(merged.convert("RGB"))
    add_noise(image, 13, 18)
    return image


def elden() -> Image.Image:
    image = gradient((38, 20, 54), (9, 7, 18))
    def paint(draw: ImageDraw.ImageDraw) -> None:
        cx, cy = 690, 270
        for radius, alpha, width in ((220, 120, 9), (160, 155, 7), (92, 200, 5)):
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(225, 169, 64, alpha), width=width)
        draw.line((cx, 40, cx, 500), fill=(226, 170, 64, 150), width=7)
        draw.line((470, 270, 910, 270), fill=(152, 88, 211, 110), width=5)
        for angle in range(0, 360, 45):
            x = cx + math.cos(math.radians(angle)) * 250
            y = cy + math.sin(math.radians(angle)) * 210
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(237, 181, 80, 160))
    glow_layer(image, paint, 30)
    add_noise(image, 14)
    return image


def fc() -> Image.Image:
    image = gradient((5, 55, 39), (4, 18, 22))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # campo estilizado
    d.rounded_rectangle((110, 70, 1090, 500), radius=28, outline=(72, 222, 133, 135), width=7)
    d.line((600, 70, 600, 500), fill=(81, 222, 142, 110), width=5)
    d.ellipse((470, 170, 730, 430), outline=(81, 222, 142, 125), width=6)
    d.rectangle((110, 190, 280, 380), outline=(70, 190, 225, 120), width=5)
    d.rectangle((920, 190, 1090, 380), outline=(70, 190, 225, 120), width=5)
    # balón abstracto
    d.ellipse((520, 175, 680, 335), fill=(11, 26, 30, 235), outline=(105, 240, 170, 210), width=8)
    d.polygon([(600, 210), (635, 235), (622, 278), (578, 278), (565, 235)], fill=(85, 226, 151, 190))
    image.paste(Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB"))
    add_noise(image, 15)
    return image


def fighter() -> Image.Image:
    image = gradient((55, 9, 55), (4, 10, 28))
    def paint(draw: ImageDraw.ImageDraw) -> None:
        draw.polygon([(70, 430), (530, 45), (660, 45), (210, 430)], fill=(239, 46, 188, 120))
        draw.polygon([(520, 475), (960, 40), (1130, 40), (700, 475)], fill=(39, 210, 255, 120))
        # choque central
        points = []
        cx, cy = 620, 260
        for i in range(24):
            angle = i * math.pi / 12
            radius = 40 if i % 2 else 155
            points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        draw.polygon(points, outline=(255, 236, 255, 180), fill=(91, 30, 109, 90))
    glow_layer(image, paint, 24)
    add_noise(image, 16)
    return image


def minecraft() -> Image.Image:
    image = gradient((33, 105, 124), (7, 26, 28))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(17)
    block = 52
    # paisaje voxel original
    heights = [rnd.randint(2, 6) for _ in range(WIDTH // block + 2)]
    for ix, height in enumerate(heights):
        for iy in range(height):
            x = ix * block
            y = HEIGHT - (iy + 1) * block
            top = iy == height - 1
            color = (72, 158, 77, 255) if top else (90, 70, 48, 255)
            d.rectangle((x, y, x + block - 2, y + block - 2), fill=color)
            if top:
                d.rectangle((x, y, x + block - 2, y + 10), fill=(105, 205, 104, 255))
    # sol cuadrado
    d.rectangle((850, 70, 980, 200), fill=(247, 215, 103, 180))
    image.paste(Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB"))
    add_noise(image, 17, 10)
    return image


def ghost() -> Image.Image:
    image = gradient((8, 56, 48), (4, 12, 22))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # puerta torii genérica
    d.rectangle((520, 90, 555, 470), fill=(15, 18, 22, 245))
    d.rectangle((770, 90, 805, 470), fill=(15, 18, 22, 245))
    d.rectangle((460, 90, 865, 130), fill=(17, 20, 24, 250))
    d.polygon([(420, 78), (900, 78), (850, 115), (470, 115)], fill=(18, 21, 25, 250))
    # guerrero abstracto
    d.ellipse((620, 235, 700, 315), fill=(7, 9, 13, 255))
    d.polygon([(660, 290), (585, 470), (735, 470)], fill=(6, 8, 12, 255))
    d.line((690, 330, 810, 190), fill=(79, 224, 142, 190), width=9)
    # niebla
    fog = Image.new("RGBA", image.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    rnd = random.Random(18)
    for _ in range(34):
        x = rnd.randint(-100, WIDTH)
        y = rnd.randint(250, HEIGHT)
        fd.ellipse((x, y, x + rnd.randint(160, 430), y + rnd.randint(35, 90)), fill=(62, 213, 135, rnd.randint(12, 34)))
    fog = fog.filter(ImageFilter.GaussianBlur(25))
    merged = Image.alpha_composite(image.convert("RGBA"), layer)
    merged = Image.alpha_composite(merged, fog)
    image.paste(merged.convert("RGB"))
    add_noise(image, 18)
    return image


GENERATORS: dict[str, Callable[[], Image.Image]] = {
    "warzone.png": warzone,
    "forza_horizon_5.png": forza,
    "resident_evil_4.png": resident,
    "elden_ring.png": elden,
    "ea_sports_fc.png": fc,
    "street_fighter_6.png": fighter,
    "minecraft.png": minecraft,
    "ghost_of_tsushima.png": ghost,
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, maker in GENERATORS.items():
        image = maker()
        image.save(OUTPUT / filename, format="PNG", optimize=True)
        print(f"Generado {filename}")


if __name__ == "__main__":
    main()
