"""Gestión de jerarquía y construcción de árboles organizacionales."""

import logging
from typing import List, Dict, Optional
from .models import Persona, Nodo

logger = logging.getLogger(__name__)


class HierarchyManager:
    """Gestiona la construcción y validación de árboles jerárquicos."""
    
    def __init__(self, personas: List[Persona]):
        """
        Inicializa el gestor con una lista de personas.
        
        Args:
            personas: Lista de objetos Persona
        """
        self.personas = personas
        self.personas_por_nombre: Dict[str, List[Persona]] = {}
        self._indexar_personas()

    def _indexar_personas(self) -> None:
        """Crea índice de personas por nombre (case-insensitive).

        Cada clave mapea a una lista de personas: si más de una persona
        comparte el mismo nombre, la clave queda marcada como ambigua en
        vez de resolverse silenciosamente a la última persona indexada.
        """
        self.personas_por_nombre = {}
        for persona in self.personas:
            claves = {
                persona.nombre_abreviado.lower(),
                persona.nombre_completo.lower(),
                # También por nombre abreviado sin puntos
                persona.nombre_abreviado.replace(".", "").strip().lower(),
            }
            for clave in claves:
                self.personas_por_nombre.setdefault(clave, []).append(persona)
    
    def construir_arbol(self, cabeza_nombre: str) -> Nodo:
        """
        Construye un árbol jerárquico con la persona especificada como raíz.
        
        Args:
            cabeza_nombre: Nombre (abreviado o completo) de la persona raíz
            
        Returns:
            Nodo raíz del árbol construido
            
        Raises:
            ValueError: Si la cabeza no existe o si hay ciclos en la estructura
        """
        # Buscar la cabeza
        cabeza = self._buscar_persona(cabeza_nombre)
        if not cabeza:
            raise ValueError(
                f"No se encontró persona con nombre '{cabeza_nombre}'. "
                f"Personas disponibles: {[p.nombre_abreviado for p in self.personas[:5]]}"
            )
        
        logger.info(f"Construyendo árbol para cabeza: {cabeza.nombre_abreviado}")
        
        # Crear nodo raíz
        nodo_raiz = Nodo(persona=cabeza)
        
        # Construir árbol recursivamente
        visitados = set()
        self._construir_arbol_recursivo(nodo_raiz, visitados)
        
        logger.info(
            f"Árbol construido: {len(nodo_raiz.obtener_todos_descendientes())} personas, "
            f"profundidad {nodo_raiz.profundidad() + 1}"
        )
        
        return nodo_raiz
    
    def _construir_arbol_recursivo(self, nodo_padre: Nodo, visitados: set) -> None:
        """
        Construye recursivamente el subárbol de un nodo.
        
        Args:
            nodo_padre: Nodo padre
            visitados: Conjunto de personas ya visitadas (para detectar ciclos)
        """
        # Marcar como visitado
        visitados.add(nodo_padre.persona.numero_personal)
        
        # Buscar subordinados (personas cuyo supervisor es este nodo)
        subordinados = self._buscar_subordinados(nodo_padre.persona)
        
        for subordinado in subordinados:
            # Validar que no hay ciclo
            if subordinado.numero_personal in visitados:
                logger.warning(
                    f"Ciclo detectado: {nodo_padre.persona.nombre_abreviado} -> "
                    f"{subordinado.nombre_abreviado}"
                )
                continue
            
            # Crear nodo hijo y agregarlo
            nodo_hijo = Nodo(persona=subordinado)
            nodo_padre.agregar_hijo(nodo_hijo)
            
            # Recursar
            self._construir_arbol_recursivo(nodo_hijo, visitados.copy())
    
    def _buscar_persona(self, nombre: str) -> Optional[Persona]:
        """
        Busca una persona por nombre (case-insensitive).

        Args:
            nombre: Nombre a buscar

        Returns:
            Objeto Persona si el nombre resuelve a exactamente una persona,
            None si no se encuentra o si el nombre es ambiguo (coincide con
            más de una persona).
        """
        nombre_lower = nombre.strip().lower()
        candidatos = self.personas_por_nombre.get(nombre_lower, [])
        if len(candidatos) == 1:
            return candidatos[0]
        if len(candidatos) > 1:
            logger.warning(
                f"Nombre ambiguo '{nombre}': coincide con {len(candidatos)} personas "
                f"(números de personal: {[p.numero_personal for p in candidatos]}). "
                f"No se puede resolver de forma única."
            )
        return None

    def obtener_nombres_ambiguos(self) -> Dict[str, int]:
        """
        Retorna los nombres del índice que coinciden con más de una persona.

        Returns:
            Diccionario {nombre: cantidad de personas que coinciden}
        """
        return {
            nombre: len(personas)
            for nombre, personas in self.personas_por_nombre.items()
            if len(personas) > 1
        }
    
    def _buscar_subordinados(self, supervisor: Persona) -> List[Persona]:
        """
        Busca todas las personas que reportan directamente a un supervisor.
        
        Args:
            supervisor: Persona supervisora
            
        Returns:
            Lista de personas subordinadas
        """
        subordinados = []
        
        for persona in self.personas:
            if persona.numero_personal == supervisor.numero_personal:
                continue  # No incluir al supervisor a sí mismo
            
            # Buscar si el supervisor de esta persona coincide
            if persona.supervisor_nombre:
                persona_supervisor = self._buscar_persona(persona.supervisor_nombre)
                if persona_supervisor and persona_supervisor.numero_personal == supervisor.numero_personal:
                    subordinados.append(persona)
        
        return subordinados
    
    def obtener_todas_las_cabezas_posibles(self) -> List[Persona]:
        """
        Retorna lista de todas las personas que pueden ser cabezas válidas
        (típicamente aquellas sin supervisor o con supervisor no encontrado).
        
        Returns:
            Lista de Persona que pueden ser cabezas
        """
        cabezas_posibles = []
        
        for persona in self.personas:
            # Si no tiene supervisor, puede ser cabeza
            if not persona.supervisor_nombre:
                cabezas_posibles.append(persona)
            else:
                # Si el supervisor no existe en la base de datos, también puede ser cabeza
                if not self._buscar_persona(persona.supervisor_nombre):
                    cabezas_posibles.append(persona)
        
        return cabezas_posibles
    
    def validar_estructura(self) -> Dict[str, any]:
        """
        Valida la estructura de datos y retorna un reporte.
        
        Returns:
            Diccionario con validaciones y advertencias
        """
        reporte = {
            "total_personas": len(self.personas),
            "cabezas_posibles": [],
            "advertencias": [],
            "errores": []
        }
        
        # Buscar cabezas posibles
        cabezas = self.obtener_todas_las_cabezas_posibles()
        reporte["cabezas_posibles"] = [p.nombre_abreviado for p in cabezas]
        
        # Validar supervisores
        supervisores_no_encontrados = set()
        for persona in self.personas:
            if persona.supervisor_nombre:
                if not self._buscar_persona(persona.supervisor_nombre):
                    supervisores_no_encontrados.add(persona.supervisor_nombre)
        
        if supervisores_no_encontrados:
            reporte["advertencias"].append(
                f"Supervisores no encontrados: {', '.join(supervisores_no_encontrados)}"
            )

        # Validar nombres ambiguos (colisiones en el índice de búsqueda)
        nombres_ambiguos = self.obtener_nombres_ambiguos()
        if nombres_ambiguos:
            ejemplos = ", ".join(
                f"'{nombre}' ({cantidad} personas)"
                for nombre, cantidad in list(nombres_ambiguos.items())[:5]
            )
            reporte["advertencias"].append(
                f"Nombres ambiguos (coinciden con más de una persona): "
                f"{len(nombres_ambiguos)} casos. Ejemplos: {ejemplos}"
            )

        return reporte
