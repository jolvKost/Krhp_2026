"""Modelos de datos para el generador de organigramas."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Persona:
    """Representa a una persona en la base de datos de empleados."""
    
    numero_personal: str
    nombre_completo: str
    nombre_abreviado: str  # Inicial(es) + Apellido Paterno
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    posicion: Optional[str] = None
    ceco: Optional[str] = None
    supervisor_nombre: Optional[str] = None
    curp: Optional[str] = None
    cal_migratoria: Optional[str] = None
    planta: Optional[str] = None


@dataclass
class Nodo:
    """Nodo en el árbol jerárquico de un organigrama."""
    
    persona: Persona
    hijos: List['Nodo'] = field(default_factory=list)
    
    def agregar_hijo(self, nodo_hijo: 'Nodo') -> None:
        """Agrega un nodo hijo a este nodo."""
        self.hijos.append(nodo_hijo)
    
    def obtener_todos_descendientes(self) -> List[Persona]:
        """Retorna todas las personas descendientes (incluyendo a sí mismo)."""
        descendientes = [self.persona]
        for hijo in self.hijos:
            descendientes.extend(hijo.obtener_todos_descendientes())
        return descendientes
    
    def profundidad(self) -> int:
        """Retorna la profundidad del subárbol (0 si no tiene hijos)."""
        if not self.hijos:
            return 0
        return 1 + max(hijo.profundidad() for hijo in self.hijos)
    
    def cantidad_subordinados(self) -> int:
        """Retorna la cantidad total de subordinados (excluyendo a sí mismo)."""
        total = len(self.hijos)
        for hijo in self.hijos:
            total += hijo.cantidad_subordinados()
        return total
