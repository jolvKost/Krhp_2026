"""Gestión de jerarquía y construcción de árboles organizacionales."""

import logging
import unicodedata
from typing import List, Dict, Optional
from .models import Persona, Nodo

logger = logging.getLogger(__name__)


def normalizar_nombre(texto) -> str:
    """
    Minúsculas, sin acentos, sin puntuación, espacios colapsados.

    Se descarta la puntuación porque el extracto SAP entrega el jefe directo
    encomillado: '"PEREZ, JUAN"'. El ORDEN de los tokens se conserva, así que
    "Apellido Nombre" y "Nombre Apellido" siguen siendo distintos.
    """
    plano = str(texto).casefold()
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", plano) if not unicodedata.combining(c)
    )
    solo_texto = "".join(c if (c.isalnum() or c.isspace()) else " " for c in sin_acentos)
    return " ".join(solo_texto.split())


class HierarchyManager:
    """Gestiona la construcción y validación de árboles jerárquicos."""
    
    def __init__(self, personas: List[Persona]):
        """
        Inicializa el gestor con una lista de personas.
        
        Args:
            personas: Lista de objetos Persona
        """
        self.personas = personas
        self.personas_por_nombre: Dict[str, Persona] = {}
        self._indexar_personas()
    
    def _indexar_personas(self) -> None:
        """
        Crea índice de personas por nombre (normalizado).

        La clave que importa para la jerarquía es "Apellido Paterno + Nombre(s)":
        es el formato en que el extracto SAP nombra al jefe directo
        ("PEREZ, JUAN PEDRO"). Las demás claves se conservan porque heads.json
        guarda las cabezas por nombre_abreviado.
        """
        for persona in self.personas:
            claves = {
                normalizar_nombre(f"{persona.apellido_paterno} {persona.nombre_completo}"),
                normalizar_nombre(persona.nombre_abreviado),
                normalizar_nombre(persona.nombre_completo),
            }
            for clave in claves:
                previa = self.personas_por_nombre.get(clave)
                if previa is not None and previa.numero_personal != persona.numero_personal:
                    # Dos personas distintas comparten clave: el árbol les
                    # asignaría los mismos subordinados. Hay que verlo, no tragarlo.
                    logger.warning(
                        f"Nombre ambiguo '{clave}': Nº pers. {previa.numero_personal} "
                        f"y {persona.numero_personal}. Se usara el ultimo."
                    )
                self.personas_por_nombre[clave] = persona
    
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
            Objeto Persona si se encuentra, None en caso contrario
        """
        return self.personas_por_nombre.get(normalizar_nombre(nombre))
    
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
        
        return reporte
