"""
Skrypt do utworzenia ikony pióra dla launchera
"""
from PIL import Image, ImageDraw
import os

def create_feather_icon():
    """Tworzy ikonę pióra w stylu minimalistycznym."""
    # Rozmiar ikony
    size = 64

    # Stwórz obrazek z białym tłem
    img = Image.new('RGB', (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Kolory - brązowy/złoty jak pióro
    feather_color = (139, 69, 19)  # Brązowy kolor pióra

    # Rysuj pióro
    # Główny trzon pióra
    shaft_width = 3
    shaft_x = size // 2
    draw.line([(shaft_x, 8), (shaft_x, size - 8)], fill=feather_color, width=shaft_width)

    # Pióra po bokach (łukowe linie)
    for i in range(12):
        y_pos = 12 + i * 3.5
        width = 6 + i * 1.8

        # Lewa strona
        draw.line([(shaft_x, y_pos), (shaft_x - width, y_pos + 2)],
                 fill=feather_color, width=2)
        # Prawa strona
        draw.line([(shaft_x, y_pos), (shaft_x + width, y_pos + 2)],
                 fill=feather_color, width=2)

    # Dolna część - mniejsze pióra
    for i in range(5):
        y_pos = 54 - i * 3
        width = 4 + i * 1.5

        draw.line([(shaft_x, y_pos), (shaft_x - width, y_pos - 2)],
                 fill=feather_color, width=1)
        draw.line([(shaft_x, y_pos), (shaft_x + width, y_pos - 2)],
                 fill=feather_color, width=1)

    # Zapisz obrazek
    output_dir = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'feather_icon.png')
    img.save(output_path, 'PNG')
    print(f"✅ Ikona pióra utworzona: {output_path}")

    # Utwórz również wersję ICO dla Windows
    ico_path = os.path.join(output_dir, 'feather_icon.ico')
    img.save(ico_path, format='ICO', sizes=[(64, 64), (32, 32), (16, 16)])
    print(f"✅ Ikona ICO utworzona: {ico_path}")

    return output_path, ico_path

if __name__ == '__main__':
    create_feather_icon()
