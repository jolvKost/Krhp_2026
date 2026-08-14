"""Interfaz gráfica de escritorio (tkinter) para generar organigramas e integrar Excels."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from .excel_integrator import (
    auto_mapear_columnas,
    combinar,
    leer_hoja,
    sugerir_columna_referencia,
)
from .excel_parser import ExcelParser
from .heads_manager import HeadsManager
from .hierarchy import HierarchyManager
from .pdf_renderer import PDFRenderer

logger = logging.getLogger(__name__)


# --- Diálogos genéricos reutilizados por ambos flujos ---


def _elegir_opcion(root: tk.Misc, titulo: str, opciones: list[str]) -> int | None:
    """Muestra una lista modal y devuelve el índice elegido, o None si se cancela."""
    if not opciones:
        return None

    ventana = tk.Toplevel(root)
    ventana.title(titulo)
    ventana.transient(root)
    ventana.grab_set()

    tk.Label(ventana, text=titulo, padx=10, pady=10, wraplength=400).pack()

    lista = tk.Listbox(ventana, width=60, height=min(15, len(opciones) + 1))
    for opcion in opciones:
        lista.insert(tk.END, opcion)
    lista.selection_set(0)
    lista.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

    resultado: dict[str, int | None] = {"indice": None}

    def aceptar() -> None:
        seleccion = lista.curselection()
        resultado["indice"] = seleccion[0] if seleccion else None
        ventana.destroy()

    def cancelar() -> None:
        resultado["indice"] = None
        ventana.destroy()

    lista.bind("<Double-Button-1>", lambda _e: aceptar())

    botones = tk.Frame(ventana)
    botones.pack(pady=(0, 10))
    tk.Button(botones, text="Aceptar", command=aceptar).pack(side=tk.LEFT, padx=5)
    tk.Button(botones, text="Cancelar", command=cancelar).pack(side=tk.LEFT, padx=5)

    ventana.protocol("WM_DELETE_WINDOW", cancelar)
    root.wait_window(ventana)
    return resultado["indice"]


def _pedir_formulario(
    root: tk.Misc, titulo: str, campos: dict[str, str]
) -> dict[str, str] | None:
    """Muestra un formulario modal (un Entry por campo) y devuelve los valores, o None si se cancela."""
    ventana = tk.Toplevel(root)
    ventana.title(titulo)
    ventana.transient(root)
    ventana.grab_set()

    entradas: dict[str, tk.Entry] = {}
    for i, (etiqueta, valor_default) in enumerate(campos.items()):
        tk.Label(ventana, text=etiqueta).grid(row=i, column=0, sticky="w", padx=10, pady=5)
        entrada = tk.Entry(ventana, width=40)
        entrada.insert(0, valor_default)
        entrada.grid(row=i, column=1, padx=10, pady=5)
        entradas[etiqueta] = entrada

    resultado: dict[str, dict[str, str] | None] = {"valores": None}

    def aceptar() -> None:
        resultado["valores"] = {clave: entrada.get().strip() for clave, entrada in entradas.items()}
        ventana.destroy()

    def cancelar() -> None:
        resultado["valores"] = None
        ventana.destroy()

    fila_botones = len(campos)
    botones = tk.Frame(ventana)
    botones.grid(row=fila_botones, column=0, columnspan=2, pady=10)
    tk.Button(botones, text="Aceptar", command=aceptar).pack(side=tk.LEFT, padx=5)
    tk.Button(botones, text="Cancelar", command=cancelar).pack(side=tk.LEFT, padx=5)

    ventana.protocol("WM_DELETE_WINDOW", cancelar)
    root.wait_window(ventana)
    return resultado["valores"]


# --- Flujo: Generar organigrama ---


def _elegir_cabeza(
    root: tk.Misc, heads_manager: HeadsManager, cabezas_posibles: list[str]
) -> str | None:
    cabezas_guardadas = heads_manager.cargar_cabezas()
    adicionales = [c for c in cabezas_posibles if c not in cabezas_guardadas]
    nombres = cabezas_guardadas + adicionales
    opciones = [f"{c} (guardada)" for c in cabezas_guardadas]
    opciones += [f"{c} (del Excel)" for c in adicionales]
    opciones.append("+ Agregar cabeza nueva manualmente")

    indice = _elegir_opcion(root, "Selecciona la cabeza del organigrama", opciones)
    if indice is None:
        return None

    if indice == len(opciones) - 1:
        valores = _pedir_formulario(root, "Nueva cabeza", {"Nombre/apellido": ""})
        nombre = valores["Nombre/apellido"] if valores else ""
        if not nombre:
            return None
        heads_manager.agregar_cabeza(nombre)
        return nombre

    nombre = nombres[indice]
    if nombre in adicionales:
        if messagebox.askyesno("Guardar cabeza", f"¿Guardar '{nombre}' para usos futuros?"):
            heads_manager.agregar_cabeza(nombre)
    return nombre


def _flujo_organigrama(root: tk.Misc) -> None:
    ruta_excel = filedialog.askopenfilename(
        title="Selecciona el Excel con los datos de empleados",
        filetypes=[("Excel", "*.xlsx *.xls *.xlsm")],
    )
    if not ruta_excel:
        return

    try:
        personas = ExcelParser().leer_excel(ruta_excel)
    except Exception as e:
        messagebox.showerror("Error al leer el Excel", str(e))
        return

    if not personas:
        messagebox.showerror("Sin datos", "No se encontraron datos en el Excel.")
        return

    hierarchy = HierarchyManager(personas)
    reporte = hierarchy.validar_estructura()
    if reporte["advertencias"]:
        messagebox.showwarning("Advertencias", "\n".join(reporte["advertencias"]))

    heads_manager = HeadsManager()
    cabeza = _elegir_cabeza(root, heads_manager, reporte["cabezas_posibles"])
    if not cabeza:
        return

    try:
        nodo_raiz = hierarchy.construir_arbol(cabeza)
    except ValueError as e:
        messagebox.showerror("Error", str(e))
        return

    metadata_actual = (
        heads_manager.obtener_metadata(cabeza) if heads_manager.existe_cabeza(cabeza) else {}
    )
    metadata = _pedir_formulario(
        root,
        f"Datos del organigrama para '{cabeza}'",
        {
            "Departamento": metadata_actual.get("departamento", ""),
            "Centro de costos": metadata_actual.get("centro_costos", ""),
            "Responsable": metadata_actual.get("responsable", ""),
        },
    )
    if metadata is None:
        return

    nombre_sanitizado = cabeza.replace(" ", "_").replace(".", "")
    ruta_pdf = filedialog.asksaveasfilename(
        title="Ubicación del PDF",
        initialfile=f"organigrama_{nombre_sanitizado}.pdf",
        defaultextension=".pdf",
        filetypes=[("PDF", "*.pdf")],
    )
    if not ruta_pdf:
        return

    ruta_base = Path(ruta_pdf)
    ruta_es = ruta_base.with_name(f"{ruta_base.stem}_es.pdf")
    ruta_en = ruta_base.with_name(f"{ruta_base.stem}_en.pdf")

    metadata_normalizada = {
        "departamento": metadata["Departamento"] or "N/A",
        "centro_costos": metadata["Centro de costos"] or "N/A",
        "responsable": metadata["Responsable"] or "N/A",
    }

    renderer = PDFRenderer()
    renderer.generar_pdf(nodo_raiz, str(ruta_es), idioma="es", metadata=metadata_normalizada)
    renderer.generar_pdf(nodo_raiz, str(ruta_en), idioma="en", metadata=metadata_normalizada)
    heads_manager.guardar_metadata(cabeza, metadata_normalizada)

    messagebox.showinfo("Listo", f"Organigramas generados:\n{ruta_es}\n{ruta_en}")


# --- Flujo: Integrar Excels ---


def _resolver_mapeo_gui(
    root: tk.Misc, nombre_archivo: str, df, columnas_canonicas: list[str]
) -> dict[str, str]:
    """Devuelve {columna_canonica: columna_original}, preguntando solo por lo que no calzó
    automáticamente. `columnas_canonicas` se extiende in-place con columnas nuevas."""
    mapeadas, sin_mapear = auto_mapear_columnas(list(df.columns), columnas_canonicas)

    for col in sin_mapear:
        opciones = list(columnas_canonicas) + [f"Es una columna nueva ('{col}')", "Ignorar esta columna"]
        indice = _elegir_opcion(
            root, f"En '{nombre_archivo}', ¿a qué corresponde la columna '{col}'?", opciones
        )
        if indice is None or indice == len(opciones) - 1:
            continue
        if indice == len(opciones) - 2:
            mapeadas[col] = col
            columnas_canonicas.append(col)
        else:
            mapeadas[columnas_canonicas[indice]] = col

    return mapeadas


def _resolver_referencia_faltante_gui(
    root: tk.Misc,
    nombre_archivo: str,
    df,
    mapeo: dict[str, str],
    columna_referencia: str,
    valores_referencia_conocidos: set[str],
) -> bool:
    """Completa mapeo[columna_referencia]; devuelve False si el usuario cancela."""
    candidatas = [c for c in df.columns if c not in mapeo.values()]
    sugerida = sugerir_columna_referencia(df, valores_referencia_conocidos, candidatas)
    if sugerida and messagebox.askyesno(
        "Columna de referencia",
        f"'{nombre_archivo}' no tiene un encabezado para la referencia; "
        f"posible coincidencia por contenido: '{sugerida}'.\n¿Usarla?",
    ):
        mapeo[columna_referencia] = sugerida
        return True

    indice = _elegir_opcion(root, f"Columna de referencia en '{nombre_archivo}'", list(df.columns))
    if indice is None:
        return False
    mapeo[columna_referencia] = list(df.columns)[indice]
    return True


def _resolver_orden_prioridad_gui(root: tk.Misc, rutas: tuple[str, ...]) -> list[int] | None:
    """Pide, uno a uno, cuál archivo va primero en prioridad ante conflictos."""
    nombres = [Path(r).name for r in rutas]
    restantes = list(range(len(rutas)))
    orden: list[int] = []

    while len(restantes) > 1:
        opciones = [nombres[i] for i in restantes]
        indice = _elegir_opcion(
            root, f"Orden de prioridad ante conflictos: elige el archivo #{len(orden) + 1}", opciones
        )
        if indice is None:
            return None
        orden.append(restantes.pop(indice))

    orden.append(restantes[0])
    return orden


def _flujo_integrar(root: tk.Misc) -> None:
    rutas = filedialog.askopenfilenames(
        title="Selecciona los Excels a integrar (mínimo 2)",
        filetypes=[("Excel", "*.xlsx *.xls *.xlsm")],
    )
    if len(rutas) < 2:
        messagebox.showerror("Faltan archivos", "Se necesitan al menos 2 archivos para integrar.")
        return

    try:
        dfs = [leer_hoja(r) for r in rutas]
    except Exception as e:
        messagebox.showerror("Error al leer los Excels", str(e))
        return

    columnas_canonicas = list(dfs[0].columns)
    mapeos = [{c: c for c in columnas_canonicas}]
    for ruta, df in zip(rutas[1:], dfs[1:]):
        mapeos.append(_resolver_mapeo_gui(root, Path(ruta).name, df, columnas_canonicas))

    indice_ref = _elegir_opcion(root, "Columna de referencia para deduplicar", columnas_canonicas)
    if indice_ref is None:
        return
    columna_referencia = columnas_canonicas[indice_ref]

    tablas = []
    valores_referencia_conocidos: set[str] = set()
    for ruta, df, mapeo in zip(rutas, dfs, mapeos):
        if columna_referencia not in mapeo:
            if not _resolver_referencia_faltante_gui(
                root, Path(ruta).name, df, mapeo, columna_referencia, valores_referencia_conocidos
            ):
                return

        tabla = df.rename(columns={original: canonica for canonica, original in mapeo.items()})
        tabla = tabla[list(mapeo.keys())]
        tablas.append(tabla)
        valores_referencia_conocidos |= set(
            tabla[columna_referencia].dropna().astype(str).str.strip()
        )

    orden_prioridad = _resolver_orden_prioridad_gui(root, rutas)
    if orden_prioridad is None:
        return

    resultado = combinar(tablas, columna_referencia, orden_prioridad)

    ruta_salida = filedialog.asksaveasfilename(
        title="Guardar CSV maestro",
        initialfile="integrado.csv",
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
    )
    if not ruta_salida:
        return

    resultado.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    messagebox.showinfo(
        "Listo",
        f"Integración completa: {len(resultado)} filas únicas por '{columna_referencia}'.\n{ruta_salida}",
    )


# --- Ventana principal ---


def _crear_ventana_principal() -> tk.Tk:
    root = tk.Tk()
    root.title("Generador de Organigramas")
    root.geometry("360x200")

    tk.Label(root, text="Generador de Organigramas", font=("", 14, "bold")).pack(pady=(20, 10))

    def ejecutar(flujo) -> None:
        try:
            flujo(root)
        except Exception as e:
            logger.error("Error inesperado: %s", e, exc_info=True)
            messagebox.showerror("Error inesperado", str(e))

    tk.Button(
        root, text="Generar organigrama", width=30, command=lambda: ejecutar(_flujo_organigrama)
    ).pack(pady=5)
    tk.Button(
        root, text="Integrar Excels", width=30, command=lambda: ejecutar(_flujo_integrar)
    ).pack(pady=5)
    tk.Button(root, text="Salir", width=30, command=root.destroy).pack(pady=5)

    return root


def main() -> None:
    """Punto de entrada de la interfaz gráfica."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    root = _crear_ventana_principal()
    root.mainloop()


if __name__ == "__main__":
    main()
