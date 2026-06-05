"""Obsługa listy miejscowości i aktywnej lokalizacji w launcherze."""

import threading


def refresh_locations(app, get_all_locations, set_active_location):
    """Odświeża listę miejscowości w menu rozwijanym."""
    force = getattr(app, "_location_refresh_force", False)
    if app._refresh_pending and not force:
        return

    if app._cached_locations and not force:
        try:
            app._refresh_pending = True
            locations = app._cached_locations
            location_names = [loc[1] for loc in locations]
            current_values = app.location_combo['values']
            if tuple(current_values) == tuple(location_names):
                return
            app.location_combo['values'] = location_names
            active_location = next((loc for loc in locations if loc[5]), None)
            if active_location:
                app.location_var.set(active_location[1])
            elif location_names:
                app.location_var.set(location_names[0])
            else:
                app.location_var.set("(brak miejscowości)")
        finally:
            app._refresh_pending = False
            app._location_refresh_force = False
        return

    try:
        app._refresh_pending = True
        locations = get_all_locations()
        app._cached_locations = locations
        location_names = [loc[1] for loc in locations]
        app.location_combo['values'] = location_names
        active_location = next((loc for loc in locations if loc[5]), None)
        if active_location:
            app.location_var.set(active_location[1])
        elif location_names:
            app.location_var.set(location_names[0])
            threading.Thread(target=lambda: set_active_location(locations[0][0]), daemon=True).start()
        else:
            app.location_var.set("(brak miejscowości)")
    finally:
        app._refresh_pending = False
        app._location_refresh_force = False


def on_location_selected(app, get_all_locations, set_active_location, refresh_data_files=None):
    """Obsługuje zmianę wybranej miejscowości."""
    selected_name = app.location_var.get()
    if not selected_name or selected_name == "(brak miejscowości)":
        return

    locations = app._cached_locations if app._cached_locations else get_all_locations()
    for loc in locations:
        if loc[1] == selected_name:
            def _change_location():
                try:
                    set_active_location(loc[0])
                    if refresh_data_files is not None:
                        refresh_data_files()
                    app.process_mgr.enqueue_event('location_changed', selected_name, None)
                except Exception as e:
                    print(f"❌ Błąd zmiany lokacji: {e}")
                    app.process_mgr.enqueue_event('location_error', None, str(e))

            threading.Thread(target=_change_location, daemon=True).start()
            break


def open_location_manager(app):
    """Otwiera okno zarządzania miejscowościami."""
    from ..ui.location_manager import LocationManager

    manager = LocationManager(app)
    app.wait_window(manager)
    app.after(50, lambda: force_refresh_locations(app))


def open_database_wizard(app):
    """Otwiera narzędzie zarządzania bazą danych PostgreSQL."""
    from ..ui.database_wizard import DatabaseWizard

    wizard = DatabaseWizard(app)
    app.wait_window(wizard)
    app.after(50, lambda: force_refresh_locations(app))


def force_refresh_locations(app):
    app._location_refresh_force = True
    app.refresh_locations()
