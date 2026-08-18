"""Diagnostica un archivo SAP original contra el pipeline del proyecto.

Corre 100% local. Reporta si los encabezados se mapean, cuántas personas se
extraen, y -- lo importante -- en qué FORMATO viene "Nombre del encargado",
enmascarado (Xxxx en vez de letras) para poder compartirlo sin exponer nombres.
"""

import argparse
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

from organigramas.excel_parser import ENCABEZADOS_ESPERADOS, ExcelParser
from organigramas.hierarchy import HierarchyManager


def enmascarar(texto: str) -> str:
    """"Juan Pérez" -> "Xxxx Xxxxx". Revela el formato, no el dato."""
    texto = re.sub(r"[0-9]", "9", texto)
    texto = re.sub(r"[^\W\d_]", lambda m: "X" if m.group().isupper() else "x", texto)
    return texto


def normalizar(texto) -> str:
    """Minusculas, sin acentos, espacios colapsados. Determinista, sin heuristicas."""
    plano = " ".join(str(texto).split()).casefold()
    return "".join(c for c in unicodedata.normalize("NFD", plano) if not unicodedata.combining(c))


def cobertura_de_claves(ruta: str, mapa: dict) -> list[str]:
    """
    Mide que clave candidata resuelve "Nombre del encargado" con match EXACTO.

    No hace matching difuso: sólo prueba combinaciones deterministas de columnas
    y reporta cuantos supervisores distintos encuentra cada una.
    """
    df = pd.read_excel(ruta, sheet_name=0)

    def col(campo):
        return df[mapa[campo]].fillna("").astype(str) if campo in mapa else None

    nombres, paterno, materno = col("nombre_completo"), col("apellido_paterno"), col("apellido_materno")
    n1 = nombres.str.split().str[0].fillna("")
    n2 = nombres.str.split().str[1].fillna("")

    candidatos = {
        "Nombre del empleado o candidat (tal cual)": col("nombre_empleado"),
        "Nombre(s) + Ap.Paterno": nombres + " " + paterno,
        "1er nombre + Ap.Paterno": n1 + " " + paterno,
        "1er nombre + Ap.Materno": n1 + " " + materno,
        "2do nombre + Ap.Paterno": n2 + " " + paterno,
        "Nombre(s) + Ap.Paterno + Ap.Materno": nombres + " " + paterno + " " + materno,
        "Ap.Paterno + Ap.Materno + Nombre(s)": paterno + " " + materno + " " + nombres,
    }

    supervisor = col("supervisor").map(normalizar)
    distintos = {s for s in supervisor if s}
    total_personas = int((supervisor != "").sum())

    lineas = [
        f"Cobertura de claves candidatas contra {len(distintos)} supervisores distintos",
        f"({total_personas} personas con supervisor; match exacto tras minusculas/sin acentos,",
        "sin matching difuso):",
    ]

    union = set()
    for etiqueta, serie in candidatos.items():
        if serie is None:
            lineas.append(f"  ----  {etiqueta}: columna ausente")
            continue
        claves = {normalizar(v) for v in serie if normalizar(v)}
        resueltos = distintos & claves
        union |= resueltos
        personas = int(supervisor.isin(resueltos).sum())
        lineas.append(
            f"  {len(resueltos):>4}/{len(distintos)} jefes  {personas:>5}/{total_personas} personas  {etiqueta}"
        )

    personas_union = int(supervisor.isin(union).sum())
    lineas.append("")
    lineas.append(
        f"UNION de todas las claves: {len(union)}/{len(distintos)} jefes"
        f"  |  {personas_union}/{total_personas} personas"
    )
    lineas.append(
        f"Sin resolver por ninguna clave determinista: {len(distintos) - len(union)} jefes"
        f"  |  {total_personas - personas_union} personas"
    )
    return lineas


def diagnosticar(ruta: str) -> str:
    lineas = [f"Archivo: {ruta}", ""]

    # leer_excel usa sheet_name=0: si "Format" no es la primera, hay que parametrizarlo.
    hojas = pd.ExcelFile(ruta).sheet_names
    lineas.append(f"Hojas del libro: {hojas}")
    lineas.append(f"Hoja leida (la primera): {hojas[0]}")
    lineas.append("")

    parser = ExcelParser()
    personas = parser.leer_excel(ruta)

    mapeados = parser.encabezados_mapa
    lineas.append(f"Campos mapeados ({len(mapeados)}/{len(ENCABEZADOS_ESPERADOS)}):")
    for campo in ENCABEZADOS_ESPERADOS:
        marca = "OK " if campo in mapeados else "-- "
        lineas.append(f"  {marca}{campo}: {mapeados.get(campo, 'NO ENCONTRADO')}")
    lineas.append("")

    lineas.append(f"Personas extraidas: {len(personas)}")
    con_super = [p for p in personas if p.supervisor_nombre]
    lineas.append(f"Con supervisor: {len(con_super)} | sin supervisor: {len(personas) - len(con_super)}")

    # Cuantos jefes distintos hay define que tan profundo puede ser el arbol.
    jefes = {normalizar(p.supervisor_nombre) for p in con_super}
    lineas.append(
        f"Jefes distintos nombrados: {len(jefes)}"
        f" -> ~{len(con_super) // max(len(jefes), 1)} reportes directos por jefe"
    )
    lineas.append("")

    jerarquia = HierarchyManager(personas)
    no_encontrados = {
        p.supervisor_nombre for p in con_super if not jerarquia._buscar_persona(p.supervisor_nombre)
    }
    resueltos = len(con_super) - sum(
        1 for p in con_super if p.supervisor_nombre in no_encontrados
    )
    lineas.append(f"Supervisores que SI resuelven: {resueltos}")
    lineas.append(f"Supervisores que NO resuelven: {len(no_encontrados)} distintos")
    lineas.append("")

    lineas.append("Formato de 'Nombre del encargado' (enmascarado, compartible):")
    for forma, veces in Counter(enmascarar(s) for s in no_encontrados).most_common(10):
        lineas.append(f"  {veces:>4}x  {forma}")
    lineas.append("")

    lineas.append("Formato de 'nombre_abreviado' generado (clave del indice):")
    for forma, veces in Counter(enmascarar(p.nombre_abreviado) for p in personas).most_common(5):
        lineas.append(f"  {veces:>4}x  {forma}")
    lineas.append("")

    if "nombre_empleado" in mapeados:
        columna = pd.read_excel(ruta, sheet_name=0)[mapeados["nombre_empleado"]].dropna()
        lineas.append("Formato de 'Nombre del empleado o candidat' (columna hoy sin usar):")
        for forma, veces in Counter(enmascarar(str(v)) for v in columna).most_common(5):
            lineas.append(f"  {veces:>4}x  {forma}")
        lineas.append("")

    lineas.extend(cobertura_de_claves(ruta, mapeados))

    return "\n".join(lineas)


def _selfcheck() -> None:
    assert enmascarar("Juan Pérez") == "Xxxx Xxxxx"
    assert enmascarar("PEREZ LOPEZ JUAN") == "XXXXX XXXXX XXXX"
    assert enmascarar("J. Pérez López") == "X. Xxxxx Xxxxx"
    assert enmascarar("K1-1234") == "X9-9999"

    # normalizar debe cerrar la brecha CAPS/acentos que hoy rompe el match
    assert normalizar("  Juan   Pérez ") == "juan perez"
    assert normalizar("PEREZ") == normalizar("Pérez")
    print("selfcheck OK")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", nargs="?", help="Ruta al archivo SAP original")
    parser.add_argument("-o", "--output", default="diagnostico_sap.txt")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args(argv)

    if args.selfcheck:
        _selfcheck()
        return 0

    ruta = args.workbook or input("Ruta al archivo SAP original: ").strip()
    Path(args.output).write_text(diagnosticar(ruta), encoding="utf-8")
    print(f"Diagnostico guardado en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
