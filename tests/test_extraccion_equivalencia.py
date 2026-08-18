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

    # La cabeza se pide por Nº pers., no por nombre
    arbol = HierarchyManager(personas).construir_arbol("1001")
    assert [h.persona.numero_personal for h in arbol.hijos] == ["1002"]
    # Y la arista quedó resuelta a Nº pers., no a un string
    assert subordinado.supervisor_numero == "1001"


def persona(num, paterno, nombres, jefe=None, materno=None):
    """Constructor corto de Persona para los tests de jerarquía."""
    from organigramas.models import Persona

    return Persona(
        numero_personal=num,
        nombres=nombres,
        nombre_abreviado=f"{nombres[:1]}. {paterno}",
        apellido_paterno=paterno,
        apellido_materno=materno,
        supervisor_nombre=jefe,
    )


def test_cabezas_se_ordenan_por_subordinados():
    """El menu solo muestra 10 cabezas: las que mandan gente deben ir primero."""
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


def test_homonimos_no_heredan_subordinados_ajenos():
    """
    El bug de fondo: dos personas distintas con el mismo Ap.Paterno + Nombre(s).

    Antes la ultima ganaba el indice y se quedaba con TODOS los subordinados de
    la otra. Ahora el nombre es ambiguo -> no resuelve, y se reporta.
    """
    personas = [
        persona("1001", "PEREZ", "JUAN", materno="LOPEZ"),
        persona("1002", "PEREZ", "JUAN", materno="GARCIA"),  # distinto empleado
        persona("1003", "RUIZ", "ANA", jefe="PEREZ, JUAN"),
    ]

    manager = HierarchyManager(personas)

    assert personas[2].supervisor_numero is None
    assert manager.construir_arbol("1001").hijos == []
    assert manager.construir_arbol("1002").hijos == []
    assert manager.nombres_ambiguos == {"perez juan"}


def test_nombres_de_pila_no_son_identificador():
    """"Nombre(s)" por si solo no indexa: cientos de personas comparten uno."""
    personas = [
        persona("1", "SOLIS", "MARIA GUADALUPE"),
        persona("2", "RUIZ", "MARIA GUADALUPE"),
        persona("3", "MORA", "LUIS", jefe="MARIA GUADALUPE"),
    ]

    manager = HierarchyManager(personas)

    assert personas[2].supervisor_numero is None
    assert manager.hijos_por_jefe == {}


def test_ciclo_no_cuelga_ni_duplica():
    """A manda a B y B manda a A: el arbol debe terminar."""
    personas = [
        persona("1", "PEREZ", "JUAN", jefe="RUIZ, ANA"),
        persona("2", "RUIZ", "ANA", jefe="PEREZ, JUAN"),
    ]

    arbol = HierarchyManager(personas).construir_arbol("1")

    assert [p.numero_personal for p in arbol.obtener_todos_descendientes()] == ["1", "2"]


def test_nadie_es_su_propio_jefe():
    personas = [persona("1", "PEREZ", "JUAN", jefe="PEREZ, JUAN")]

    manager = HierarchyManager(personas)

    assert personas[0].supervisor_numero is None
    assert manager.obtener_todas_las_cabezas_posibles()[0].numero_personal == "1"


def test_numero_personal_duplicado_se_reporta():
    duplicados = ExcelParser._advertir_numeros_duplicados(
        [
            persona("1001", "PEREZ", "JUAN"),
            persona("1001", "RUIZ", "ANA"),
            persona("1002", "MORA", "LUIS"),
        ]
    )

    assert duplicados == ["1001"]


def test_validar_estructura_reporta_cobertura_real():
    """
    El reporte debe hacer VISIBLE cuanta gente quedo sin jefe resuelto, y
    distinguir "el jefe no existe" de "el nombre del jefe es ambiguo": son
    problemas de datos distintos y antes se contaban dos veces.
    """
    personas = [
        persona("1", "PEREZ", "JUAN", materno="LOPEZ"),
        persona("2", "PEREZ", "JUAN", materno="GARCIA"),  # homonimo de 1
        persona("3", "RUIZ", "ANA", jefe="PEREZ, JUAN"),  # ambiguo
        persona("4", "MORA", "LUIS", jefe="NADIE, QUE EXISTA"),  # inexistente
        persona("5", "SOLIS", "EVA", jefe="RUIZ, ANA"),  # resuelto
    ]

    reporte = HierarchyManager(personas).validar_estructura()

    assert reporte["jefes_resueltos"] == 1
    # "3" encabeza la lista porque es la unica de las cuatro que manda a alguien
    assert [c.numero_personal for c in reporte["cabezas_posibles"]] == ["3", "1", "2", "4"]

    advertencias = " | ".join(reporte["advertencias"])
    assert "2 personas sin dato de jefe" in advertencias
    assert "1 personas cuyo jefe no existe" in advertencias
    assert "nadie que exista" in advertencias  # ejemplo concreto, no vacio
    assert "1 personas cuyo jefe coincide con mas de una" in advertencias
    assert "1/5 personas" in advertencias


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
