import cv2
import numpy as np
import matplotlib.pyplot as plt

# --- KONFIGURACJA ---
NAZWA_PLIKU = "mapa.jpg"
KOLOR_RGB = [255, 200, 100]  # Złoty/Pomarańczowy
INTENSYWNOSC = 0.4           # Przezroczystość (0.4 = 40%)
# ---------------------

# Zmienne globalne
points = []
img_rgb = None
original_rgb = None
ax = None
fig = None
im_display = None

def apply_polygon_color():
    global img_rgb, points
    
    if len(points) < 3:
        print("Za mało punktów, żeby stworzyć obszar!")
        return

    print("Przetwarzanie obszaru...")
    
    # Konwersja punktów na format numpy
    pts = np.array(points, np.int32)
    pts = pts.reshape((-1, 1, 2))

    # 1. Tworzymy maskę wielokąta
    h, w = img_rgb.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [pts], 255) # 255 = biały w środku wielokąta

    # 2. Przygotowanie warstw do mieszania
    # Normalizacja obrazu i koloru do zakresu 0.0 - 1.0
    roi = original_rgb.astype(float) / 255.0
    color_norm = np.array(KOLOR_RGB) / 255.0
    
    # Warstwa pełnego koloru
    colored_layer = np.ones_like(roi)
    # Wypełniamy ją kolorem, ale na razie wszędzie
    colored_layer[:] = color_norm

    # 3. MNOŻENIE (Multiply)
    # Wynik = Mapa * Kolor
    multiplied = roi * colored_layer

    # 4. Mieszanie z przezroczystością (Alpha Blending)
    # Wynik = (Pomnożony * Intensywność) + (Oryginał * (1-Intensywność))
    blended = (multiplied * INTENSYWNOSC) + (roi * (1.0 - INTENSYWNOSC))
    
    # 5. Aplikacja tylko tam, gdzie maska (czyli wewnątrz wielokąta)
    final_img = original_rgb.copy()
    
    # Skomplikowana operacja NumPy: zamieniamy piksele tam gdzie maska > 0
    # Konwertujemy blended z powrotem do uint8 (0-255)
    blended_uint8 = (np.clip(blended, 0, 1) * 255).astype(np.uint8)
    
    # Kopiujemy piksele z blended_uint8 do final_img w miejscach maski
    mask_bool = mask > 0
    final_img[mask_bool] = blended_uint8[mask_bool]

    # Aktualizacja wyświetlania
    img_rgb = final_img
    im_display.set_data(img_rgb)
    fig.canvas.draw()
    
    # Reset punktów, żeby można było rysować kolejny obszar
    points = []
    print("Gotowe! Możesz rysować kolejny obszar lub zapisać ('s').")

def onclick(event):
    # Ignoruj narzędzia zoom/pan
    if fig.canvas.toolbar.mode != '': return
    if event.xdata is None or event.ydata is None: return

    # Lewy przycisk: Dodaj punkt
    if event.button == 1:
        ix, iy = int(event.xdata), int(event.ydata)
        points.append([ix, iy])
        
        # Rysuj kropkę i linię pomocniczą
        ax.plot(ix, iy, 'ro', markersize=2)
        if len(points) > 1:
            prev = points[-2]
            ax.plot([prev[0], ix], [prev[1], iy], 'r-', linewidth=1)
        
        fig.canvas.draw()
        print(f"Punkt: {ix}, {iy}")

    # Prawy przycisk: Zamknij obszar i pokoloruj
    elif event.button == 3:
        apply_polygon_color()

def onkey(event):
    if event.key == 's':
        save_img = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite("mapa_obrysowana.png", save_img)
        print("ZAPISANO: mapa_obrysowana.png")
        plt.title("ZAPISANO!")
        fig.canvas.draw()
    elif event.key == 'z':
        # Cofnij ostatni punkt (opcja 'z')
        if len(points) > 0:
            points.pop()
            print("Cofnięto punkt. (Odświeżenie widoku wymaga restartu rysowania w tej wersji, sorki!)")
            # W matplotlib proste cofanie rysowania linii jest trudne bez przerysowania całego obrazka
            # więc ta funkcja w tej prostej wersji usuwa tylko punkt z pamięci logicznej

def main():
    global img_rgb, original_rgb, ax, fig, im_display

    img_bgr = cv2.imread(NAZWA_PLIKU)
    if img_bgr is None:
        print("Błąd pliku!")
        return

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    original_rgb = img_rgb.copy() # Kopia oryginału

    fig, ax = plt.subplots(figsize=(12, 8))
    plt.title("LPM: Stawiaj punkty | PPM: Zamknij i Pokoloruj | 's': Zapisz")
    
    im_display = ax.imshow(img_rgb)
    
    fig.canvas.mpl_connect('button_press_event', onclick)
    fig.canvas.mpl_connect('key_press_event', onkey)

    print("--- INSTRUKCJA ---")
    print("1. Klikaj LEWYM przyciskiem wzdłuż granicy gminy (obrysuj ją).")
    print("2. Używaj ZOOMu (lupy), żeby stawiać punkty precyzyjnie.")
    print("3. Jak skończysz obrys, kliknij PRAWYM przyciskiem myszy.")
    print("4. Obszar w środku zostanie pokolorowany.")
    print("5. Wciśnij 's' żeby zapisać.")
    
    plt.show()

if __name__ == "__main__":
    main()