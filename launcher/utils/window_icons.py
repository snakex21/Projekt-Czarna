"""Ikony okien Tkinter i paska zadań Windows."""

import os
import platform

from ..config.paths import BASE_DIR
from .engine_access import _ensure_engine


__all__ = ["set_dialog_icon", "set_windows_taskbar_icon_for_window"]


def set_dialog_icon(window):

    """

    Ustawia ikonę dla okna dialogowego (Toplevel).

    Używa custom ikony jeśli istnieje, w przeciwnym razie domyślnej.

    Args:

        window: Okno tk.Toplevel do którego ma być dodana ikona

    """
    import tkinter as tk  # lazy: tkinter nie może być top-level (test wymusza)


    try:

        # Pobierz aktywną miejscowość

        active_location = _ensure_engine().get_active_location()

        # Najpierw szukaj w backup/{miejscowość}/

        if active_location:

            location_name = active_location[1]

            backup_icon_dir = os.path.join(BASE_DIR, "data", "locations", location_name)

            # Sprawdź czy jest custom_icon w folderze miejscowości

            custom_png = os.path.join(backup_icon_dir, 'custom_icon.png')

            custom_ico = os.path.join(backup_icon_dir, 'custom_icon.ico')

            if os.path.exists(custom_png) or os.path.exists(custom_ico):

                png_path = custom_png if os.path.exists(custom_png) else None

                ico_path = custom_ico if os.path.exists(custom_ico) else None

                if png_path and os.path.exists(png_path):

                    icon_image = tk.PhotoImage(file=png_path)

                    window.iconphoto(True, icon_image)

                    window._icon_image = icon_image

                if platform.system() == "Windows" and ico_path and os.path.exists(ico_path):

                    window.iconbitmap(ico_path)

                return

        # Jeśli miejscowość nie ma własnej ikony, użyj domyślnej feather_icon

        icon_dir = os.path.join(os.path.dirname(__file__), 'assets')

        png_path = os.path.join(icon_dir, 'feather_icon.png')

        ico_path = os.path.join(icon_dir, 'feather_icon.ico')

        if os.path.exists(png_path):

            icon_image = tk.PhotoImage(file=png_path)

            window.iconphoto(True, icon_image)

            # Zachowaj referencję aby uniknąć garbage collection

            window._icon_image = icon_image

        # Dla Windows, spróbuj też ICO

        if platform.system() == "Windows":

            if os.path.exists(ico_path):

                window.iconbitmap(ico_path)

    except Exception as e:

        print(f"⚠️ Nie udało się ustawić ikony okna: {e}")


def set_windows_taskbar_icon_for_window(window, ico_path):

    """

    Ustawia ikonę dla paska zadań Windows używając Windows API.

    Używa multi-size ICO dla najlepszej jakości.

    Args:

        window: Okno Tkinter (główne lub Toplevel)

        ico_path: Ścieżka do pliku ICO

    """

    if platform.system() != "Windows" or not os.path.exists(ico_path):

        return

    try:

        import ctypes

        # Stałe Windows API

        GCLP_HICON = -14

        GCLP_HICONSM = -34

        WM_SETICON = 0x0080

        ICON_SMALL = 0

        ICON_BIG = 1

        IMAGE_ICON = 1

        LR_LOADFROMFILE = 0x0010

        LR_DEFAULTSIZE = 0x0040

        # Pobierz handle okna

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

        if not hwnd:

            hwnd = window.winfo_id()

        # Załaduj małą ikonę (16x16 lub 32x32 w zależności od DPI)

        hicon_small = ctypes.windll.user32.LoadImageW(

            None,

            ico_path,

            IMAGE_ICON,

            16,

            16,

            LR_LOADFROMFILE

        )

        # Załaduj dużą ikonę (używa największego rozmiaru z ICO)

        hicon_big = ctypes.windll.user32.LoadImageW(

            None,

            ico_path,

            IMAGE_ICON,

            0,

            0,

            LR_LOADFROMFILE | LR_DEFAULTSIZE

        )

        if hicon_small:

            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

            try:

                ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon_small)

            except:

                pass

        if hicon_big:

            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)

            try:

                ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICON, hicon_big)

            except:

                pass

    except Exception as e:

        print(f"⚠️ Nie udało się ustawić ikony paska zadań: {e}")
