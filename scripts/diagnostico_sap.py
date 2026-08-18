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


def enmascarar(texto: str) -> str:
    """"Juan Pérez" -> "Xxxx Xxxxx". Revela el formato, no el dato."""
    texto = re.sub(r"[0-9]", "9", texto)
    texto = re.sub(r"[^\W\d_]", lambda m: "X" if m.group().isupper() else "x", texto)
    return texto


def normalizar(texto) -> str:
    """
    Minusculas, sin acentos, sin puntuacion, espacios colapsados.

    Se descarta la puntuacion porque el extracto SAP entrega Cal.Migratoria
    encomillada: '"PEREZ, JUAN"'. La propia Power Query del .xlsm limpia esas
    comillas (Table.ReplaceValue sobre Cal.Migratoria), asi que quitarlas aqui
    reproduce lo que el proceso actual ya hace.

    El ORDEN de los tokens se conserva, asi que "Apellido Nombre" y
    "Nombre Apellido" siguen siendo distintos. Determinista, sin heuristicas.
    """
    plano = str(texto).casefold()
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", plano) if not unicodedata.combining(c)
    )
    solo_texto = "".join(c if (c.isalnum() or c.isspace()) else " " for c in sin_acentos)
    return " ".join(solo_texto.split())


def cobertura_de_claves(df, mapa: dict, campo_jefe: str) -> list[str]:
    """
    Mide que clave candidata resuelve la columna de jefe indicada, con match EXACTO.

    No hace matching difuso: sólo prueba combinaciones deterministas de columnas
    y reporta cuantos jefes distintos encuentra cada una.
    """

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
        # Variantes "Apellido, Nombre" (la coma se ignora al normalizar)
        "Ap.Paterno + Nombre(s)": paterno + " " + nombres,
        "Ap.Paterno + 1er nombre": paterno + " " + n1,
        "Ap.Paterno + Ap.Materno + Nombre(s)": paterno + " " + materno + " " + nombres,
        "Ap.Paterno + Ap.Materno + 1er nombre": paterno + " " + materno + " " + n1,
    }

    jefe = col(campo_jefe)
    if jefe is None:
        return [f"Columna '{campo_jefe}' ausente: no se puede medir cobertura."]

    jefe = jefe.map(normalizar)
    distintos = {s for s in jefe if s}
    total_personas = int((jefe != "").sum())
    vacios = int((jefe == "").sum())

    lineas = [
        f"=== Cobertura contra '{mapa[campo_jefe]}' ===",
        f"{total_personas} personas con jefe | {vacios} en blanco | {len(distintos)} jefes distintos",
        "(match exacto tras minusculas/sin acentos/sin puntuacion, sin matching difuso):",
    ]

    union = set()
    for etiqueta, serie in candidatos.items():
        if serie is None:
            lineas.append(f"  ----  {etiqueta}: columna ausente")
            continue
        claves = {normalizar(v) for v in serie if normalizar(v)}
        resueltos = distintos & claves
        union |= resueltos
        personas = int(jefe.isin(resueltos).sum())
        lineas.append(
            f"  {len(resueltos):>4}/{len(distintos)} jefes  {personas:>5}/{total_personas} personas  {etiqueta}"
        )

    personas_union = int(jefe.isin(union).sum())
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
    lineas.append("")

    df = pd.read_excel(ruta, sheet_name=0)

    # Las dos columnas de jefe se miden POR SEPARADO. excel_parser usa
    # Cal.Migratoria solo como fallback de "Nombre del encargado"; mezclarlas
    # (como hacia una version previa de este script) falsea las cuentas.
    for campo in ("supervisor", "cal_migratoria"):
        if campo not in mapeados:
            continue
        columna = df[mapeados[campo]].fillna("").astype(str)
        normalizada = columna.map(normalizar)
        distintos = {v for v in normalizada if v}
        con_dato = int((normalizada != "").sum())
        lineas.append(f"--- Columna '{mapeados[campo]}' ---")
        lineas.append(
            f"  Con dato: {con_dato} | en blanco: {len(df) - con_dato}"
            f" | jefes distintos: {len(distintos)}"
            f" -> ~{con_dato // max(len(distintos), 1)} reportes por jefe"
        )
        lineas.append("  Formato (enmascarado, compartible):")
        for forma, veces in Counter(enmascarar(v) for v in columna if v.strip()).most_common(6):
            lineas.append(f"    {veces:>5}x  {forma}")
        lineas.append("")

    lineas.append("Formato de 'nombre_abreviado' generado (clave actual del indice):")
    for forma, veces in Counter(enmascarar(p.nombre_abreviado) for p in personas).most_common(5):
        lineas.append(f"  {veces:>4}x  {forma}")
    lineas.append("")

    for campo in ("cal_migratoria", "supervisor"):
        if campo in mapeados:
            lineas.extend(cobertura_de_claves(df, mapeados, campo))
            lineas.append("")

    return "\n".join(lineas)


def _selfcheck() -> None:
    assert enmascarar("Juan Pérez") == "Xxxx Xxxxx"
    assert enmascarar("PEREZ LOPEZ JUAN") == "XXXXX XXXXX XXXX"
    assert enmascarar("J. Pérez López") == "X. Xxxxx Xxxxx"
    assert enmascarar("K1-1234") == "X9-9999"

    # normalizar debe cerrar la brecha CAPS/acentos/puntuacion que rompe el match
    assert normalizar("  Juan   Pérez ") == "juan perez"
    assert normalizar("PEREZ") == normalizar("Pérez")
    assert normalizar("PEREZ, JUAN") == "perez juan"
    assert normalizar("PEREZ,JUAN") == normalizar("PEREZ, JUAN")
    # el extracto SAP entrega Cal.Migratoria encomillada
    assert normalizar('"PEREZ, JUAN PEDRO"') == "perez juan pedro"
    # el orden sigue distinguiendo "Apellido Nombre" de "Nombre Apellido"
    assert normalizar("PEREZ, JUAN") != normalizar("JUAN PEREZ")
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
