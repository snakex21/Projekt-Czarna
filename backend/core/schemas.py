"""Modele Pydantic dla danych wejściowych endpointów zapisu.

Cele:
- odrzucanie złych typów (np. słownik tam, gdzie oczekiwany tekst) kodem 422
  zamiast błędu 500 z bazy,
- limity długości tekstów i liczności list,
- zgodność z frontendem: formularze wysyłają liczby jako tekst ("1882"),
  a puste pola jako "" albo null - oba warianty są akceptowane.

Nieznane pola są ignorowane (frontend wysyła np. ``marriages``).
"""
from __future__ import annotations

from typing import Annotated, Any, ClassVar, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

SHORT_TEXT = 255
LONG_TEXT = 50_000
MAX_IDS = 10_000
MAX_FEATURES = 50_000


def _empty_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


ShortText = Annotated[str, StringConstraints(max_length=SHORT_TEXT)]
LongText = Annotated[str, StringConstraints(max_length=LONG_TEXT)]
OptYear = Annotated[Optional[Annotated[int, Field(ge=0, le=3000)]], BeforeValidator(_empty_to_none)]
OptCount = Annotated[Optional[Annotated[int, Field(ge=0, le=100_000_000)]], BeforeValidator(_empty_to_none)]
# Identyfikator osoby: id z bazy (liczba) albo json_id (tekst).
PersonRef = Annotated[
    Optional[Union[int, ShortText]], BeforeValidator(_empty_to_none)
]
ObjectId = Annotated[int, Field(ge=0, le=2**53)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True, str_strip_whitespace=False)


class LoginRequest(_Input):
    username: Annotated[str, StringConstraints(max_length=128)] = ""
    password: Annotated[str, StringConstraints(max_length=1024)] = ""


class ChangePasswordRequest(_Input):
    current_password: Annotated[str, StringConstraints(max_length=1024)] = ""
    new_password: Annotated[str, StringConstraints(max_length=1024)] = ""


class OwnerIn(_Input):
    unikalny_klucz: Optional[ShortText] = None
    nazwa_wlasciciela: Optional[ShortText] = None
    numer_protokolu: Optional[ShortText] = None
    numer_domu: Optional[ShortText] = None
    genealogia: Optional[LongText] = None
    historia_wlasnosci: Optional[LongText] = None
    uwagi: Optional[LongText] = None
    wspolwlasnosc: Optional[LongText] = None
    powiazania_i_transakcje: Optional[LongText] = None
    interpretacja_i_wnioski: Optional[LongText] = None
    data_protokolu: Optional[ShortText] = None
    miejsce_protokolu: Optional[ShortText] = None
    dzialki_rzeczywiste_ids: Annotated[List[ObjectId], Field(max_length=MAX_IDS)] = []
    dzialki_protokol_ids: Annotated[List[ObjectId], Field(max_length=MAX_IDS)] = []

    OWNER_FIELDS: ClassVar[Tuple[str, ...]] = (
        "unikalny_klucz", "nazwa_wlasciciela", "numer_protokolu", "numer_domu",
        "genealogia", "historia_wlasnosci", "uwagi", "wspolwlasnosc",
        "powiazania_i_transakcje", "interpretacja_i_wnioski", "data_protokolu",
        "miejsce_protokolu",
    )

    def owner_columns(self) -> Dict[str, Any]:
        """Tylko kolumny tabeli ``wlasciciele`` jawnie podane w żądaniu."""
        sent = self.model_fields_set
        return {k: getattr(self, k) for k in self.OWNER_FIELDS if k in sent}


class ObjectUpdateIn(_Input):
    nazwa_lub_numer: Optional[ShortText] = None
    kategoria: Optional[Annotated[str, StringConstraints(max_length=64)]] = None
    # GeoJSON jako tekst (format bazy) albo obiekt (serializowany do tekstu).
    geometria: Optional[Union[Annotated[str, StringConstraints(max_length=5_000_000)], Dict[str, Any]]] = None

    def columns(self) -> Dict[str, Any]:
        import json

        out = {k: getattr(self, k) for k in ("nazwa_lub_numer", "kategoria", "geometria") if k in self.model_fields_set}
        if isinstance(out.get("geometria"), dict):
            out["geometria"] = json.dumps(out["geometria"], ensure_ascii=False)
        return out


class GenealogyIn(_Input):
    id_osoby: Optional[ShortText] = None
    imie: Optional[ShortText] = None
    nazwisko: Optional[ShortText] = None
    plec: Optional[Annotated[str, StringConstraints(max_length=16)]] = None
    rok_urodzenia: OptYear = None
    rok_smierci: OptYear = None
    uwagi: Optional[LongText] = None
    numer_domu: Optional[ShortText] = None
    id_ojca: PersonRef = None
    id_matki: PersonRef = None


class DemographyIn(_Input):
    rok: OptYear = None
    populacja_ogolem: OptCount = 0
    katolicy: OptCount = 0
    zydzi: OptCount = 0
    inni: OptCount = 0
    opis: Optional[LongText] = ""


class GeoJSONFeature(_Input):
    id: Optional[Union[int, ShortText]] = None
    properties: Dict[str, Any] = {}
    geometry: Optional[Dict[str, Any]] = None


class FeatureCollectionIn(_Input):
    type: Optional[Annotated[str, StringConstraints(max_length=64)]] = None
    features: Annotated[List[GeoJSONFeature], Field(max_length=MAX_FEATURES)] = []
