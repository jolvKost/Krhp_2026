"""Diagnostica un archivo SAP original contra el pipeline del proyecto.

Corre 100% local. Reporta si los encabezados se mapean, cuántas personas se
extraen, y -- lo importante -- en qué FORMATO viene "Nombre del encargado",
enmascarado (Xxxx en vez de letras) para poder compartirlo sin exponer nombres.
"""

import argparse
import re
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

    return "\n".join(lineas)


def _selfcheck() -> None:
    assert enmascarar("Juan Pérez") == "Xxxx Xxxxx"
    assert enmascarar("PEREZ LOPEZ JUAN") == "XXXXX XXXXX XXXX"
    assert enmascarar("J. Pérez López") == "X. Xxxxx Xxxxx"
    assert enmascarar("K1-1234") == "X9-9999"
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
