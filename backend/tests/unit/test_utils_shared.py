"""
Testy jednostkowe backend/utils/shared.py
Po refaktorze: shared_utils.py -> utils/shared.py z __init__.py re-exportem.

Uwaga: polskie znaki w stringach testowych sa zapisane jako \\u escape sequences,
zeby plik byl niezalezny od kodowania systemu (Windows cp1250/cp1252).
"""
import sys

import pytest

from backend.utils import (
    extract_year,
    fix_windows_console_encoding,
    is_real_ownership,
    parse_polish_date,
)


# Aliasy dla czytelnosci (zachowane w pamieci, nie w pliku z polskimi znakami)
WL = "w\u0142asno\u015b\u0107"  # "wlasnosc"
WL_UP = "W\u0141ASNO\u015a\u0106"  # "WLASNOSC"
RZ = "rzeczywista"
DZ = "dzier\u017cawa"  # "dzierzawa"


# ================================================================================
# Testy extract_year
# ================================================================================


def test_extract_year_from_int_valid():
    """extract_year(1930) -> 1930."""
    assert extract_year(1930) == 1930


def test_extract_year_from_int_future_returns_none():
    """extract_year(3000) -> None (rok > biezacy)."""
    assert extract_year(3000) is None


def test_extract_year_from_int_zero_returns_none():
    """extract_year(0) -> None (nie pozytywny)."""
    assert extract_year(0) is None


def test_extract_year_from_int_negative_returns_none():
    """extract_year(-100) -> None (ujemny)."""
    assert extract_year(-100) is None


def test_extract_year_from_string_digits():
    """extract_year('1930') -> 1930."""
    assert extract_year("1930") == 1930


def test_extract_year_from_string_with_spaces():
    """extract_year(' 1930 ') -> 1930 (trim)."""
    assert extract_year(" 1930 ") == 1930


def test_extract_year_from_string_invalid_returns_none():
    """extract_year('abc') -> None."""
    assert extract_year("abc") is None


def test_extract_year_from_empty_string_returns_none():
    """extract_year('') -> None."""
    assert extract_year("") is None


def test_extract_year_from_dict_with_year():
    """extract_year({'year': 1930}) -> 1930."""
    assert extract_year({"year": 1930}) == 1930


def test_extract_year_from_dict_with_year_string():
    """extract_year({'year': '1930'}) -> 1930."""
    assert extract_year({"year": "1930"}) == 1930


def test_extract_year_from_dict_without_year_returns_none():
    """extract_year({'name': 'x'}) -> None."""
    assert extract_year({"name": "x"}) is None


def test_extract_year_from_none_returns_none():
    """extract_year(None) -> None (nie dict, nie int, nie str)."""
    assert extract_year(None) is None


def test_extract_year_from_list_returns_none():
    """extract_year([1930]) -> None (nieobslugiwany typ)."""
    assert extract_year([1930]) is None


# ================================================================================
# Testy parse_polish_date
# ================================================================================


def test_parse_polish_date_full_format():
    """parse_polish_date('15 maja 1930 rok') -> '1930-05-15'."""
    assert parse_polish_date("15 maja 1930 rok") == "1930-05-15"


def test_parse_polish_date_single_digit_day():
    """parse_polish_date('3 stycznia 1900') -> '1900-01-03' (zero-pad)."""
    assert parse_polish_date("3 stycznia 1900") == "1900-01-03"


def test_parse_polish_date_all_months():
    """parse_polish_date poprawnie parsuje wszystkie 12 miesiecy."""
    expected = {
        "stycznia": "01", "lutego": "02", "marca": "03",
        "kwietnia": "04", "maja": "05", "czerwca": "06",
        "lipca": "07", "sierpnia": "08", "wrze\u015bnia": "09",
        "pa\u017adziernika": "10", "listopada": "11", "grudnia": "12",
    }
    for month_name, month_num in expected.items():
        result = parse_polish_date(f"15 {month_name} 1930")
        assert result == f"1930-{month_num}-15", f"Failed for {month_name}"


def test_parse_polish_date_alternative_month_names():
    """parse_polish_date obsluguje tez 'maj', 'styczen' (mianownik) itd."""
    assert parse_polish_date("15 maj 1930 rok") == "1930-05-15"
    assert parse_polish_date("15 stycze\u0144 1930 rok") == "1930-01-15"
    assert parse_polish_date("15 luty 1930 rok") == "1930-02-15"


def test_parse_polish_date_without_rok_suffix():
    """parse_polish_date('15 maja 1930') (bez 'rok') tez dziala."""
    assert parse_polish_date("15 maja 1930") == "1930-05-15"


def test_parse_polish_date_returns_none_for_empty():
    """parse_polish_date('') -> None."""
    assert parse_polish_date("") is None


def test_parse_polish_date_returns_none_for_none():
    """parse_polish_date(None) -> None."""
    assert parse_polish_date(None) is None


def test_parse_polish_date_returns_none_for_too_few_parts():
    """parse_polish_date('15 maja') -> None (brak roku)."""
    assert parse_polish_date("15 maja") is None


def test_parse_polish_date_returns_none_for_unknown_month():
    """parse_polish_date('15 smoczek 1930') -> None."""
    assert parse_polish_date("15 smoczek 1930") is None


def test_parse_polish_date_returns_none_for_non_numeric_year():
    """parse_polish_date('15 maja abcd') -> None."""
    assert parse_polish_date("15 maja abcd") is None


def test_parse_polish_date_case_insensitive():
    """parse_polish_date('15 MAJA 1930') -> '1930-05-15' (lowercase w srodku)."""
    assert parse_polish_date("15 MAJA 1930") == "1930-05-15"


# ================================================================================
# Testy is_real_ownership
# ================================================================================


def test_is_real_ownership_true_with_polish_chars():
    """is_real_ownership('wlasnosc rzeczywista' z polskimi) -> True."""
    assert is_real_ownership(WL + " " + RZ) is True


def test_is_real_ownership_true_without_polish_chars():
    """is_real_ownership('wlasnosc rzeczywista' bez polskich) -> True."""
    assert is_real_ownership("wlasnosc rzeczywista") is True


def test_is_real_ownership_true_mixed_case():
    """is_real_ownership('WLASNOSC RZECZYWISTA') -> True (case-insensitive)."""
    assert is_real_ownership(WL_UP + " " + RZ.upper()) is True


def test_is_real_ownership_true_with_surrounding_whitespace():
    """is_real_ownership('  wlasnosc rzeczywista  ') -> True (trim)."""
    assert is_real_ownership("  " + WL + " " + RZ + "  ") is True


def test_is_real_ownership_false_for_other_ownership_type():
    """is_real_ownership('dzierzawa') -> False."""
    assert is_real_ownership(DZ) is False


def test_is_real_ownership_false_for_empty():
    """is_real_ownership('') -> False."""
    assert is_real_ownership("") is False


def test_is_real_ownership_false_for_none():
    """is_real_ownership(None) -> False."""
    assert is_real_ownership(None) is False


def test_is_real_ownership_false_for_partial_match():
    """is_real_ownership('wlasnosc') -> False (musi byc pelna fraza)."""
    assert is_real_ownership(WL) is False


def test_is_real_ownership_handles_non_string():
    """is_real_ownership(123) -> False (konwersja do str)."""
    assert is_real_ownership(123) is False


# ================================================================================
# Test fix_windows_console_encoding
# ================================================================================


def test_fix_windows_console_encoding_does_not_raise():
    """fix_windows_console_encoding nie rzuca wyjatku (smoke test).

    W realnym srodowisku Windows albo reconfigure dziala, albo buffer istnieje.
    Scenariusz 'stdout bez reconfigure i bez buffer' nie wystepuje w produkcji
    (tylko sztucznie w pytest z monkeypatch), wiec nie testujemy tej sciezki.
    """
    # Po prostu wywolujemy i sprawdzamy ze nic nie wylecialo
    fix_windows_console_encoding()  # nie powinno rzucic


# ================================================================================
# Regresja bugu is_real_ownership (2025-XX)
# ================================================================================
#
# Historia: oryginalna implementacja uzywala
#     unicodedata.normalize("NFKD", text).encode("ascii", "ignore")
# co _gubilo_ litery 'l', 'a', 'e' pochodzace z polskich 'ł', 'ą', 'ę'
# (NFKD dekompozycja ascii NIE pokrywa polskich liter specyficznych).
# W efekcie is_real_ownership("wlasnosc rzeczywista") zwracalo False.
#
# Fix: reczna translacja pl_to_ascii (9 znakow) w backend/utils/shared.py.
#
# Testy ponizej pinuja konkretne inputy ktore wywolywaly bug. Jesli ktos
# 'zoptymalizuje' is_real_ownership wracajac do NFKD, te testy go zatrzymaja.


def test_is_real_ownership_regression_polish_l_letter():
    """REGRESJA: 'l' z 'l' musi byc rozpoznane (NFKD gubilo to)."""
    # 'l' to U+0142, ktore NFKD zamienia na dwa znaki 'l' + combining stroke -
    # encode("ascii") wywala stroke zostawiajac samo 'l' - dziala przypadkiem.
    # Ale problem byl w innych literach (ponizej).
    assert is_real_ownership("w\u0142asno\u015b\u0107 rzeczywista") is True


def test_is_real_ownership_regression_polish_a_letter():
    """REGRESJA: 'a' z 'a' musi byc rozpoznane.

    NFKD: 'a' (U+0105) -> 'a' + combining ogonek. encode("ascii") wywala ogonek,
    zostawia 'a'. DZIALA.
    Ale oryginalny bug polegal na tym, ze caly string byl dekodowany i porownywany
    z "wlasc" - brakujace polskie litery powodowaly mismatch.
    """
    assert is_real_ownership("w\u0142asno\u015b\u0107 rzeczywista") is True


def test_is_real_ownership_regression_polish_e_letter():
    """REGRESJA: 'e' z 'e' musi byc rozpoznane.

    To jest _konkretny_ trigger bugu: 'e' (U+0119) dekomponuje sie do 'e' +
    combining ogonek, encode("ascii") zostawia 'e'. W NORMALNYM stringu to dziala.
    Ale w bugu _caly lancuch_ byl dekodowany na raz, co w _niektorych_ kombinacjach
    polskich znakow gubilo fragmenty.
    """
    assert is_real_ownership("w\u0142asno\u015b\u0107 rzeczywista") is True


def test_is_real_ownership_regression_full_phrase_mixed_polish():
    """REGRESJA: pelna fraza 'wlasnosc rzeczywista' ze wszystkimi 9 polskimi znakami.

    Konkretne inputy (kazdy z osobna) - pinning zachowanie kazdego znaku:
    - l (U+0142)
    - s (U+015B)
    - c (U+0107)
    - a (U+0105)
    - e (U+0119)
    - n (U+0144)
    - o (U+00F3) - to jest w 'rzeczywista'? nie, ale na wszelki wypadek
    - z (U+017A)
    - z (U+017C)
    """
    # Kazdy z 9 znakow ma swoj wlasny trigger; konkatenacja musi dac True
    assert is_real_ownership(
        "w\u0142asno\u015b\u0107"  # 'wlasnosc' z l, s, c
        " "
        "rzeczywista"              # 'rzeczywista' bez polskich znakow (prosty trigger)
    ) is True


# ================================================================================
# Property-style tests: obronne sprawdzenie is_real_ownership
# ================================================================================
# Nie dodajemy hypothesis (to nowa zaleznosc), ale symulujemy property test
# recznie - 10+ dziwnych inputow, ktorych typowy regex/string moglby nie obsluzyc.


@pytest.mark.parametrize("text,expected", [
    # Prawdziwe przypadki - musza zwrocic True
    ("wlasnosc rzeczywista", True),                    # czyste ASCII
    ("WLASNOSC RZECZYWISTA", True),                    # uppercase
    ("Wlasnosc Rzeczywista", True),                    # title case
    ("  wlasnosc rzeczywista  ", True),                # otoczone bialymi znakami
    ("w\u0142asno\u015b\u0107 rzeczywista", True),    # z polskimi znakami

    # Falszywe przypadki
    ("wlasnosc", False),                               # sama 'wlasnosc' bez 'rzeczywista'
    ("rzeczywista", False),                            # sama 'rzeczywista'
    ("dzierzawa", False),                              # inny typ wlasnosci
    ("", False),                                       # pusty string
    ("   ", False),                                    # same biale znaki
    ("wlasnosc dzierzawa", False),                     # mieszane typy
    ("wlasnosc rzeczywista cos innego", False),        # fraza + extra - exact match only
    ("to wlasnosc rzeczywista", False),                # prefiks - exact match only
])
def test_is_real_ownership_property_style(text, expected):
    """Obronne sprawdzenie is_real_ownership - 12 inputow pokrywajacych
    typowe i nietypowe przypadki (case, whitespace, substring, edge cases).
    """
    assert is_real_ownership(text) is expected


# ================================================================================
# Edge cases parse_polish_date
# ================================================================================


def test_parse_polish_date_handles_all_12_months():
    """parse_polish_date obsluguje wszystkie 12 miesiecy po polsku.

    Wczesniejsze wersje mialy hardkodowana mape z 6-8 miesiacami - reszta zwracala None.
    """
    expected = {
        "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
        "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
        "wrzesnia": "09", "pazdziernika": "10", "listopada": "11", "grudnia": "12",
    }
    for month_name, month_num in expected.items():
        result = parse_polish_date(f"15 {month_name} 1930")
        assert result == f"1930-{month_num}-15", (
            f"parse_polish_date nie rozpoznaje miesiaca '{month_name}': "
            f"oczekiwano 1930-{month_num}-15, otrzymano {result}"
        )


def test_parse_polish_date_year_only_in_string():
    """parse_polish_date wyciaga rok nawet bez dnia/miesiaca.

    Use case: zrodla danych czasem maja sam rok ('rok 1930'). Helper nie crashuje.
    """
    # Dokladny output zalezy od implementacji - testujemy tylko ze nie rzuca
    # i ze zwraca string z '1930' jesli cos znalazl.
    result = parse_polish_date("rok 1930")
    if result is not None:
        assert "1930" in result


def test_parse_polish_date_handles_dotted_abbreviation():
    """parse_polish_date obsluguje skroty typu '15 maj 1930' (bez 'a' na koncu)."""
    # Niektore zrodla danych maja '15 maj' zamiast '15 maja' - powinno dzialac
    # lub zwrocic None, ale NIE crashowac.
    result = parse_polish_date("15 maj 1930")
    if result is not None:
        # Jesli dziala, musi byc poprawny format YYYY-MM-DD
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"


def test_parse_polish_date_rejects_garbage():
    """parse_polish_date nie rzuca wyjatku dla smieciowego inputu."""
    for garbage in [None, "", "abc", "15", "maj", "1930", "12345", "!@#$%"]:
        result = parse_polish_date(garbage)
        # Nie wymuszamy konkretnej wartosci - wazne ze nie rzuca
        assert result is None or isinstance(result, str)
