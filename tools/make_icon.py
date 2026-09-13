"""Dessine l'icone de l'application.

Le motif reprend ce que le nom raconte: un profil de plongee qui descend,
traverse une **thermocline** — la bande orange ou l'eau change brutalement de
temperature — puis remonte.

    python tools/make_icon.py

Produit `thermocline/resources/thermocline.png` (1024 px) et `.ico`
multi-tailles pour Windows. L'icone macOS `.icns` est fabriquee au moment de
la compilation par `iconutil`, qui n'existe que la-bas.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = ROOT / "thermocline" / "resources"

SIZE = 1024

# Les couleurs sont celles du theme sombre de l'application.
DEEP = (15, 20, 27)
WATER_TOP = (16, 78, 110)
WATER_BOTTOM = (10, 32, 50)
PROFILE = (56, 189, 248)
THERMOCLINE = (251, 146, 60)

#: Tailles rangees dans le fichier .ico, de la vignette au grand format.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    return mask


def water_background(size: int) -> Image.Image:
    """Degrade vertical: la lumiere s'eteint avec la profondeur."""
    image = Image.new("RGB", (size, size), DEEP)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / (size - 1)
        colour = tuple(
            round(top + (bottom - top) * ratio)
            for top, bottom in zip(WATER_TOP, WATER_BOTTOM)
        )
        draw.line(((0, y), (size, y)), fill=colour)
    return image


def dive_profile(size: int) -> list[tuple[float, float]]:
    """Une descente, un temps au fond legerement remontant, une remontee."""
    points: list[tuple[float, float]] = []
    left, right = size * 0.16, size * 0.84
    surface, bottom = size * 0.22, size * 0.74

    descent_end = left + (right - left) * 0.22
    ascent_start = left + (right - left) * 0.72

    steps = 160
    for step in range(steps + 1):
        x = left + (right - left) * step / steps
        if x <= descent_end:
            progress = (x - left) / (descent_end - left)
            y = surface + (bottom - surface) * progress
        elif x <= ascent_start:
            progress = (x - descent_end) / (ascent_start - descent_end)
            # Un fond qui remonte doucement, avec un leger relief.
            y = bottom - (bottom - surface) * 0.18 * progress
            y -= math.sin(progress * math.pi * 2) * size * 0.012
        else:
            progress = (x - ascent_start) / (right - ascent_start)
            deep = bottom - (bottom - surface) * 0.18
            y = deep + (surface - deep) * progress**0.85
        points.append((x, y))
    return points


#: Facteur de surechantillonnage: on dessine en grand, on reduit ensuite.
SUPERSAMPLE = 4


def draw_icon(size: int = SIZE) -> Image.Image:
    """Dessine l'icone, puis la reduit: les courbes ressortent lisses."""
    big = size * SUPERSAMPLE
    image = water_background(big).convert("RGBA")

    points = dive_profile(big)
    left, right = points[0][0], points[-1][0]

    # L'aire sous la courbe, sur son propre calque pour rester translucide.
    fill = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon(
        [(left, big)] + points + [(right, big)], fill=(*PROFILE, 54)
    )
    image = Image.alpha_composite(image, fill)

    # La thermocline: une bande nette en travers de la colonne d'eau, posee
    # par-dessus l'aire pour qu'on la voie la traverser.
    band_top = big * 0.52
    band = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band)
    band_draw.rectangle(
        (0, band_top, big, band_top + big * 0.05), fill=(*THERMOCLINE, 64)
    )
    band_draw.rectangle(
        (0, band_top - big * 0.006, big, band_top + big * 0.006),
        fill=(*THERMOCLINE, 240),
    )
    image = Image.alpha_composite(image, band)

    draw = ImageDraw.Draw(image)
    draw.line(points, fill=PROFILE, width=round(big * 0.052), joint="curve")

    # Le point le plus profond, comme dans le graphique de l'application.
    deepest = max(points, key=lambda point: point[1])
    radius = big * 0.038
    draw.ellipse(
        (
            deepest[0] - radius,
            deepest[1] - radius,
            deepest[0] + radius,
            deepest[1] + radius,
        ),
        fill=(255, 255, 255),
    )

    rounded = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    rounded.paste(image, (0, 0), rounded_mask(big, round(big * 0.22)))
    return rounded.resize((size, size), Image.LANCZOS)


def draw_arrow(pointing_down: bool, size: int = 32) -> Image.Image:
    """Petit chevron pour les listes deroulantes et les compteurs.

    Qt ne dessine plus ses propres fleches des qu'une feuille de style touche
    au widget, et il ignore les triangles faits de bordures CSS: il faut donc
    lui fournir une vraie image.
    """
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = big * 0.22
    middle = big / 2
    if pointing_down:
        points = [(margin, middle - big * 0.12), (big - margin, middle - big * 0.12),
                  (middle, middle + big * 0.22)]
    else:
        points = [(margin, middle + big * 0.12), (big - margin, middle + big * 0.12),
                  (middle, middle - big * 0.22)]
    # Gris neutre: la meme image convient au theme clair et au theme sombre.
    draw.polygon(points, fill=(139, 152, 165, 255))
    return image.resize((size, size), Image.LANCZOS)


def main() -> int:
    RESOURCES.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()

    for name, down in (("arrow-down.png", True), ("arrow-up.png", False)):
        target = RESOURCES / name
        draw_arrow(down).save(target)
        print(f"  {target.relative_to(ROOT)}")

    png = RESOURCES / "thermocline.png"
    icon.save(png)
    print(f"  {png.relative_to(ROOT)}")

    ico = RESOURCES / "thermocline.ico"
    icon.save(ico, sizes=[(s, s) for s in ICO_SIZES])
    print(f"  {ico.relative_to(ROOT)}")

    # Une version 256 px sert de visuel dans le README.
    preview = ROOT / "docs" / "icone.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    icon.resize((256, 256), Image.LANCZOS).save(preview)
    print(f"  {preview.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
