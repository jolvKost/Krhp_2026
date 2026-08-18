import pandas as pd

from organigramas.excel_integrator import auto_mapear_columnas, combinar


def test_auto_mapear_columnas_exacto_insensible_mayusculas():
    mapeadas, sin_mapear = auto_mapear_columnas(
        ["ID", "correo", "Depto Nuevo"], ["id", "correo electronico"]
    )

    assert mapeadas == {"id": "ID"}
    assert sin_mapear == ["correo", "Depto Nuevo"]


def test_combinar_prioridad_resuelve_conflicto():
    alta = pd.DataFrame({"id": ["1"], "nombre": ["Ana Vieja"]})
    baja = pd.DataFrame({"id": ["1"], "nombre": ["Ana Nueva"]})

    resultado = combinar([alta, baja], "id", orden_prioridad=[0, 1])

    assert resultado.loc[0, "nombre"] == "Ana Vieja"


def test_combinar_rellena_columna_faltante_desde_otro_archivo():
    sin_correo = pd.DataFrame({"id": ["1"], "nombre": ["Ana"]})
    con_correo = pd.DataFrame({"id": ["1"], "correo": ["ana@example.com"]})

    resultado = combinar([sin_correo, con_correo], "id", orden_prioridad=[0, 1])

    assert resultado.loc[0, "nombre"] == "Ana"
    assert resultado.loc[0, "correo"] == "ana@example.com"


def test_combinar_no_duplica_filas_por_referencia_repetida():
    archivo_1 = pd.DataFrame({"id": ["1", "2"], "nombre": ["Ana", "Bruno"]})
    archivo_2 = pd.DataFrame({"id": ["2", "3"], "nombre": ["Bruno", "Carla"]})

    resultado = combinar([archivo_1, archivo_2], "id", orden_prioridad=[0, 1])

    assert sorted(resultado["id"]) == ["1", "2", "3"]
    assert len(resultado) == 3
