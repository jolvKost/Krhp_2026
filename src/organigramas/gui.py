"""Interfaz gráfica de escritorio (tkinter) para generar organigramas e integrar Excels."""

import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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


# --- Estilo ---


def _configurar_estilo(root: tk.Misc) -> None:
    """Aplica un tema ttk moderno y define estilos reutilizados por toda la GUI."""
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    fondo = "#f4f6f8"
    acento = "#2f6fed"

    estilo.configure(".", background=fondo, font=("Segoe UI", 10))
    estilo.configure("TFrame", background=fondo)
    estilo.configure("TLabel", background=fondo)
    estilo.configure("Card.TFrame", background="#ffffff", relief="flat")
    estilo.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), background=fondo)
    estilo.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#5a6472", background=fondo)
    estilo.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"), background="#ffffff")
    estilo.configure("CardDesc.TLabel", font=("Segoe UI", 9), foreground="#5a6472", background="#ffffff")
    estilo.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=8)
    estilo.map("Accent.TButton", background=[("active", acento)])
    estilo.configure("Counter.TLabel", font=("Segoe UI", 8), foreground="#5a6472", background=fondo)

    if isinstance(root, tk.Tk) or isinstance(root, tk.Toplevel):
        root.configure(background=fondo)


# --- Diálogos genéricos reutilizados por ambos flujos ---


def _filtrar_indices(opciones: list[str], texto: str) -> list[int]:
    """Devuelve los índices de `opciones` cuyo texto contiene `texto` (case-insensitive).

    Sin texto de búsqueda, devuelve todos los índices en orden original. El orden del
    resultado es siempre el orden original de `opciones`, nunca reordenado por relevancia.
    """
    texto = texto.strip().lower()
    if not texto:
        return list(range(len(opciones)))
    return [i for i, opcion in enumerate(opciones) if texto in opcion.lower()]


def _autocheck_filtrar_indices() -> None:
    opciones = ["Ana López", "Juan Pérez", "ana Torres", "Beto Ruiz"]
    assert _filtrar_indices(opciones, "") == [0, 1, 2, 3]
    assert _filtrar_indices(opciones, "ANA") == [0, 2]
    assert _filtrar_indices(opciones, "zzz") == []
    assert _filtrar_indices(opciones, "  juan  ") == [1]


_autocheck_filtrar_indices()


def _elegir_opcion(root: tk.Misc, titulo: str, opciones: list[str]) -> int | None:
    """Muestra una lista modal (con búsqueda) y devuelve el índice elegido, o None si se cancela."""
    if not opciones:
        return None

    ventana = tk.Toplevel(root)
    ventana.title(titulo)
    ventana.transient(root)
    ventana.grab_set()
    ventana.minsize(360, 320)
    ventana.columnconfigure(0, weight=1)
    ventana.rowconfigure(2, weight=1)

    contenedor = ttk.Frame(ventana, padding=12)
    contenedor.grid(row=0, column=0, sticky="nsew")
    contenedor.columnconfigure(0, weight=1)
    ventana.rowconfigure(0, weight=1)
    contenedor.rowconfigure(2, weight=1)

    ttk.Label(contenedor, text=titulo, wraplength=420, style="CardTitle.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )

    busqueda_var = tk.StringVar()
    entrada_busqueda = ttk.Entry(contenedor, textvariable=busqueda_var)
    entrada_busqueda.grid(row=1, column=0, sticky="ew", pady=(0, 6))

    lista_frame = ttk.Frame(contenedor)
    lista_frame.grid(row=2, column=0, sticky="nsew")
    lista_frame.columnconfigure(0, weight=1)
    lista_frame.rowconfigure(0, weight=1)

    lista = tk.Listbox(lista_frame, width=60, height=min(15, len(opciones) + 1), activestyle="dotbox")
    scrollbar = ttk.Scrollbar(lista_frame, orient="vertical", command=lista.yview)
    lista.configure(yscrollcommand=scrollbar.set)
    lista.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    contador = ttk.Label(contenedor, text="", style="Counter.TLabel")
    contador.grid(row=3, column=0, sticky="w", pady=(4, 8))

    indices_visibles: list[int] = []

    def refrescar(*_args: object) -> None:
        indices_visibles.clear()
        indices_visibles.extend(_filtrar_indices(opciones, busqueda_var.get()))
        lista.delete(0, tk.END)
        for i in indices_visibles:
            lista.insert(tk.END, opciones[i])
        if indices_visibles:
            lista.selection_set(0)
        contador.configure(text=f"{len(indices_visibles)} de {len(opciones)}")

    busqueda_var.trace_add("write", refrescar)
    refrescar()

    resultado: dict[str, int | None] = {"indice": None}

    def aceptar(_e: object = None) -> None:
        seleccion = lista.curselection()
        if seleccion:
            resultado["indice"] = indices_visibles[seleccion[0]]
        ventana.destroy()

    def cancelar(_e: object = None) -> None:
        resultado["indice"] = None
        ventana.destroy()

    lista.bind("<Double-Button-1>", aceptar)
    ventana.bind("<Return>", aceptar)
    ventana.bind("<Escape>", cancelar)

    botones = ttk.Frame(contenedor)
    botones.grid(row=4, column=0, pady=(4, 0))
    ttk.Button(botones, text="Aceptar", command=aceptar, style="Accent.TButton").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Button(botones, text="Cancelar", command=cancelar).pack(side=tk.LEFT, padx=5)

    ventana.protocol("WM_DELETE_WINDOW", cancelar)
    entrada_busqueda.focus_set()
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
    ventana.resizable(False, False)

    contenedor = ttk.Frame(ventana, padding=12)
    contenedor.pack(fill=tk.BOTH, expand=True)

    grupo = ttk.LabelFrame(contenedor, text=titulo, padding=10)
    grupo.pack(fill=tk.BOTH, expand=True)

    entradas: dict[str, ttk.Entry] = {}
    primera_entrada: ttk.Entry | None = None
    for i, (etiqueta, valor_default) in enumerate(campos.items()):
        ttk.Label(grupo, text=etiqueta).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=5)
        entrada = ttk.Entry(grupo, width=40)
        entrada.insert(0, valor_default)
        entrada.grid(row=i, column=1, pady=5)
        entradas[etiqueta] = entrada
        if primera_entrada is None:
            primera_entrada = entrada

    resultado: dict[str, dict[str, str] | None] = {"valores": None}

    def aceptar(_e: object = None) -> None:
        resultado["valores"] = {clave: entrada.get().strip() for clave, entrada in entradas.items()}
        ventana.destroy()

    def cancelar(_e: object = None) -> None:
        resultado["valores"] = None
        ventana.destroy()

    botones = ttk.Frame(contenedor)
    botones.pack(pady=(10, 0))
    ttk.Button(botones, text="Aceptar", command=aceptar, style="Accent.TButton").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Button(botones, text="Cancelar", command=cancelar).pack(side=tk.LEFT, padx=5)

    ventana.bind("<Return>", aceptar)
    ventana.bind("<Escape>", cancelar)
    ventana.protocol("WM_DELETE_WINDOW", cancelar)
    if primera_entrada is not None:
        primera_entrada.focus_set()
    root.wait_window(ventana)
    return resultado["valores"]


def _ejecutar_con_progreso(root: tk.Misc, mensaje: str, funcion, *args: object, **kwargs: object):
    """Ejecuta `funcion(*args, **kwargs)` en un hilo mientras muestra un modal con progreso
    indeterminado. Solo el hilo principal toca widgets de Tk; el hilo worker solo calcula
    y reporta el resultado (o la excepción) por una cola. Si `funcion` lanza una excepción,
    se relanza aquí para que el llamador la maneje como si hubiera sido síncrona."""
    ventana = tk.Toplevel(root)
    ventana.title("Procesando...")
    ventana.transient(root)
    ventana.grab_set()
    ventana.resizable(False, False)
    ventana.protocol("WM_DELETE_WINDOW", lambda: None)

    contenedor = ttk.Frame(ventana, padding=20)
    contenedor.pack()
    ttk.Label(contenedor, text=mensaje).pack(pady=(0, 10))
    barra = ttk.Progressbar(contenedor, mode="indeterminate", length=260)
    barra.pack()
    barra.start(10)

    cola: queue.Queue = queue.Queue()

    def trabajar() -> None:
        try:
            resultado = funcion(*args, **kwargs)
            cola.put(("ok", resultado))
        except Exception as exc:  # noqa: BLE001 - se relanza en el hilo principal
            cola.put(("error", exc))

    hilo = threading.Thread(target=trabajar, daemon=True)
    hilo.start()

    salida: dict[str, object] = {}

    def sondear() -> None:
        try:
            estado, valor = cola.get_nowait()
        except queue.Empty:
            root.after(80, sondear)
            return
        salida["estado"] = estado
        salida["valor"] = valor
        barra.stop()
        ventana.grab_release()
        ventana.destroy()

    root.after(80, sondear)
    root.wait_window(ventana)

    if salida.get("estado") == "error":
        raise salida["valor"]  # type: ignore[misc]
    return salida.get("valor")


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
        personas = _ejecutar_con_progreso(
            root, "Leyendo Excel...", ExcelParser().leer_excel, ruta_excel
        )
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

    def _generar_ambos_pdfs() -> None:
        renderer = PDFRenderer()
        renderer.generar_pdf(nodo_raiz, str(ruta_es), idioma="es", metadata=metadata_normalizada)
        renderer.generar_pdf(nodo_raiz, str(ruta_en), idioma="en", metadata=metadata_normalizada)

    try:
        _ejecutar_con_progreso(root, "Generando organigramas...", _generar_ambos_pdfs)
    except Exception as e:
        messagebox.showerror("Error al generar el PDF", str(e))
        return

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
        dfs = _ejecutar_con_progreso(
            root, "Leyendo archivos...", lambda: [leer_hoja(r) for r in rutas]
        )
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

    try:
        resultado = _ejecutar_con_progreso(
            root, "Combinando datos...", combinar, tablas, columna_referencia, orden_prioridad
        )
    except Exception as e:
        messagebox.showerror("Error al combinar", str(e))
        return

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


def _crear_tarjeta_accion(
    padre: tk.Misc, icono: str, titulo: str, descripcion: str, comando
) -> ttk.Frame:
    tarjeta = ttk.Frame(padre, style="Card.TFrame", padding=16)
    tarjeta.columnconfigure(1, weight=1)

    ttk.Label(tarjeta, text=icono, font=("Segoe UI", 20), style="CardTitle.TLabel").grid(
        row=0, column=0, rowspan=2, padx=(0, 14), sticky="n"
    )
    ttk.Label(tarjeta, text=titulo, style="CardTitle.TLabel").grid(row=0, column=1, sticky="w")
    ttk.Label(tarjeta, text=descripcion, style="CardDesc.TLabel", wraplength=340).grid(
        row=1, column=1, sticky="w", pady=(2, 10)
    )
    ttk.Button(tarjeta, text=titulo, command=comando, style="Accent.TButton").grid(
        row=2, column=1, sticky="w"
    )
    return tarjeta


def _crear_ventana_principal() -> tk.Tk:
    root = tk.Tk()
    root.title("Generador de Organigramas")
    root.geometry("580x540")
    root.minsize(500, 480)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    _configurar_estilo(root)

    contenedor = ttk.Frame(root, padding=20)
    contenedor.grid(row=0, column=0, sticky="nsew")
    contenedor.columnconfigure(0, weight=1)

    ttk.Label(contenedor, text="Generador de Organigramas", style="Title.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        contenedor,
        text="Genera organigramas jerárquicos bilingües a partir de tus datos de Excel.",
        style="Subtitle.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(2, 18))

    def ejecutar(flujo) -> None:
        try:
            flujo(root)
        except Exception as e:
            logger.error("Error inesperado: %s", e, exc_info=True)
            messagebox.showerror("Error inesperado", str(e))

    _crear_tarjeta_accion(
        contenedor,
        "🗂",
        "Generar organigrama",
        "Elige un Excel de empleados, selecciona una cabeza y genera el PDF jerárquico en español e inglés.",
        lambda: ejecutar(_flujo_organigrama),
    ).grid(row=2, column=0, sticky="ew", pady=(0, 12))

    _crear_tarjeta_accion(
        contenedor,
        "🔗",
        "Integrar Excels",
        "Combina dos o más Excels en un solo CSV maestro, resolviendo columnas y duplicados.",
        lambda: ejecutar(_flujo_integrar),
    ).grid(row=3, column=0, sticky="ew")

    contenedor.rowconfigure(4, weight=1)
    ttk.Button(contenedor, text="Salir", command=root.destroy).grid(
        row=5, column=0, sticky="e", pady=(12, 0)
    )

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
