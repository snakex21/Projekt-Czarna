
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.backends.backend_pdf import PdfPages
import json
import os
import io
from datetime import datetime

# Ścieżki do danych (zakładając strukturę katalogów)
# backend/utils/pdf_generator.py → 2 poziomy w górę = root projektu
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BASE_DIR, "data", "locations", "Czarna") # Domyślna lokalizacja

import textwrap

def find_owner_by_house(house_number, owner_data):
    """Znajduje dane właściciela na podstawie numeru domu."""
    if not house_number:
        return None
    
    house_str = str(house_number).strip().lower()
    for key, data in owner_data.items():
        if data is None: continue 
        if str(data.get("houseNumber", "")).strip().lower() == house_str:
            return data
    return None

def find_owner_for_person(person, owner_data):
    """Znajduje protokół właściciela dla osoby.

    Najpierw używa klucza protokołu, bo numer domu w genealogii może oznaczać
    dom urodzenia/zamieszkania osoby i nie musi być tym samym numerem, który
    jest wpisany w protokole katastralnym. Dopiero awaryjnie wracamy do
    dopasowania po numerze domu.
    """
    if not owner_data:
        return None

    protocol_key = person.get("protocolKey") or person.get("protokolKey")
    if protocol_key:
        direct = owner_data.get(str(protocol_key))
        if direct:
            return direct

        protocol_key_norm = str(protocol_key).strip().lower()
        for key, data in owner_data.items():
            if data is None:
                continue
            if str(key).strip().lower() == protocol_key_norm:
                return data

    return find_owner_by_house(person.get("houseNumber"), owner_data)

def parse_plots(owner_data):
    """Parsuje listę działek z formatu JSON owner_data, zwracając słownik numer -> typ."""
    plots = {} # numer -> typ (building/agricultural)
    if not owner_data: return {}
    
    def extract_num(plot_entry):
        if not plot_entry: return None
        if isinstance(plot_entry, str):
            return plot_entry.strip()
        elif isinstance(plot_entry, dict):
            num = plot_entry.get("numerator")
            den = plot_entry.get("denominator")
            if den:
                return f"{num}/{den}"
            return str(num)
        return None

    # Priorytet dla budowlanych (jeśli działka jest tu i tu - choć nie powinna)
    for p in owner_data.get("realagriculturalPlots", []):
        num = extract_num(p)
        if num: plots[num] = 'agricultural'
        
    for p in owner_data.get("realbuildingPlots", []):
        num = extract_num(p)
        if num: plots[num] = 'building'
    
    return plots

def extract_geometry_points(parcel_data):
    """Zwraca (punkty, typ) w układzie matplotlib (x=lon, y=lat).

    Obsługuje dwa formaty danych używane w projekcie:
    - stary JSON: [lat, lon] albo [[lat, lon], ...]
    - GeoJSON z bazy: {type: Point/Polygon/LineString, coordinates: [lon, lat]}
    """
    if not parcel_data:
        return [], None

    geo = parcel_data.get("geometria")
    if not geo:
        return [], None

    if isinstance(geo, dict):
        geo_type = geo.get("type")
        coords = geo.get("coordinates") or []
        if geo_type == "Point" and len(coords) >= 2:
            return [(coords[0], coords[1])], "point"
        if geo_type == "Polygon" and coords:
            ring = coords[0] or []
            return [(pt[0], pt[1]) for pt in ring if len(pt) >= 2], "polygon"
        if geo_type == "MultiPolygon" and coords and coords[0]:
            ring = coords[0][0] or []
            return [(pt[0], pt[1]) for pt in ring if len(pt) >= 2], "polygon"
        if geo_type in ("LineString", "MultiLineString") and coords:
            line = coords[0] if geo_type == "MultiLineString" else coords
            return [(pt[0], pt[1]) for pt in line if len(pt) >= 2], "line"
        return [], None

    if isinstance(geo, list):
        # Punkt w starym formacie: [lat, lon]
        if len(geo) >= 2 and isinstance(geo[0], (float, int)) and isinstance(geo[1], (float, int)):
            return [(geo[1], geo[0])], "point"

        # Wielokąt w starym formacie: [[lat, lon], ...]
        if geo and isinstance(geo[0], list) and geo[0] and isinstance(geo[0][0], (float, int)):
            return [(pt[1], pt[0]) for pt in geo if len(pt) >= 2], "polygon"

        # Zagnieżdżony wielokąt: [[[lat, lon], ...]]
        if geo and isinstance(geo[0], list) and geo[0] and isinstance(geo[0][0], list):
            ring = geo[0]
            return [(pt[1], pt[0]) for pt in ring if len(pt) >= 2], "polygon"

    return [], None

def generate_family_pdf(person, all_persons=None, output_buffer=None):
    """
    Generuje PDF z Kartą Rodziny dla danej osoby.
    Zwraca bufor bajtów jeśli output_buffer to None.
    """
    
    # 0. Przygotowanie mapy osób
    person_map = {p['id']: p for p in all_persons} if all_persons else {}
    
    def get_name(pid):
        return person_map.get(pid, {}).get('name', f'ID {pid}')

    # 1. Ładowanie danych mapy
    try:
        with open(os.path.join(BACKUP_DIR, "owner_data_to_import.json"), "r", encoding="utf-8") as f:
            owners_db = json.load(f)
        with open(os.path.join(BACKUP_DIR, "parcels_data.json"), "r", encoding="utf-8") as f:
            parcels_geo = json.load(f)
    except Exception as e:
        print(f"Error loading map data: {e}")
        return None

    # 2. Znalezienie właściciela / protokołu
    house_num = person.get("houseNumber")
    owner_info = find_owner_for_person(person, owners_db)
    if owner_info and owner_info.get("houseNumber"):
        # Dla mapy posiadłości pokazujemy numer domu z protokołu właściciela,
        # niekoniecznie numer domu wpisany przy osobie w genealogii.
        house_num = owner_info.get("houseNumber")
    
    # 3. Wyciągnięcie działek właściciela (Dictionary: num -> type)
    owner_plots_dict = {}
    if owner_info:
        owner_plots_dict = parse_plots(owner_info)
    
    # Listy numerów do wyświetlania
    # owner_plots_keys = list(owner_plots_dict.keys())

    # 4. Inicjalizacja PDF
    if output_buffer is None:
        output_buffer = io.BytesIO()
    
    with PdfPages(output_buffer) as pdf:
        
        # --- STRONA 1: KARTA RODZINY ---
        fig = plt.figure(figsize=(8.27, 11.69), dpi=100) # A4
        fig.patch.set_facecolor('white')
        
        # 4.1 Nagłówek
        fig.text(0.5, 0.95, "KARTA RODZINY I MAJĄTKU", fontsize=24, ha='center', va='top', fontweight='bold', fontfamily='sans-serif')
        fig.text(0.5, 0.91, "GENEALOGIA CYFROWA 'CZARNA'", fontsize=10, ha='center', va='top', color='gray')
        
        line = plt.Line2D([0.1, 0.9], [0.89, 0.89], transform=fig.transFigure, color='black', linewidth=1)
        fig.add_artist(line)
        
        # 4.2 Dane Osobowe
        y_pos = 0.84
        name_str = f"{person.get('name', 'Nieznany')}"
        
        bd = person.get('birthDate') or {}
        dd = person.get('deathDate') or {}
        dates_str = f"Ur. {bd.get('year', '?')} - Zm. {dd.get('year', '?')}"
        
        fig.text(0.1, y_pos, name_str, fontsize=18, fontweight='bold', color='#2c3e50')
        fig.text(0.1, y_pos - 0.03, dates_str, fontsize=14, color='#7f8c8d')
        
        house_info = f"Dom Rodzinny Nr {house_num}" if house_num else "Brak danych o domu"
        fig.text(0.9, y_pos, house_info, fontsize=16, fontweight='bold', color='#e67e22', ha='right')
        
        if owner_info:
            owner_name = owner_info.get("ownerName", "Nieznany")
            fig.text(0.9, y_pos - 0.03, f"Wł. w 1882: {owner_name}", fontsize=10, color='#7f8c8d', ha='right')

        # 4.3 Sekcja Relacji (Rozbudowana)
        y_pos -= 0.09
        fig.text(0.1, y_pos, "Drzewo Genealogiczne (Najbliżsi):", fontsize=14, fontweight='bold')
        
        relations_lines = []
        
        # --- DZIADKOWIE ---
        grandparents = []
        # Od ojca
        fid = person.get('fatherId')
        if fid:
            fp = person_map.get(fid, {})
            if fp.get('fatherId'): grandparents.append(get_name(fp['fatherId']) + " (Ojciec Ojca)")
            if fp.get('motherId'): grandparents.append(get_name(fp['motherId']) + " (Matka Ojca)")
        # Od matki
        mid = person.get('motherId')
        if mid:
            mp = person_map.get(mid, {})
            if mp.get('fatherId'): grandparents.append(get_name(mp['fatherId']) + " (Ojciec Matki)")
            if mp.get('motherId'): grandparents.append(get_name(mp['motherId']) + " (Matka Matki)")
            
        if grandparents:
            relations_lines.append(f"• Dziadkowie: {', '.join(grandparents)}")
        else:
            relations_lines.append("• Dziadkowie: Brak danych")

        # --- RODZICE ---
        parents_list = []
        if fid: parents_list.append(get_name(fid))
        if mid: parents_list.append(get_name(mid))
        if parents_list:
            relations_lines.append(f"• Rodzice: {', '.join(parents_list)}")
        else:
            relations_lines.append("• Rodzice: Brak danych")

        # --- MAŁŻONKOWIE ---
        spouses_list = []
        for sid in person.get('spouseIds', []):
            spouses_list.append(get_name(sid))
        if spouses_list:
            relations_lines.append(f"• Małżeństwa: {', '.join(spouses_list)}")
            
        # --- RODZEŃSTWO ---
        siblings_list = []
        if fid or mid:
            for p in all_persons or []:
                if p['id'] == person.get('id'): continue
                # Wspólny ojciec lub wspólna matka
                shares_father = fid and p.get('fatherId') == fid
                shares_mother = mid and p.get('motherId') == mid
                if shares_father or shares_mother:
                    siblings_list.append(p.get('name', 'Nieznany'))
        
        if siblings_list:
             # Limit
             label = f"• Rodzeństwo ({len(siblings_list)}): "
             s_str = ", ".join(siblings_list[:6])
             if len(siblings_list) > 6: s_str += "..."
             relations_lines.append(label + s_str)
        else:
             relations_lines.append("• Rodzeństwo: Brak danych")

        # --- DZIECI ---
        children_list = []
        if all_persons:
            pid = person.get('id')
            for p in all_persons:
                if p.get('fatherId') == pid or p.get('motherId') == pid:
                    children_list.append(p.get('name'))
        
        if children_list:
            children_str = ", ".join(children_list[:6])
            if len(children_list) > 6: children_str += f", ... (+{len(children_list)-6})"
            relations_lines.append(f"• Dzieci ({len(children_list)}): {children_str}")
        else:
            relations_lines.append("• Dzieci: Brak wpisów")

        # Rysowanie tekstu relacji
        y_text_start = y_pos - 0.04
        for line_text in relations_lines:
            wrapped = textwrap.wrap(line_text, width=95)
            for w_line in wrapped:
                fig.text(0.1, y_text_start, w_line, fontsize=10, va='top')
                y_text_start -= 0.018
        
        # Notatki
        if person.get('notes') and y_text_start > 0.60:
            clean_notes = person.get('notes').replace('\n', ' ')
            wrapped_notes = textwrap.wrap(f"Notatki: {clean_notes}", width=110)
            y_text_start -= 0.010
            for wn in wrapped_notes[:2]:
                fig.text(0.1, y_text_start, wn, fontsize=9, style='italic', color='gray', va='top')
                y_text_start -= 0.014


        # 4.4 MAPA
        # [left, bottom, width, height]
        ax_map = fig.add_axes([0.1, 0.22, 0.8, 0.35]) 
        ax_map.set_title(f"Mapa Posiadłości: Dom nr {house_num}", fontsize=12, pad=10)
        ax_map.set_aspect('equal')
        ax_map.axis('off') 
        ax_map.set_xticks([])
        ax_map.set_yticks([])
        
        all_x = []
        all_y = []
        found_parcels = 0
        
        # Kolory
        COLOR_BUILDING = '#e74c3c'  # Czerwony
        COLOR_AGRI = '#f1c40f'      # Żółty/Złoty
        COLOR_OTHER = '#95a5a6'     # Szary
        
        owned_polys = []
        
        # Rysowanie własnych działek
        for key, parcel_data in parcels_geo.items():
            if parcel_data is None: continue 
            raw_num = key.split('_')[0]
            
            # Sprawdź czy to nasza działka
            p_type = owner_plots_dict.get(raw_num)
            
            coords, geom_kind = extract_geometry_points(parcel_data)

            if coords:
                if p_type: # Jeśli jest w słowniku to jest własna
                    color = COLOR_BUILDING if p_type == 'building' else COLOR_AGRI
                    if geom_kind == "point":
                        ax_map.scatter([coords[0][0]], [coords[0][1]], s=90, c=color, edgecolors='black', linewidths=1.0, zorder=8)
                    elif geom_kind == "line":
                        ax_map.plot([pt[0] for pt in coords], [pt[1] for pt in coords], color=color, linewidth=2.0, zorder=6)
                    else:
                        poly = Polygon(coords, closed=True, facecolor=color, edgecolor='black', alpha=0.9, zorder=5)
                        ax_map.add_patch(poly)
                        owned_polys.append(poly)
                    all_x.extend([pt[0] for pt in coords])
                    all_y.extend([pt[1] for pt in coords])
                    found_parcels += 1
                    
                    # Oznaczanie numeru domu na działce budowlanej
                    if p_type == 'building' and house_num:
                        # Obliczamy centroid / pozycję punktu
                        cx = sum([pt[0] for pt in coords]) / len(coords)
                        cy = sum([pt[1] for pt in coords]) / len(coords)
                        ax_map.text(cx, cy, str(house_num), fontsize=8, color='white', ha='center', va='center', fontweight='bold', zorder=10)

        # Ustalanie widoku (RESTORED LOGIC)
        if all_x and all_y:
            margin_x = (max(all_x) - min(all_x)) * 1.0 
            margin_y = (max(all_y) - min(all_y)) * 1.0
            if margin_x < 0.002: margin_x = 0.002
            if margin_y < 0.002: margin_y = 0.002
            
            view_xlim = (min(all_x) - margin_x, max(all_x) + margin_x)
            view_ylim = (min(all_y) - margin_y, max(all_y) + margin_y)
            
            ax_map.set_xlim(view_xlim)
            ax_map.set_ylim(view_ylim)
            
            # TŁO (RESTORED LOGIC)
            for key, parcel_data in parcels_geo.items():
                if parcel_data is None: continue
                raw_num = key.split('_')[0]
                if raw_num in owner_plots_dict: continue 
                
                coords, geom_kind = extract_geometry_points(parcel_data)
                 
                if coords:
                    cx, cy = coords[0]
                    if view_xlim[0] <= cx <= view_xlim[1] and view_ylim[0] <= cy <= view_ylim[1]:
                        if geom_kind == "point":
                            ax_map.scatter([cx], [cy], s=18, c='#bdc3c7', edgecolors='none', alpha=0.35, zorder=1)
                        elif geom_kind == "line":
                            ax_map.plot([pt[0] for pt in coords], [pt[1] for pt in coords], color='#bdc3c7', linewidth=0.4, alpha=0.5, zorder=1)
                        else:
                            poly = Polygon(coords, closed=True, facecolor='#ecf0f1', edgecolor='#bdc3c7', linewidth=0.5, alpha=0.5, zorder=1)
                            ax_map.add_patch(poly)

            # --- LEGENDA MAPY ---
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], marker='s', color='w', label='Działki Budowlane', markerfacecolor=COLOR_BUILDING, markersize=10, markeredgecolor='black'),
                Line2D([0], [0], marker='s', color='w', label='Działki Rolne/Inne', markerfacecolor=COLOR_AGRI, markersize=10, markeredgecolor='black'),
                Line2D([0], [0], marker='$N$', color='w', label='Numer Domu', markerfacecolor='black', markeredgecolor='none', markersize=10, linestyle='None')
            ]
            ax_map.legend(handles=legend_elements, loc='upper right', fontsize=8, framealpha=0.9)
            
        else:
            ax_map.text(0.5, 0.5, "Brak danych przestrzennych (geometrii)", 
                     transform=ax_map.transAxes, ha='center', va='center', color='red')
            ax_map.axis('off')

        # 4.5 Stopka - Lista Działek
        fig.text(0.1, 0.17, f"Inwentarz Gruntów ({found_parcels} poz.):", fontsize=12, fontweight='bold')
        
        if owner_plots_dict:
            # Sortowanie numeryczne
            keys = sorted(owner_plots_dict.keys(), key=lambda x: int(x.split('/')[0]) if x.split('/')[0].isdigit() else 0)
            
            # Podział na typy w tekście
            build_nums = [k for k in keys if owner_plots_dict[k] == 'building']
            agri_nums = [k for k in keys if owner_plots_dict[k] == 'agricultural']
            
            footer_lines = []
            if build_nums: footer_lines.append(f"Budowlane: {', '.join(build_nums)}")
            if agri_nums: footer_lines.append(f"Rolne: {', '.join(agri_nums)}")
            
            full_text = " | ".join(footer_lines)

            # Większe wrapowanie
            wrapped_plots = textwrap.wrap(full_text, width=100)
            
            y_footer = 0.15
            for line in wrapped_plots:
                fig.text(0.1, y_footer, line, fontsize=10, style='italic', color='#34495e', va='top')
                y_footer -= 0.018
                if y_footer < 0.03: break
        
        fig.text(0.5, 0.02, f"Raport wygenerowany automatycznie: {datetime.now().strftime('%Y-%m-%d %H:%M')} | System 'Czarna'", fontsize=8, ha='center', color='#bdc3c7')

        pdf.savefig(fig)
        plt.close()
    
    output_buffer.seek(0)
    return output_buffer
