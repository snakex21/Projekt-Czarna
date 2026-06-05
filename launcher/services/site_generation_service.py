"""Orkiestracja odświeżania statycznych plików strony dla aktywnej miejscowości."""


def refresh_html_pages(get_active_location, generate_location_config_js, apply_homepage_template) -> bool:
    """Generuje location-config.js i stosuje szablon strony aktywnej miejscowości."""
    active_location = get_active_location()
    if not active_location:
        return False

    generate_location_config_js()
    template = active_location[6] if len(active_location) > 6 else "standardowy"
    apply_homepage_template(template)
    print(f"✓ Automatycznie zaktualizowano dane miejscowości: {active_location[1]}")
    return True
