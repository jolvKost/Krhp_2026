"""Gestor de cabezas (personas raíz) para persistencia e interfaz CLI.

Una cabeza se guarda por Nº pers., no por nombre: el extracto SAP se actualiza
constantemente, y el Nº pers. es lo unico que sigue apuntando a la misma persona
entre corridas. El nombre viaja junto pero solo para desplegarlo en el menu.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from .models import Persona

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

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def cargar_cabezas(self) -> List[Dict[str, str]]:
        """
        Carga las cabezas guardadas como [{"numero_personal": ..., "nombre": ...}].

        Tolera el formato viejo (lista de nombres sueltos) degradandolo a una
        cabeza sin Nº pers., que el menu mostrara como no disponible: un nombre
        no basta para identificar a nadie.
        """
        data = self._leer_json()
        cabezas = []
        for entrada in data.get("cabezas", []):
            if isinstance(entrada, dict):
                cabezas.append(
                    {
                        "numero_personal": str(entrada.get("numero_personal", "")),
                        "nombre": entrada.get("nombre", ""),
                    }
                )
            else:  # formato viejo: solo el nombre
                cabezas.append({"numero_personal": "", "nombre": str(entrada)})

        if cabezas:
            logger.info(f"Se cargaron {len(cabezas)} cabezas existentes")
        return cabezas

    def _leer_json(self) -> Dict[str, Any]:
        """Lee el contenido del archivo JSON o devuelve un diccionario vacío."""
        if not self.archivo_heads.exists():
            return {}
        try:
            with open(self.archivo_heads, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"Error al leer heads.json: {e}")
            return {}

    def _guardar_json(self, data: Dict[str, Any]) -> None:
        """Persiste el contenido JSON del gestor."""
        with open(self.archivo_heads, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def existe_cabeza(self, numero_personal: str) -> bool:
        """Indica si una cabeza ya existe en el registro."""
        return any(c["numero_personal"] == str(numero_personal) for c in self.cabezas)

    def agregar_cabeza(self, numero_personal: str, nombre: str) -> bool:
        """
        Agrega una nueva cabeza si no existe ya.

        Returns:
            True si se agregó, False si ya existía
        """
        numero_personal = str(numero_personal)
        if self.existe_cabeza(numero_personal):
            logger.info(f"Cabeza ya existe: Nº pers. {numero_personal}")
            return False

        data = self._leer_json()
        data.setdefault("cabezas", [])
        data["cabezas"].append({"numero_personal": numero_personal, "nombre": nombre})
        self._guardar_json(data)
        self.cabezas = self.cargar_cabezas()
        logger.info(f"Cabeza agregada: Nº pers. {numero_personal}")
        return True

    def eliminar_cabeza(self, numero_personal: str) -> bool:
        """
        Elimina una cabeza existente.

        Returns:
            True si se eliminó, False si no existía
        """
        numero_personal = str(numero_personal)
        if not self.existe_cabeza(numero_personal):
            logger.info(f"Cabeza no encontrada: Nº pers. {numero_personal}")
            return False

        data = self._leer_json()
        data["cabezas"] = [
            c
            for c in data.get("cabezas", [])
            if not (isinstance(c, dict) and str(c.get("numero_personal")) == numero_personal)
        ]
        self._guardar_json(data)
        self.cabezas = self.cargar_cabezas()
        logger.info(f"Cabeza eliminada: Nº pers. {numero_personal}")
        return True

    def guardar_metadata(
        self, numero_personal: str, nombre: str, metadata: Dict[str, Any]
    ) -> None:
        """Guarda los datos asociados a una cabeza, indexados por Nº pers."""
        numero_personal = str(numero_personal)
        data = self._leer_json()
        data.setdefault("cabezas", [])

        if not any(
            isinstance(c, dict) and str(c.get("numero_personal")) == numero_personal
            for c in data["cabezas"]
        ):
            data["cabezas"].append({"numero_personal": numero_personal, "nombre": nombre})

        data.setdefault("metadata", {})
        data["metadata"][numero_personal] = {
            "departamento": metadata.get("departamento"),
            "centro_costos": metadata.get("centro_costos"),
            "responsable": metadata.get("responsable"),
        }
        self._guardar_json(data)
        self.cabezas = self.cargar_cabezas()

    def obtener_metadata(self, numero_personal: str) -> Dict[str, Any]:
        """Devuelve la metadata guardada para una cabeza o valores vacíos."""
        data = self._leer_json()
        metadata = data.get("metadata", {}).get(str(numero_personal), {})
        return {
            "departamento": metadata.get("departamento") or "",
            "centro_costos": metadata.get("centro_costos") or "",
            "responsable": metadata.get("responsable") or "",
        }

    # ------------------------------------------------------------------
    # Interfaz CLI
    # ------------------------------------------------------------------

    @staticmethod
    def _etiqueta(persona: Persona) -> str:
        """Como se muestra una persona: el Nº pers. primero, porque es la identidad."""
        return f"{persona.numero_personal} — {persona.nombre_abreviado}"

    def interfaz_seleccion_interactiva(
        self,
        cabezas_disponibles: List[Persona],
        buscar: Optional[Callable[[str], List[Persona]]] = None,
    ) -> str | None:
        """
        Interfaz interactiva CLI para seleccionar una cabeza.

        Args:
            cabezas_disponibles: Personas sin jefe resuelto en el Excel actual
            buscar: Callable texto -> [Persona] para la busqueda libre (opcion 3)

        Returns:
            Nº pers. de la cabeza seleccionada, o None si se cancela
        """
        print("\n" + "=" * 60)
        print("GENERADOR DE ORGANIGRAMAS")
        print("=" * 60)

        numeros_disponibles = {p.numero_personal for p in cabezas_disponibles}

        if self.cabezas:
            print("\n📋 Cabezas guardadas:")
            for i, cabeza in enumerate(self.cabezas, 1):
                disponible = "✓" if cabeza["numero_personal"] in numeros_disponibles else "✗"
                numero = cabeza["numero_personal"] or "sin Nº pers."
                print(f"   {i}. {numero} — {cabeza['nombre']} {disponible}")
            print("   (✓ = disponible en Excel actual | ✗ = no disponible)")
        else:
            print("\n📋 No hay cabezas guardadas aún.")

        print(f"\n📊 Cabezas disponibles en Excel ({len(cabezas_disponibles)}):")
        for i, persona in enumerate(cabezas_disponibles[:10], 1):
            print(f"   {i}. {self._etiqueta(persona)}")
        if len(cabezas_disponibles) > 10:
            print(f"   ... y {len(cabezas_disponibles) - 10} más")

        print("\n" + "-" * 60)
        print("Opciones:")
        print("  1. Seleccionar una cabeza guardada")
        print("  2. Seleccionar una cabeza del Excel")
        print("  3. Buscar por Nº pers. o nombre")
        print("  0. Cancelar")
        print("-" * 60)

        while True:
            opcion = input("\n¿Qué deseas hacer? (0-3): ").strip()

            if opcion == "0":
                print("Operación cancelada.")
                return None
            elif opcion == "1":
                return self._seleccionar_cabeza_guardada(numeros_disponibles)
            elif opcion == "2":
                return self._seleccionar_cabeza_excel(cabezas_disponibles)
            elif opcion == "3":
                return self._buscar_cabeza(buscar)
            else:
                print("❌ Opción inválida. Intenta de nuevo.")

    def _seleccionar_cabeza_guardada(self, numeros_disponibles: set) -> str | None:
        """Permite seleccionar una cabeza de las guardadas."""
        if not self.cabezas:
            print("❌ No hay cabezas guardadas.")
            return None

        print("\n📋 Selecciona una cabeza guardada:")
        for i, cabeza in enumerate(self.cabezas, 1):
            numero = cabeza["numero_personal"] or "sin Nº pers."
            print(f"  {i}. {numero} — {cabeza['nombre']}")
        print("  0. Atrás")

        while True:
            opcion = input(f"\nSelección (0-{len(self.cabezas)}): ").strip()

            if opcion == "0":
                return None

            try:
                idx = int(opcion) - 1
            except ValueError:
                print("❌ Entrada inválida. Ingresa un número.")
                continue

            if not (0 <= idx < len(self.cabezas)):
                print("❌ Opción inválida.")
                continue

            cabeza = self.cabezas[idx]
            if not cabeza["numero_personal"]:
                # Entrada del formato viejo: sin Nº pers. no se puede identificar.
                print("❌ Esa cabeza se guardó sin Nº pers. Búscala con la opción 3.")
                return None
            if cabeza["numero_personal"] not in numeros_disponibles:
                print(
                    f"⚠️  Nº pers. {cabeza['numero_personal']} no aparece como cabeza "
                    "en este Excel; se intentará construir el árbol igualmente."
                )
            print(f"✓ Seleccionada: {cabeza['numero_personal']} — {cabeza['nombre']}")
            return cabeza["numero_personal"]

    def _seleccionar_cabeza_excel(self, cabezas_disponibles: List[Persona]) -> str | None:
        """Permite seleccionar una cabeza de las disponibles en Excel."""
        if not cabezas_disponibles:
            print("❌ No hay cabezas disponibles en Excel.")
            return None

        print("\n📊 Selecciona una cabeza del Excel:")
        for i, persona in enumerate(cabezas_disponibles, 1):
            print(f"  {i}. {self._etiqueta(persona)}")
        print("  0. Atrás")

        while True:
            opcion = input(f"\nSelección (0-{len(cabezas_disponibles)}): ").strip()

            if opcion == "0":
                return None

            try:
                idx = int(opcion) - 1
            except ValueError:
                print("❌ Entrada inválida. Ingresa un número.")
                continue

            if 0 <= idx < len(cabezas_disponibles):
                return self._confirmar_seleccion(cabezas_disponibles[idx])
            print("❌ Opción inválida.")

    def _buscar_cabeza(self, buscar: Optional[Callable[[str], List[Persona]]]) -> str | None:
        """
        Busca una cabeza por Nº pers. o nombre entre TODAS las personas del Excel.

        Siempre devuelve el Nº pers. de alguien que existe: antes esta opcion
        aceptaba texto libre y guardaba cabezas fantasma que nunca resolvian.
        """
        if buscar is None:
            print("❌ Búsqueda no disponible.")
            return None

        texto = input("\n🔎 Nº pers. o parte del nombre: ").strip()
        if not texto:
            print("❌ Búsqueda vacía.")
            return None

        coincidencias = buscar(texto)
        if not coincidencias:
            print(f"❌ Sin coincidencias para '{texto}'.")
            return None

        if len(coincidencias) > 20:
            print(f"⚠️  {len(coincidencias)} coincidencias; se muestran las primeras 20.")
            coincidencias = coincidencias[:20]

        print("\nCoincidencias:")
        for i, persona in enumerate(coincidencias, 1):
            print(f"  {i}. {self._etiqueta(persona)}")
        print("  0. Atrás")

        while True:
            opcion = input(f"\nSelección (0-{len(coincidencias)}): ").strip()

            if opcion == "0":
                return None

            try:
                idx = int(opcion) - 1
            except ValueError:
                print("❌ Entrada inválida. Ingresa un número.")
                continue

            if 0 <= idx < len(coincidencias):
                return self._confirmar_seleccion(coincidencias[idx])
            print("❌ Opción inválida.")

    def _confirmar_seleccion(self, persona: Persona) -> str:
        """Ofrece guardar la cabeza elegida y devuelve su Nº pers."""
        etiqueta = self._etiqueta(persona)
        if not self.existe_cabeza(persona.numero_personal):
            guardar = input(f"\n¿Guardar '{etiqueta}' para usos futuros? (s/n): ").strip().lower()
            if guardar == "s":
                self.agregar_cabeza(persona.numero_personal, persona.nombre_abreviado)

        print(f"✓ Seleccionada: {etiqueta}")
        return persona.numero_personal
