#!/usr/bin/env python3
"""Script de prueba para validar que todos los módulos se importan correctamente."""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Prueba que todos los módulos se importan sin errores."""
    print("🧪 Prueba de importaciones...")
    
    try:
        print("  1. Importando models...", end=" ")
        from organigramas.models import Persona, Nodo
        print("✓")
        
        print("  2. Importando excel_parser...", end=" ")
        from organigramas.excel_parser import ExcelParser
        print("✓")
        
        print("  3. Importando hierarchy...", end=" ")
        from organigramas.hierarchy import HierarchyManager
        print("✓")
        
        print("  4. Importando heads_manager...", end=" ")
        from organigramas.heads_manager import HeadsManager
        print("✓")
        
        print("  5. Importando pdf_renderer...", end=" ")
        from organigramas.pdf_renderer import PDFRenderer, Organigrama
        print("✓")
        
        print("  6. Importando cli...", end=" ")
        from organigramas.cli import main
        print("✓")

        print("  7. Importando gui...", end=" ")
        from organigramas.gui import main as gui_main
        print("✓")

        print("\n✅ Todas las importaciones exitosas!")
        return True
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_basic_creation():
    """Prueba la creación básica de objetos."""
    print("\n🧪 Prueba de creación de objetos...")
    
    try:
        from organigramas.models import Persona, Nodo
        
        # Crear una persona
        print("  1. Creando Persona...", end=" ")
        p1 = Persona(
            numero_personal="001",
            nombre_completo="Juan Pérez",
            nombre_abreviado="J. Pérez",
            apellido_paterno="Pérez",
            posicion="Director",
            ceco="1000"
        )
        print("✓")
        
        # Crear nodo
        print("  2. Creando Nodo...", end=" ")
        nodo = Nodo(persona=p1)
        print("✓")
        
        # Agregar hijo
        print("  3. Agregando hijo...", end=" ")
        p2 = Persona(
            numero_personal="002",
            nombre_completo="María García",
            nombre_abreviado="M. García",
            apellido_paterno="García",
            posicion="Gerente",
            ceco="1001",
            supervisor_nombre="J. Pérez"
        )
        nodo_hijo = Nodo(persona=p2)
        nodo.agregar_hijo(nodo_hijo)
        print("✓")
        
        print(f"  4. Verificando árbol...", end=" ")
        assert len(nodo.hijos) == 1
        assert nodo.cantidad_subordinados() == 1
        assert len(nodo.obtener_todos_descendientes()) == 2
        print("✓")
        
        print("\n✅ Creación de objetos exitosa!")
        return True
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = True
    success = test_imports() and success
    success = test_basic_creation() and success
    
    if success:
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS PASARON")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("❌ ALGUNAS PRUEBAS FALLARON")
        print("="*60)
        sys.exit(1)
