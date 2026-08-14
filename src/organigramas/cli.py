"""Interfaz CLI principal del generador de organigramas."""

import sys
import logging
from pathlib import Path

from .excel_parser import ExcelParser
from .hierarchy import HierarchyManager
from .heads_manager import HeadsManager
from .pdf_renderer import PDFRenderer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Función principal de la CLI."""
    try:
        logger.info("Iniciando Generador de Organigramas")
        while True:
            resultado = _generar_organigrama()
            if resultado != 0:
                return resultado

            print("\n" + "="*60)
            generar_otro = input("¿Generar otro organigrama? (s/n): ").strip().lower()
            if generar_otro != 's':
                print("Gracias por usar el Generador de Organigramas.")
                return 0
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario.")
        return 1
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        print(f"\n❌ Error inesperado: {e}")
        return 1


def _generar_organigrama() -> int:
    """Ejecuta un ciclo completo de generación de organigrama."""
    # 1. Solicitar ruta del archivo Excel
    ruta_excel = _solicitar_archivo_excel()
    if not ruta_excel:
        print("❌ Operación cancelada.")
        return 1

    # 2. Cargar datos del Excel
    print("\n📂 Cargando datos del Excel...")
    parser = ExcelParser()
    personas = parser.leer_excel(ruta_excel)

    if not personas:
        print("❌ No se encontraron datos en el Excel.")
        return 1

    print(f"✓ Cargadas {len(personas)} personas")

    # 3. Validar estructura jerárquica
    print("\n🔍 Analizando estructura jerárquica...")
    hierarchy = HierarchyManager(personas)
    reporte = hierarchy.validar_estructura()

    print(f"✓ Encontradas {len(reporte['cabezas_posibles'])} cabezas posibles")
    if reporte['advertencias']:
        for adv in reporte['advertencias']:
            print(f"⚠️  {adv}")

    # 4. Seleccionar cabeza usando HeadsManager
    print("\n👥 Seleccionando cabeza del organigrama...")
    heads_manager = HeadsManager()
    cabeza_seleccionada = heads_manager.interfaz_seleccion_interactiva(
        reporte['cabezas_posibles']
    )

    if not cabeza_seleccionada:
        print("❌ Operación cancelada.")
        return 1

    # 5. Construir árbol jerárquico
    print(f"\n🌳 Construyendo árbol para: {cabeza_seleccionada}")
    try:
        nodo_raiz = hierarchy.construir_arbol(cabeza_seleccionada)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return 1

    metadata_actual = heads_manager.obtener_metadata(cabeza_seleccionada) if heads_manager.existe_cabeza(cabeza_seleccionada) else {}
    metadata = _solicitar_metadata_organigrama(cabeza_seleccionada, metadata_actual)
    if metadata is None:
        print("❌ Operación cancelada.")
        return 1

    # 6. Generar PDF
    print("\n📄 Generando PDF...")
    ruta_pdf = _solicitar_ubicacion_pdf(cabeza_seleccionada)
    if not ruta_pdf:
        print("❌ Operación cancelada.")
        return 1

    ruta_base = Path(ruta_pdf)
    nombre_base = ruta_base.stem
    ruta_es = ruta_base.with_name(f"{nombre_base}_es.pdf")
    ruta_en = ruta_base.with_name(f"{nombre_base}_en.pdf")

    renderer = PDFRenderer()
    renderer.generar_pdf(nodo_raiz, str(ruta_es), idioma="es", metadata=metadata)
    renderer.generar_pdf(nodo_raiz, str(ruta_en), idioma="en", metadata=metadata)
    heads_manager.guardar_metadata(cabeza_seleccionada, metadata)

    print(f"\n✅ ¡Éxito! Organigramas generados en: {ruta_es} y {ruta_en}")
    return 0


def _solicitar_metadata_organigrama(cabeza: str, metadata_actual: dict | None) -> dict | None:
    """Solicita los datos del organigrama, reutilizando valores previos si existen."""
    metadata = metadata_actual or {}
    es_nuevo = not metadata or not any(metadata.get(k) for k in ("departamento", "centro_costos", "responsable"))

    if es_nuevo:
        print(f"\n📝 Datos del organigrama para '{cabeza}'")
        metadata["departamento"] = input("Departamento: ").strip() or "N/A"
        metadata["centro_costos"] = input("Centro de costos: ").strip() or "N/A"
        metadata["responsable"] = input("Responsable: ").strip() or "N/A"
        return metadata

    print(f"\n📝 Datos actuales para '{cabeza}'")
    for clave, valor in metadata.items():
        if valor:
            print(f"  - {clave}: {valor}")

    respuesta = input("¿Desea modificar alguno de estos campos? (s/n): ").strip().lower()
    if respuesta != "s":
        return metadata

    metadata["departamento"] = input(f"Departamento [{metadata.get('departamento') or 'N/A'}]: ").strip() or metadata.get("departamento") or "N/A"
    metadata["centro_costos"] = input(f"Centro de costos [{metadata.get('centro_costos') or 'N/A'}]: ").strip() or metadata.get("centro_costos") or "N/A"
    metadata["responsable"] = input(f"Responsable [{metadata.get('responsable') or 'N/A'}]: ").strip() or metadata.get("responsable") or "N/A"
    return metadata


def _solicitar_archivo_excel() -> str | None:
    """Solicita al usuario la ruta del archivo Excel."""
    print("\n" + "="*60)
    print("GENERADOR DE ORGANIGRAMAS")
    print("="*60)
    
    while True:
        ruta = input("\n📁 Ingresa la ruta al archivo Excel: ").strip()
        
        if not ruta:
            print("❌ Ruta vacía.")
            continue
        
        # Remover comillas si las hay
        ruta = ruta.strip('"\'')
        
        # Verificar que existe
        ruta_path = Path(ruta)
        if not ruta_path.exists():
            print(f"❌ Archivo no encontrado: {ruta}")
            print(f"   Intenta con ruta absoluta o relativa desde: {Path.cwd()}")
            continue
        
        # Verificar extensión
        if ruta_path.suffix.lower() not in ['.xlsx', '.xls', '.xlsm']:
            print(f"❌ El archivo debe ser un Excel (.xlsx, .xls, .xlsm)")
            continue
        
        return ruta


def _solicitar_ubicacion_pdf(nombre_cabeza: str) -> str | None:
    """Solicita al usuario dónde guardar el PDF."""
    # Generar nombre por defecto
    nombre_sanitizado = nombre_cabeza.replace(" ", "_").replace(".", "")
    nombre_default = f"organigrama_{nombre_sanitizado}.pdf"
    
    # Ubicación por defecto: carpeta actual
    ubicacion_default = Path.cwd() / nombre_default
    
    print(f"\n📄 Ubicación de salida (por defecto: {nombre_default})")
    ubicacion = input("Ruta completa del PDF (Enter para usar default): ").strip()
    
    if not ubicacion:
        ubicacion = str(ubicacion_default)
    else:
        ubicacion = ubicacion.strip('"\'')
    
    # Convertir a Path
    ruta_path = Path(ubicacion)
    
    # Si la ruta es un directorio existente o no tiene extensión, construir ruta con nombre de archivo
    if ruta_path.is_dir() or (not ruta_path.suffix):
        ruta_path = ruta_path / nombre_default
    
    # Crear directorio si no existe
    ruta_path.parent.mkdir(parents=True, exist_ok=True)
    
    return str(ruta_path)
