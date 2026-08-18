"""Verifica que la extracción produzca los mismos datos que hoy imprime el Excel.

Las cajas del organigrama en HC_Controlling muestran 4 campos, tomados de la
hoja "Organigrama": O (área), T (CeCo), S (posición) y Q (nombre abreviado).
"""

import json

import pandas as pd

from organigramas.excel_parser import ExcelParser, cargar_catalogo_areas


def test_nombre_abreviado_replica_columna_aa():
    # AA = LEFT(Nombre(s),1) & "." & " " & Ap.Paterno & " " & Ap.Materno
    assert (
        ExcelParser._generar_nombre_abreviado("Juan Pedro", "Pérez", "López")
        == "J. Pérez López"
    )
    # Sin apellido materno no debe quedar un espacio colgando
    assert ExcelParser._generar_nombre_abreviado("Ana", "Ruiz") == "A. Ruiz"


def test_catalogo_areas_ausente_no_rompe(tmp_path):
    assert cargar_catalogo_areas(tmp_path / "no_existe.json") == {}


def test_catalogo_areas_normaliza_claves(tmp_path):
    ruta = tmp_path / "areas.json"
    ruta.write_text(json.dumps({"1234.0": "Producción"}), encoding="utf-8")
    assert cargar_catalogo_areas(ruta) == {"1234": "Producción"}


def test_extraccion_desde_layout_sap(tmp_path):
    archivo = tmp_path / "sap.xlsx"
    pd.DataFrame(
        [
            {
                "Nº pers.": 1001,
                "Nombre(s)": "Juan Pedro",
                "Apellido Paterno": "Pérez",
                "Apellido Materno": "López",
                "Denominación de la posición": "Director General",
                "CeCo": 1234,
                "Planta": "K1",
            }
        ]
    ).to_excel(archivo, index=False)

    personas = ExcelParser(catalogo_areas={"1234": "Producción"}).leer_excel(str(archivo))

    assert len(personas) == 1
    persona = personas[0]
    assert persona.nombre_abreviado == "J. Pérez López"  # col Q (vía AA)
    assert persona.ceco == "1234"  # col T
    assert persona.posicion == "Director General"  # col S
    assert persona.area == "Producción"  # col O


def test_area_resuelve_con_ceco_flotante(tmp_path):
    """pandas tipa CeCo como float si la columna trae huecos: 1234 -> "1234.0"."""
    archivo = tmp_path / "sap.xlsx"
    pd.DataFrame(
        [
            {"Nº pers.": 1001, "Nombre(s)": "Juan", "Apellido Paterno": "Pérez", "CeCo": 1234},
            {"Nº pers.": 1002, "Nombre(s)": "Ana", "Apellido Paterno": "Ruiz", "CeCo": None},
        ]
    ).to_excel(archivo, index=False)

    personas = ExcelParser(catalogo_areas={"1234": "Producción"}).leer_excel(str(archivo))

    assert personas[0].area == "Producción"
    assert personas[1].area is None
