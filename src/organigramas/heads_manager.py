"""Gestor de cabezas (personas raíz) para persistencia e interfaz CLI."""

import json
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class HeadsManager:
    """Gestiona la persistencia y selección de cabezas (personas raíz)."""
    
    def __init__(self, archivo_heads: str = "data/heads.json"):
        """
        Inicializa el gestor de cabezas.
        
        Args:
            archivo_heads: Ruta al archivo JSON de persistencia
        """
        self.archivo_heads = Path(archivo_heads)
        self.archivo_heads.parent.mkdir(parents=True, exist_ok=True)
        self.cabezas = self.cargar_cabezas()
    
    def cargar_cabezas(self) -> List[str]:
        """
        Carga la lista de cabezas desde el archivo JSON.
        
        Returns:
            Lista de nombres de cabezas (puede estar vacía)
        """
        if not self.archivo_heads.exists():
            logger.info(f"Archivo de cabezas no existe: {self.archivo_heads}")
            return []
        
        try:
            with open(self.archivo_heads, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cabezas = data.get("cabezas", [])
                logger.info(f"Se cargaron {len(cabezas)} cabezas existentes")
                return cabezas
        except Exception as e:
            logger.error(f"Error al cargar heads.json: {e}")
            return []
    
    def guardar_cabezas(self, cabezas: List[str]) -> None:
        """
        Guarda la lista de cabezas en el archivo JSON.
        
        Args:
            cabezas: Lista de nombres de cabezas
        """
        data = {"cabezas": list(set(cabezas))}  # Eliminar duplicados
        
        try:
            with open(self.archivo_heads, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                self.cabezas = data["cabezas"]
                logger.info(f"Guardadas {len(self.cabezas)} cabezas en {self.archivo_heads}")
        except Exception as e:
            logger.error(f"Error al guardar heads.json: {e}")
            raise
    
    def agregar_cabeza(self, nombre: str) -> bool:
        """
        Agrega una nueva cabeza si no existe ya.
        
        Args:
            nombre: Nombre de la cabeza a agregar
            
        Returns:
            True si se agregó, False si ya existía
        """
        if nombre in self.cabezas:
            logger.info(f"Cabeza ya existe: {nombre}")
            return False
        
        self.cabezas.append(nombre)
        self.guardar_cabezas(self.cabezas)
        logger.info(f"Cabeza agregada: {nombre}")
        return True
    
    def eliminar_cabeza(self, nombre: str) -> bool:
        """
        Elimina una cabeza existente.
        
        Args:
            nombre: Nombre de la cabeza a eliminar
            
        Returns:
            True si se eliminó, False si no existía
        """
        if nombre not in self.cabezas:
            logger.info(f"Cabeza no encontrada: {nombre}")
            return False
        
        self.cabezas.remove(nombre)
        self.guardar_cabezas(self.cabezas)
        logger.info(f"Cabeza eliminada: {nombre}")
        return True
    
    def interfaz_seleccion_interactiva(
        self,
        cabezas_disponibles: List[str]
    ) -> str | None:
        """
        Proporciona interfaz interactiva CLI para seleccionar o agregar una cabeza.
        
        Args:
            cabezas_disponibles: Lista de cabezas válidas disponibles (del Excel)
            
        Returns:
            Nombre de la cabeza seleccionada o agregada, o None si se cancela
        """
        print("\n" + "="*60)
        print("GENERADOR DE ORGANIGRAMAS")
        print("="*60)
        
        # Mostrar cabezas guardadas
        if self.cabezas:
            print("\n📋 Cabezas guardadas:")
            for i, cabeza in enumerate(self.cabezas, 1):
                # Indicar si está disponible en el Excel actual
                disponible = "✓" if cabeza in cabezas_disponibles else "✗"
                print(f"   {i}. {cabeza} {disponible}")
            print(f"   (✓ = disponible en Excel actual | ✗ = no disponible)")
        else:
            print("\n📋 No hay cabezas guardadas aún.")
        
        # Mostrar cabezas disponibles en el Excel
        print(f"\n📊 Cabezas disponibles en Excel ({len(cabezas_disponibles)}):")
        for i, cabeza in enumerate(cabezas_disponibles[:10], 1):
            print(f"   {i}. {cabeza}")
        if len(cabezas_disponibles) > 10:
            print(f"   ... y {len(cabezas_disponibles) - 10} más")
        
        print("\n" + "-"*60)
        print("Opciones:")
        print("  1. Seleccionar una cabeza guardada")
        print("  2. Seleccionar una cabeza del Excel")
        print("  3. Agregar una nueva cabeza y guardarla")
        print("  0. Cancelar")
        print("-"*60)
        
        while True:
            opcion = input("\n¿Qué deseas hacer? (0-3): ").strip()
            
            if opcion == "0":
                print("Operación cancelada.")
                return None
            
            elif opcion == "1":
                return self._seleccionar_cabeza_guardada()
            
            elif opcion == "2":
                return self._seleccionar_cabeza_excel(cabezas_disponibles)
            
            elif opcion == "3":
                return self._agregar_cabeza_nueva(cabezas_disponibles)
            
            else:
                print("❌ Opción inválida. Intenta de nuevo.")
    
    def _seleccionar_cabeza_guardada(self) -> str | None:
        """Permite seleccionar una cabeza de las guardadas."""
        if not self.cabezas:
            print("❌ No hay cabezas guardadas.")
            return None
        
        print("\n📋 Selecciona una cabeza guardada:")
        for i, cabeza in enumerate(self.cabezas, 1):
            print(f"  {i}. {cabeza}")
        print("  0. Atrás")
        
        while True:
            try:
                opcion = input("\nSelección (0-{}): ".format(len(self.cabezas))).strip()
                
                if opcion == "0":
                    return None
                
                idx = int(opcion) - 1
                if 0 <= idx < len(self.cabezas):
                    cabeza = self.cabezas[idx]
                    print(f"✓ Seleccionada: {cabeza}")
                    return cabeza
                else:
                    print("❌ Opción inválida.")
            except ValueError:
                print("❌ Entrada inválida. Ingresa un número.")
    
    def _seleccionar_cabeza_excel(self, cabezas_disponibles: List[str]) -> str | None:
        """Permite seleccionar una cabeza de las disponibles en Excel."""
        if not cabezas_disponibles:
            print("❌ No hay cabezas disponibles en Excel.")
            return None
        
        print("\n📊 Selecciona una cabeza del Excel:")
        for i, cabeza in enumerate(cabezas_disponibles, 1):
            print(f"  {i}. {cabeza}")
        print("  0. Atrás")
        
        while True:
            try:
                opcion = input("\nSelección (0-{}): ".format(len(cabezas_disponibles))).strip()
                
                if opcion == "0":
                    return None
                
                idx = int(opcion) - 1
                if 0 <= idx < len(cabezas_disponibles):
                    cabeza = cabezas_disponibles[idx]
                    
                    # Preguntar si guardarla
                    guardar = input(f"\n¿Guardar '{cabeza}' para usos futuros? (s/n): ").strip().lower()
                    if guardar == 's':
                        self.agregar_cabeza(cabeza)
                    
                    print(f"✓ Seleccionada: {cabeza}")
                    return cabeza
                else:
                    print("❌ Opción inválida.")
            except ValueError:
                print("❌ Entrada inválida. Ingresa un número.")
    
    def _agregar_cabeza_nueva(self, cabezas_disponibles: List[str]) -> str | None:
        """Permite agregar una nueva cabeza manualmente."""
        print("\n➕ Agregar nueva cabeza")
        print(f"Cabezas disponibles en Excel: {', '.join(cabezas_disponibles[:5])}")
        if len(cabezas_disponibles) > 5:
            print(f"... y {len(cabezas_disponibles) - 5} más")
        
        nombre = input("\nIngresa el nombre/apellido de la cabeza: ").strip()
        
        if not nombre:
            print("❌ Nombre vacío.")
            return None
        
        # Verificar si existe en disponibles (sugerencia)
        coincidencias = [c for c in cabezas_disponibles if nombre.lower() in c.lower()]
        if not coincidencias:
            print(f"⚠️  Advertencia: '{nombre}' no se encontró en las cabezas disponibles del Excel.")
            confirmar = input("¿Continuar igualmente? (s/n): ").strip().lower()
            if confirmar != 's':
                return None
        else:
            print(f"✓ Encontradas coincidencias: {coincidencias[:3]}")
        
        self.agregar_cabeza(nombre)
        print(f"✓ Cabeza agregada: {nombre}")
        return nombre
