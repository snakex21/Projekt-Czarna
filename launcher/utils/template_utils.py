"""Narzędzia szablonów strony głównej."""

import json
import os

from ..config.paths import HOMEPAGE_DIR, TEMPLATES_DIR
from .engine_access import _ensure_engine


__all__ = ["get_available_templates", "apply_homepage_template"]


def get_available_templates():

    """Zwraca listę dostępnych szablonów strony głównej."""

    templates = []

    if os.path.exists(TEMPLATES_DIR):

        for item in os.listdir(TEMPLATES_DIR):

            template_path = os.path.join(TEMPLATES_DIR, item)

            if os.path.isdir(template_path):

                index_path = os.path.join(template_path, "index.html")

                if os.path.exists(index_path):

                    templates.append(item)

    return templates


def apply_homepage_template(template_name):

    """

    Aplikuje wybrany szablon strony głównej.

    Args:

        template_name: Nazwa szablonu (np. 'standardowy', 'praca_inzynierska')

    Returns:

        True jeśli sukces, False w przeciwnym razie

    """

    template_path = os.path.join(TEMPLATES_DIR, template_name, "index.html")

    target_path = os.path.join(HOMEPAGE_DIR, "index.html")

    if not os.path.exists(template_path):

        print(f"❌ Szablon '{template_name}' nie istnieje")

        return False

    try:

        # Dla wszystkich szablonów - zastąp placeholdery danymi miejscowości

        active_location = _ensure_engine().get_active_location()

        if not active_location:

            print("❌ Brak aktywnej miejscowości")

            return False

        location_name = active_location[1]

        location_full_name = active_location[2] or location_name

        location_powiat = active_location[3] or "Powiat"

        location_region = active_location[4] or "Region"

        location_year = active_location[7] if len(active_location) > 7 else "1882"

        location_century = active_location[8] if len(active_location) > 8 else "XIX w."

        location_desc = active_location[9] if len(active_location) > 9 else ""

        history_p1 = active_location[10] if len(active_location) > 10 else ""

        history_p2 = active_location[11] if len(active_location) > 11 else ""

        history_p3 = active_location[12] if len(active_location) > 12 else ""

        history_photos_raw = active_location[17] if len(active_location) > 17 else "[]"

        try:

            history_photos = json.loads(history_photos_raw) if isinstance(history_photos_raw, str) else (history_photos_raw or [])

        except Exception:

            history_photos = []

        with open(template_path, 'r', encoding='utf-8') as f:

            content = f.read()

        content = content.replace('{{MIEJSCOWOSC}}', location_name)

        content = content.replace('{{MIEJSCOWOSC_PELNA}}', location_full_name)

        content = content.replace('{{POWIAT}}', location_powiat)

        content = content.replace('{{REGION}}', location_region)

        content = content.replace('{{YEAR}}', location_year)

        content = content.replace('{{WIEK}}', location_century)

        content = content.replace('{{HOMEPAGE_DESC}}', location_desc)

        content = content.replace('{{HISTORY_P1}}', history_p1)

        content = content.replace('{{HISTORY_P2}}', history_p2)

        content = content.replace('{{HISTORY_P3}}', history_p3)

        if history_photos:

            photos_html = ""

            for photo in history_photos:

                if isinstance(photo, dict):

                    src = photo.get("filename") or photo.get("src") or ""

                    caption = photo.get("caption") or ""

                    if src:

                        photos_html += f'<div class="photo-item"><img src="../assets/history_photos/{src}" alt="{caption}"><p>{caption}</p></div>\n'

                elif isinstance(photo, str):

                    photos_html += f'<div class="photo-item"><img src="../assets/history_photos/{photo}" alt=""></div>\n'

            if photos_html:

                import re

                content = re.sub(

                    r'<div class="[^"]*no-photos[^"]*"[^>]*>.*?</div>\s*</div>',

                    f'<div class="history-photos-gallery">{photos_html}</div>',

                    content,

                    flags=re.DOTALL

                )

        else:

            content = content.replace(

                'Brak zdjęć historycznych dla tej miejscowości.',

                ''

            )

        with open(target_path, 'w', encoding='utf-8') as f:

            f.write(content)

        print(f"✅ Zastosowano szablon '{template_name}' dla miejscowości: {location_full_name} ({location_year})")

        return True

    except Exception as e:

        print(f"❌ Błąd podczas aplikowania szablonu: {e}")

        import traceback

        traceback.print_exc()

        return False
