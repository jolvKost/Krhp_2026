"""Integración de múltiples Excels en un CSV maestro, por columna de referencia."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def leer_hoja(ruta: str) -> pd.DataFrame:
    """Lee un Excel genérico y normaliza sus encabezados (sin mapear a Persona)."""
    df = pd.read_excel(ruta, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def auto_mapear_columnas(
    columnas_archivo: list[str], columnas_canonicas: list[str]
) -> tuple[dict[str, str], list[str]]:
    """Empareja encabezados por texto exacto insensible a mayúsculas.

    Devuelve (mapeadas, sin_mapear): mapeadas es {columna_canonica: columna_original}.
    """
    canonicas_por_lower = {c.strip().lower(): c for c in columnas_canonicas}
    mapeadas: dict[str, str] = {}
    sin_mapear: list[str] = []
    for col in columnas_archivo:
        canonica = canonicas_por_lower.get(col.strip().lower())
        if canonica:
            mapeadas[canonica] = col
        else:
            sin_mapear.append(col)
    return mapeadas, sin_mapear


def sugerir_columna_referencia(
    df: pd.DataFrame,
    valores_conocidos: set[str],
    columnas_candidatas: list[str],
    umbral: float = 0.5,
) -> str | None:
    """Sugiere cuál de las columnas sin mapear es la columna de referencia,
    comparando el solapamiento de sus valores contra los ya conocidos."""
    if not valores_conocidos:
        return None

    mejor_columna = None
    mejor_ratio = 0.0
    for col in columnas_candidatas:
        valores_col = set(df[col].dropna().astype(str).str.strip())
        valores_col.discard("")
        if not valores_col:
            continue
        ratio = len(valores_col & valores_conocidos) / len(valores_col)
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_columna = col

    return mejor_columna if mejor_ratio > umbral else None


def combinar(
    tablas: list[pd.DataFrame], columna_referencia: str, orden_prioridad: list[int]
) -> pd.DataFrame:
    """Combina tablas ya normalizadas a columnas canónicas en un maestro sin duplicados.

    orden_prioridad es una lista de índices en `tablas`, de mayor a menor prioridad:
    ante un conflicto en una misma columna para el mismo valor de referencia, gana
    el valor no vacío del archivo con mayor prioridad.
    """
    tablas_ordenadas = [tablas[i] for i in orden_prioridad]
    combinado = pd.concat(tablas_ordenadas, ignore_index=True, sort=False)

    combinado[columna_referencia] = combinado[columna_referencia].astype(str).str.strip()
    combinado = combinado[
        combinado[columna_referencia].notna()
        & (combinado[columna_referencia] != "")
        & (combinado[columna_referencia].str.lower() != "nan")
    ]

    # ponytail: groupby().first() ya toma, por columna, el primer valor no nulo
    # del grupo -- como las tablas están concatenadas en orden de prioridad, esto
    # resuelve el conflicto sin lógica de merge manual.
    resultado = combinado.groupby(columna_referencia, sort=False).first()
    return resultado.reset_index()


def _validar_ruta_excel(ruta: str) -> Path | None:
    ruta = ruta.strip().strip('"\'')
    if not ruta:
        return None
    ruta_path = Path(ruta)
    if not ruta_path.exists():
        print(f"❌ Archivo no encontrado: {ruta}")
        return None
    if ruta_path.suffix.lower() not in (".xlsx", ".xls", ".xlsm"):
        print("❌ El archivo debe ser un Excel (.xlsx, .xls, .xlsm)")
        return None
    return ruta_path


def _solicitar_archivos() -> list[str]:
    print("\nIngresa las rutas de los Excels a integrar (Enter vacío para terminar).")
    rutas: list[str] = []
    while True:
        entrada = input(f"Archivo {len(rutas) + 1} (o Enter para terminar): ").strip()
        if not entrada:
            if len(rutas) >= 2:
                return rutas
            print("❌ Se necesitan al menos 2 archivos para integrar.")
            continue
        ruta_path = _validar_ruta_excel(entrada)
        if ruta_path:
            rutas.append(str(ruta_path))
            print(f"✓ Agregado: {ruta_path.name}")


def _resolver_mapeo_archivo(
    nombre_archivo: str, df: pd.DataFrame, columnas_canonicas: list[str]
) -> dict[str, str]:
    """Devuelve {columna_canonica: columna_original} para un archivo, preguntando
    al usuario solo por las columnas que no calzaron automáticamente."""
    mapeadas, sin_mapear = auto_mapear_columnas(list(df.columns), columnas_canonicas)

    for col in sin_mapear:
        print(f"\nEn '{nombre_archivo}' la columna '{col}' no coincide con ninguna conocida:")
        for i, canonica in enumerate(columnas_canonicas, 1):
            print(f"   {i}. {canonica}")
        print(f"   n. Es una columna nueva ('{col}')")
        print("   0. Ignorar esta columna")

        while True:
            opcion = input("¿A cuál corresponde? ").strip().lower()
            if opcion == "0":
                break
            if opcion == "n":
                mapeadas[col] = col
                columnas_canonicas.append(col)
                break
            try:
                idx = int(opcion) - 1
            except ValueError:
                idx = -1
            if 0 <= idx < len(columnas_canonicas):
                mapeadas[columnas_canonicas[idx]] = col
                break
            print("❌ Opción inválida.")

    return mapeadas


def _resolver_columna_referencia(columnas_canonicas: list[str]) -> str:
    print("\nColumnas disponibles:")
    for i, col in enumerate(columnas_canonicas, 1):
        print(f"   {i}. {col}")
    while True:
        opcion = input("¿Cuál es la columna de referencia para deduplicar? (número): ").strip()
        try:
            idx = int(opcion) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(columnas_canonicas):
            return columnas_canonicas[idx]
        print("❌ Opción inválida.")


def _resolver_referencia_faltante(
    nombre_archivo: str,
    df: pd.DataFrame,
    mapeo: dict[str, str],
    columna_referencia: str,
    valores_referencia_conocidos: set[str],
) -> None:
    """Completa mapeo[columna_referencia] cuando el archivo no la trajo mapeada."""
    candidatas = [c for c in df.columns if c not in mapeo.values()]
    sugerida = sugerir_columna_referencia(df, valores_referencia_conocidos, candidatas)
    if sugerida:
        print(
            f"\n⚠️  '{nombre_archivo}' no tiene un encabezado para la referencia; "
            f"posible coincidencia por contenido: '{sugerida}'"
        )
        if input("¿Usar esta columna como referencia? (s/n): ").strip().lower() == "s":
            mapeo[columna_referencia] = sugerida
            return

    print(f"\nNo se detectó columna de referencia en '{nombre_archivo}'. Columnas: {list(df.columns)}")
    while columna_referencia not in mapeo:
        manual = input("Nombre exacto de la columna que sirve de referencia: ").strip()
        if manual in df.columns:
            mapeo[columna_referencia] = manual
        else:
            print("❌ No existe esa columna en el archivo.")


def _resolver_orden_prioridad(rutas: list[str]) -> list[int]:
    print("\nArchivos cargados:")
    for i, ruta in enumerate(rutas, 1):
        print(f"   {i}. {Path(ruta).name}")
    while True:
        entrada = input(
            "Orden de prioridad ante conflictos (números separados por coma, de mayor a menor): "
        ).strip()
        try:
            indices = [int(x.strip()) - 1 for x in entrada.split(",")]
        except ValueError:
            print("❌ Entrada inválida.")
            continue
        if sorted(indices) == list(range(len(rutas))):
            return indices
        print("❌ Debes listar cada archivo exactamente una vez.")


def interfaz_integracion_interactiva() -> None:
    """Flujo interactivo de integración de Excels en un CSV maestro."""
    print("\n" + "=" * 60)
    print("INTEGRAR EXCELS")
    print("=" * 60)

    rutas = _solicitar_archivos()

    print("\n📂 Cargando archivos...")
    dfs_crudos = [leer_hoja(r) for r in rutas]

    columnas_canonicas = list(dfs_crudos[0].columns)
    mapeos = [{c: c for c in columnas_canonicas}]
    for ruta, df in zip(rutas[1:], dfs_crudos[1:]):
        mapeos.append(_resolver_mapeo_archivo(Path(ruta).name, df, columnas_canonicas))

    print(f"\n✓ Columnas combinadas ({len(columnas_canonicas)}): {', '.join(columnas_canonicas)}")
    columna_referencia = _resolver_columna_referencia(columnas_canonicas)

    tablas = []
    valores_referencia_conocidos: set[str] = set()
    for ruta, df, mapeo in zip(rutas, dfs_crudos, mapeos):
        if columna_referencia not in mapeo:
            _resolver_referencia_faltante(
                Path(ruta).name, df, mapeo, columna_referencia, valores_referencia_conocidos
            )

        tabla = df.rename(columns={original: canonica for canonica, original in mapeo.items()})
        tabla = tabla[list(mapeo.keys())]
        tablas.append(tabla)
        valores_referencia_conocidos |= set(
            tabla[columna_referencia].dropna().astype(str).str.strip()
        )

    orden_prioridad = _resolver_orden_prioridad(rutas)

    resultado = combinar(tablas, columna_referencia, orden_prioridad)
    print(f"\n✓ Integración completa: {len(resultado)} filas únicas por '{columna_referencia}'")

    salida = input("\nRuta del CSV de salida (Enter para 'integrado.csv'): ").strip().strip('"\'')
    ruta_salida = Path(salida) if salida else Path("integrado.csv")
    if ruta_salida.is_dir():
        ruta_salida = ruta_salida / "integrado.csv"
    elif not ruta_salida.suffix:
        ruta_salida = ruta_salida.with_suffix(".csv")
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    resultado.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    print(f"\n✅ CSV maestro generado en: {ruta_salida}")
