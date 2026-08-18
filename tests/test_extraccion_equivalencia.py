"""Verifica que la extracción produzca los mismos datos que hoy imprime el Excel.

Las cajas del organigrama en HC_Controlling muestran 4 campos, tomados de la
hoja "Organigrama": O (área), T (CeCo), S (posición) y Q (nombre abreviado).
"""

import json

import pandas as pd

from organigramas.excel_parser import ExcelParser, cargar_catalogo_areas
from organigramas.hierarchy import HierarchyManager, normalizar_nombre


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


def test_normalizar_ignora_comillas_y_comas_pero_no_el_orden():
    # El extracto SAP entrega el jefe directo encomillado: '"PEREZ, JUAN"'
    assert normalizar_nombre('"PEREZ, JUAN PEDRO"') == "perez juan pedro"
    assert normalizar_nombre("PEREZ,JUAN") == normalizar_nombre("PEREZ, JUAN")
    assert normalizar_nombre("PEREZ") == normalizar_nombre("Pérez")
    # "Apellido Nombre" y "Nombre Apellido" NO deben colapsar en la misma clave
    assert normalizar_nombre("PEREZ, JUAN") != normalizar_nombre("JUAN PEREZ")


def test_jefe_directo_se_resuelve_desde_cal_migratoria(tmp_path):
    """Cal.Migratoria trae "Apellido, Nombre(s)" del jefe directo, encomillado."""
    archivo = tmp_path / "sap.xlsx"
    pd.DataFrame(
        [
            {
                "Nº pers.": 1001,
                "Nombre(s)": "JUAN PEDRO",
                "Apellido Paterno": "PEREZ",
                "Apellido Materno": "LOPEZ",
                "Nombre del encargado": "Ing Calidad K1",
                "Cal.Migratoria": "",
            },
            {
                "Nº pers.": 1002,
                "Nombre(s)": "ANA",
                "Apellido Paterno": "RUIZ",
                "Apellido Materno": "DIAZ",
                "Nombre del encargado": "Ing Calidad K1",
                "Cal.Migratoria": '"PEREZ, JUAN PEDRO"',
            },
        ]
    ).to_excel(archivo, index=False)

    personas = ExcelParser(catalogo_areas={}).leer_excel(str(archivo))
    jefe, subordinado = personas

    # El árbol se arma desde Cal.Migratoria, no desde "Nombre del encargado"
    assert subordinado.supervisor_nombre == '"PEREZ, JUAN PEDRO"'
    assert jefe.supervisor_nombre is None

    arbol = HierarchyManager(personas).construir_arbol(jefe.nombre_abreviado)
    assert [h.persona.numero_personal for h in arbol.hijos] == ["1002"]


def test_cabezas_se_ordenan_por_subordinados():
    """El menu solo muestra 10 cabezas: las que mandan gente deben ir primero."""
    from organigramas.models import Persona

    def persona(num, paterno, nombres, jefe=None):
        return Persona(
            numero_personal=num,
            nombre_completo=nombres,
            nombre_abreviado=f"{nombres[:1]}. {paterno}",
            apellido_paterno=paterno,
            supervisor_nombre=jefe,
        )

    # SOLIS no tiene jefe ni subordinados; PEREZ no tiene jefe pero manda a dos.
    personas = [
        persona("1", "SOLIS", "EVA"),
        persona("2", "PEREZ", "JUAN"),
        persona("3", "RUIZ", "ANA", jefe="PEREZ, JUAN"),
        persona("4", "MORA", "LUIS", jefe="PEREZ, JUAN"),
    ]

    cabezas = HierarchyManager(personas).obtener_todas_las_cabezas_posibles()

    assert [c.numero_personal for c in cabezas] == ["2", "1"]
    # No se filtra a nadie: la hoja suelta sigue estando, sólo que al final
    assert len(cabezas) == 2


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
