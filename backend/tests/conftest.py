import pytest
import sys
import psycopg2.extras

class _MemDB:
    def __init__(self):
        self.reset()

    def reset(self):
        self.wlasciciele, self.demografia, self.obiekty = [], [], []
        self.osoby_genealogia, self.malzenstwa = [], []
        self.dzialki_wlasciciele = []
        self.seq = {
            "wlasciciele": 1, "demografia": 1, "obiekty": 1,
            "osoby_genealogia": 1, "malzenstwa": 1,
        }

    def next_id(self, table):
        nid = self.seq[table]
        self.seq[table] += 1
        return nid

_MEM = _MemDB()

class _FakeCursor:
    def __init__(self):
        self._last_rows = None

    def execute(self, query, params=None):
        q = " ".join(query.lower().split())
        self._last_rows = []

        # --- Statystyki ---
        if "select count(*) as total_owners from wlasciciele" in q:
            self._last_rows = [{"total_owners": len(_MEM.wlasciciele)}]
        elif "select count(*) as total_plots from obiekty_geograficzne" in q:
            self._last_rows = [{"total_plots": len(_MEM.obiekty)}]
        
        # --- Demografia ---
        elif q.startswith("select * from demografia"):
            self._last_rows = sorted(_MEM.demografia, key=lambda r: r.get("rok", 0))
        elif q.startswith("insert into demografia"):
            new_id = _MEM.next_id("demografia")
            _MEM.demografia.append({"id": new_id, **dict(zip(["rok", "populacja_ogolem", "katolicy", "zydzi", "inni", "opis"], params))})
            self._last_rows = [(new_id,)]
        elif q.startswith("update demografia"):
            data = dict(zip(["rok", "populacja_ogolem", "katolicy", "zydzi", "inni", "opis"], params))
            rid = params[-1]
            for r in _MEM.demografia:
                if r["id"] == int(rid): r.update(data)
        elif q.startswith("delete from demografia"):
            _MEM.demografia = [r for r in _MEM.demografia if r["id"] != int(params[0])]

        # --- Genealogia ---
        elif q.startswith("select p.id as db_id"):
            # Zwracamy listę, ale musimy dodać alias 'db_id'
            self._last_rows = [
                {**person, "db_id": person["id"]} for person in _MEM.osoby_genealogia
            ]
        elif q.startswith("insert into osoby_genealogia"):
            new_id = _MEM.next_id("osoby_genealogia")
            data = dict(zip(["json_id", "imie_nazwisko", "plec", "numer_domu", "rok_urodzenia", "rok_smierci", "id_ojca", "id_matki", "id_protokolu", "uwagi"], params))
            _MEM.osoby_genealogia.append({"id": new_id, **data})
            self._last_rows = [(new_id,)]
        elif q.startswith("update osoby_genealogia"):
            data = dict(zip(["json_id", "imie_nazwisko", "plec", "numer_domu", "rok_urodzenia", "rok_smierci", "id_ojca", "id_matki", "id_protokolu", "uwagi"], params))
            rid = params[-1]
            for r in _MEM.osoby_genealogia:
                if r["id"] == int(rid): r.update(data)
        elif q.startswith("delete from osoby_genealogia"):
            _MEM.osoby_genealogia = [r for r in _MEM.osoby_genealogia if r["id"] != int(params[0])]

        # --- Wlasciciele ---
        elif q.startswith("select * from wlasciciele where id ="):
            self._last_rows = [r for r in _MEM.wlasciciele if r["id"] == int(params[0])]
        elif q.startswith("select * from wlasciciele"):
            self._last_rows = list(_MEM.wlasciciele)
        elif q.startswith("insert into wlasciciele"):
            new_id = _MEM.next_id("wlasciciele")
            _MEM.wlasciciele.append({"id": new_id, **dict(zip(["unikalny_klucz", "nazwa_wlasciciela", "numer_protokolu", "numer_domu", "genealogia", "historia_wlasnosci", "uwagi", "wspolwlasnosc", "powiazania_i_transakcje", "interpretacja_i_wnioski", "data_protokolu", "miejsce_protokolu"], params))})
            self._last_rows = [(new_id,)]
        elif q.startswith("update wlasciciele"):
             data = dict(zip(["unikalny_klucz", "nazwa_wlasciciela", "numer_protokolu", "numer_domu", "genealogia", "historia_wlasnosci", "uwagi", "wspolwlasnosc", "powiazania_i_transakcje", "interpretacja_i_wnioski", "data_protokolu", "miejsce_protokolu"], params))
             rid = params[-1]
             for r in _MEM.wlasciciele:
                if r["id"] == int(rid): r.update(data)
        elif q.startswith("delete from wlasciciele"):
            _MEM.wlasciciele = [r for r in _MEM.wlasciciele if r["id"] != int(params[0])]

        # --- Dzialki_Wlasciciele ---
        elif q.startswith("select o.id, o.nazwa_lub_numer, o.kategoria, dw.typ_posiadania"):
            wid = params[0]
            # Znajdź ID obiektów powiązanych z tym właścicielem
            linked_oids = {
                link['obiekt_id'] for link in _MEM.dzialki_wlasciciele
                if link['wlasciciel_id'] == int(wid)
            }
            # Zwróć tylko te obiekty, które są na liście powiązań
            self._last_rows = [
                obj for obj in _MEM.obiekty if obj['id'] in linked_oids
            ]
        elif q.startswith("delete from dzialki_wlasciciele"):
            _MEM.dzialki_wlasciciele = [
                r for r in _MEM.dzialki_wlasciciele if r['wlasciciel_id'] != int(params[0])
            ]
        elif "insert into dzialki_wlasciciele (wlasciciel_id, obiekt_id" in q and "values %s" in q:
            # Obsługa psycopg2.extras.execute_values
            rows = params[0]
            for row_tuple in rows:
                rec = {"wlasciciel_id": row_tuple[0], "obiekt_id": row_tuple[1]}
                # Jeśli podano typ_posiadania (trzeci element), zachowaj go w mocku
                if len(row_tuple) >= 3:
                    rec["typ_posiadania"] = row_tuple[2]
                _MEM.dzialki_wlasciciele.append(rec)

        # --- Obiekty ---
        # Używamy tego wyróżnika, by nie kolidowało z SELECT-em z JOIN dzialki_wlasciciele.
        elif q.startswith("select o.id, o.nazwa_lub_numer, o.kategoria") and "case when" in q:
            self._last_rows = list(_MEM.obiekty)
        elif q.startswith("update obiekty_geograficzne"):
            nazwa, kategoria, oid = params
            for r in _MEM.obiekty:
                if r["id"] == int(oid):
                    r.update({"nazwa_lub_numer": nazwa, "kategoria": kategoria})
        elif q.startswith("delete from obiekty_geograficzne"):
            _MEM.obiekty = [r for r in _MEM.obiekty if r["id"] != int(params[0])]

    def fetchone(self): return self._last_rows[0] if self._last_rows else None
    def fetchall(self): return self._last_rows
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.close()

class _FakeConn:
    def cursor(self, *args, **kwargs): return _FakeCursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass

@pytest.fixture
def app(monkeypatch):
    if 'backend' not in sys.path: sys.path.insert(0, 'backend')
    import app as backend_app
    monkeypatch.setattr(psycopg2.extras, "execute_values", lambda cur, sql, args: cur.execute(sql, (args,)))
    monkeypatch.setattr(backend_app, "get_db_connection", lambda: _FakeConn())
    _MEM.reset()
    _MEM.wlasciciele.extend([{"id": _MEM.next_id("wlasciciele"), "unikalny_klucz": f"W-{i}", "nazwa_wlasciciela": f"Właściciel {i}"} for i in range(2)])
    _MEM.obiekty.extend([{"id": _MEM.next_id("obiekty"), "nazwa_lub_numer": f"O-{i}", "kategoria": "rolna"} for i in range(5)])
    _MEM.demografia.append({"id": 1, "rok": 1850, "populacja_ogolem": 100})
    return backend_app.app

@pytest.fixture
def client(app):
    return app.test_client()