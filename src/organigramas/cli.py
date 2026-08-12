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
        
        # 6. Generar PDF
        print("\n📄 Generando PDF...")
        ruta_pdf = _solicitar_ubicacion_pdf(cabeza_seleccionada)
        if not ruta_pdf:
            print("❌ Operación cancelada.")
            return 1
        
        renderer = PDFRenderer()
        renderer.generar_pdf(nodo_raiz, ruta_pdf)
        
        print(f"\n✅ ¡Éxito! Organigrama generado en: {ruta_pdf}")
        
        # 7. Ofrecer generar otro
        print("\n" + "="*60)
        generar_otro = input("¿Generar otro organigrama? (s/n): ").strip().lower()
        if generar_otro == 's':
            return main()  # Recursivamente llamar main
        
        print("Gracias por usar el Generador de Organigramas.")
        return 0
    
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario.")
        return 1
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        print(f"\n❌ Error inesperado: {e}")
        return 1


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
