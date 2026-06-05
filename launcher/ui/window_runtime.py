"""Runtime geometrii, skalowania i fokusu okna launchera."""

import ctypes
import platform
import time

from tkinter import messagebox

from launcher.config.ui_settings import set_ui_scale_setting


__all__ = ["setup_window_geometry", "apply_ui_scale", "on_window_focus"]


def setup_window_geometry(app):
        """Inteligentnie dostosowuje rozmiar okna do ekranu i DPI."""
        sw, sh = app.winfo_screenwidth(), app.winfo_screenheight()
        dpi = app.winfo_fpixels("1i")
        dpi_scale = dpi / 96
        ui_scale = max(0.85, min(float(getattr(app, 'ui_scale', 1.0) or 1.0), 2.0))

        if sw <= 1920:
            w, h = min(int(sw * 0.85), 1400), min(int(sh * 0.95), 1000)
        elif sw <= 2560:
            w, h = min(int(sw * 0.75), 1600), min(int(sh * 0.90), 1050)
        else:
            w, h = min(int(sw * 0.65), 1800), min(int(sh * 0.85), 1100)

        # Minimalny rozmiar zależy od skali UI launchera, nie od skali Windows.
        # Inaczej przy Windows 150% nawet UI 100% wymuszało zbyt duże okno.
        min_w = max(1000, int(900 * ui_scale))
        min_h = max(700, int(650 * ui_scale))
        w, h = max(w, min_w), max(h, min_h)

        # Przy bardzo dużej skali UI potrzebujemy prawie całego ekranu,
        # inaczej dolna konsola nie ma miejsca.
        if ui_scale >= 1.6:
            w = min(sw - 40, max(w, int(sw * 0.92)))
            h = min(sh - 60, max(h, int(sh * 0.92)))

        x = (sw - w) // 2
        y = (sh - h) // 2

        app.geometry(f"{w}x{h}+{x}+{y}")
        app.minsize(min_w, min_h)
        app.scale_factor = dpi_scale
        app.is_high_dpi = dpi_scale > 1.25

def apply_ui_scale(app, new_scale, restart_now=False):
        """Zapisuje skalę UI i restartuje launcher by zastosować."""
        app.ui_scale = max(0.85, min(float(new_scale), 2.0))
        if not set_ui_scale_setting(app.ui_scale):
            messagebox.showerror("Błąd", "Nie udało się zapisać ustawienia skali interfejsu.", parent=app)
            return False

        percent = int(round(app.ui_scale * 100))

        if restart_now:
            app.restart_application()
        elif messagebox.askyesno(
            "Zastosować skalę?",
            f"Nowa skala: {percent}%\n\n"
            f"Aby zobaczyć zmianę, launcher musi się zrestartować.\n"
            f"Czy restartować teraz?",
            parent=app,
        ):
            app.restart_application()
        return True

def on_window_focus(app, event=None):
        """Obsługuje zdarzenie powrotu focusu do okna (np. po alt+tab).

        Upewnia się, że okno jest zawsze na wierzchu i otrzymuje focus
        gdy użytkownik do niego wraca. Throttling zapobiega migotaniu GUI.
        """
        try:
            # Throttling - nie wykonuj częściej niż raz na 250ms (zapobiega migotaniu)
            current_time = time.time()
            if hasattr(app, '_last_focus_time'):
                time_since_last = current_time - app._last_focus_time
                if time_since_last < 0.25:  # 250ms
                    return

            app._last_focus_time = current_time

            # Przenieś okno na wierzch stosu okien
            app.lift()

            # Dla Windows - użyj Windows API aby wymusić focus
            if platform.system() == "Windows":
                try:
                    # Pobierz handle okna
                    hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
                    if not hwnd:
                        hwnd = app.winfo_id()

                    # Wymuś okno na pierwszy plan za pomocą Windows API
                    # FIX: SW_RESTORE (9) cofa maksymalizację, więc używamy go TYLKO gdy okno jest zminimalizowane
                    if app.state() == 'iconic':
                        ctypes.windll.user32.ShowWindow(hwnd, 9)

                    # Ustaw okno jako aktywne
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    # Wymuś focus na oknie
                    ctypes.windll.user32.SetFocus(hwnd)
                except:
                    # Jeśli Windows API zawiedzie, użyj standardowej metody Tkinter
                    pass

            # Wymuś focus na oknie (Tkinter)
            app.focus_force()

            # Upewnij się że okno jest widoczne i nie zminimalizowane
            if app.state() == 'iconic':
                app.deiconify()

        except:
            # Ignoruj błędy jeśli okno jest w trakcie zamykania
            pass
