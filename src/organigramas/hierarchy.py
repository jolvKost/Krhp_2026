"""Gestión de jerarquía y construcción de árboles organizacionales.

La identidad de una persona es su Nº pers., nunca su nombre. El unico punto
donde un nombre se convierte en identidad es `_resolver_supervisores`, porque
el extracto SAP entrega al jefe directo como texto ("APELLIDO, NOMBRE"). De ahi
en adelante el arbol se arma exclusivamente con Nº pers.
"""

import logging
import unicodedata
from typing import List, Dict, Optional, Set
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
        self.por_numero: Dict[str, Persona] = {}          # Nº pers. -> Persona (LA identidad)
        self._indice_nombres: Dict[str, Set[str]] = {}    # nombre normalizado -> {Nº pers.}
        self.hijos_por_jefe: Dict[str, List[Persona]] = {}  # Nº pers. jefe -> subordinados
        self.nombres_ambiguos: Set[str] = set()
        self.jefes_no_resueltos: Set[str] = set()

        self._indexar_personas()
        self._resolver_supervisores()
        self._indexar_hijos()

    # ------------------------------------------------------------------
    # Indexado
    # ------------------------------------------------------------------

    def _indexar_personas(self) -> None:
        """
        Indexa por Nº pers. y arma un indice auxiliar nombre -> {Nº pers.}.

        El indice de nombres guarda un CONJUNTO de numeros, no una persona: asi
        un homonimo se detecta en vez de sobreescribir al anterior. Solo entran
        dos llaves, cada una con un uso concreto:

        - "Ap.Paterno + Nombre(s)": el unico formato que empata contra
          Cal.Migratoria, que es como SAP nombra al jefe directo.
        - "nombre_abreviado": para que el usuario pueda buscar una cabeza
          escribiendo el nombre en el menu.

        NO se indexa "Nombre(s)" a secas: son nombres de pila, cientos de
        personas comparten "MARIA GUADALUPE" y usarlos como llave era la causa
        de que un subarbol completo colgara de la persona equivocada.
        """
        for persona in self.personas:
            previa = self.por_numero.get(persona.numero_personal)
            if previa is not None:
                logger.warning(
                    f"Nº pers. duplicado {persona.numero_personal}: se conserva la ultima fila."
                )
            self.por_numero[persona.numero_personal] = persona

            claves = {
                normalizar_nombre(f"{persona.apellido_paterno} {persona.nombres}"),
                normalizar_nombre(persona.nombre_abreviado),
            }
            for clave in claves:
                if clave:
                    self._indice_nombres.setdefault(clave, set()).add(persona.numero_personal)

    def _resolver_supervisores(self) -> None:
        """
        Traduce el nombre del jefe a Nº pers., UNA sola vez por persona.

        Este es el unico salto nombre -> identidad del proyecto. Si algun dia el
        extracto SAP trae un "Nº pers. del encargado", se cambia aqui y nada mas.
        """
        for persona in self.personas:
            if not persona.supervisor_nombre:
                continue

            clave = normalizar_nombre(persona.supervisor_nombre)
            candidatos = self._indice_nombres.get(clave, set())

            if len(candidatos) == 1:
                numero = next(iter(candidatos))
                # Auto-referencia: nadie es su propio jefe.
                persona.supervisor_numero = (
                    numero if numero != persona.numero_personal else None
                )
            elif len(candidatos) > 1:
                # Ambiguo: preferimos dejar a la persona sin jefe (visible en el
                # reporte) antes que colgarla de uno de los dos al azar.
                self.nombres_ambiguos.add(clave)
            else:
                self.jefes_no_resueltos.add(clave)

    def _indexar_hijos(self) -> None:
        """Agrupa subordinados por Nº pers. del jefe en una sola pasada."""
        for persona in self.personas:
            if persona.supervisor_numero:
                self.hijos_por_jefe.setdefault(persona.supervisor_numero, []).append(persona)

    # ------------------------------------------------------------------
    # Arbol
    # ------------------------------------------------------------------

    def construir_arbol(self, numero_personal: str) -> Nodo:
        """
        Construye un árbol jerárquico con la persona especificada como raíz.

        Args:
            numero_personal: Nº pers. de la persona raíz

        Returns:
            Nodo raíz del árbol construido

        Raises:
            ValueError: Si el Nº pers. no existe en el Excel cargado
        """
        cabeza = self.por_numero.get(str(numero_personal).strip())
        if not cabeza:
            raise ValueError(
                f"No se encontró persona con Nº pers. '{numero_personal}' en el Excel cargado."
            )

        logger.info(f"Construyendo árbol para Nº pers. {cabeza.numero_personal}")

        nodo_raiz = Nodo(persona=cabeza)
        self._construir_arbol_recursivo(nodo_raiz, {cabeza.numero_personal})

        logger.info(
            f"Árbol construido: {len(nodo_raiz.obtener_todos_descendientes())} personas, "
            f"profundidad {nodo_raiz.profundidad() + 1}"
        )

        return nodo_raiz

    def _construir_arbol_recursivo(self, nodo_padre: Nodo, ancestros: Set[str]) -> None:
        """
        Construye recursivamente el subárbol de un nodo.

        `ancestros` es el camino raiz->nodo actual, mutado y restaurado en vez de
        copiarse por nivel. Como cada persona tiene un solo jefe, lo unico que
        puede descartar es un ciclo real (A -> B -> A).
        """
        for subordinado in self.hijos_por_jefe.get(nodo_padre.persona.numero_personal, []):
            if subordinado.numero_personal in ancestros:
                logger.warning(
                    f"Ciclo detectado: Nº pers. {nodo_padre.persona.numero_personal} -> "
                    f"{subordinado.numero_personal}"
                )
                continue

            nodo_hijo = Nodo(persona=subordinado)
            nodo_padre.agregar_hijo(nodo_hijo)

            ancestros.add(subordinado.numero_personal)
            self._construir_arbol_recursivo(nodo_hijo, ancestros)
            ancestros.discard(subordinado.numero_personal)

    # ------------------------------------------------------------------
    # Consultas y reportes
    # ------------------------------------------------------------------

    def buscar_por_numero(self, numero_personal: str) -> Optional[Persona]:
        """Busca una persona por Nº pers."""
        return self.por_numero.get(str(numero_personal).strip())

    def buscar_por_texto(self, texto: str) -> List[Persona]:
        """
        Busca personas por Nº pers. exacto o por coincidencia parcial de nombre.

        Devuelve TODAS las coincidencias para que el usuario elija: nunca
        adivina cual de dos homonimos queria.
        """
        texto = texto.strip()
        if not texto:
            return []

        exacta = self.por_numero.get(texto)
        if exacta:
            return [exacta]

        aguja = normalizar_nombre(texto)
        return [
            p
            for p in self.personas
            if aguja in normalizar_nombre(f"{p.nombre_abreviado} {p.apellido_paterno} {p.nombres}")
        ]

    def contar_subordinados_directos(self) -> Dict[str, int]:
        """Cuenta reportes directos por Nº pers. del jefe."""
        return {numero: len(hijos) for numero, hijos in self.hijos_por_jefe.items()}

    def obtener_todas_las_cabezas_posibles(self) -> List[Persona]:
        """
        Retorna las personas sin jefe resuelto, ordenadas por cantidad de
        subordinados directos (de mayor a menor).

        El orden importa: contra el extracto real quedan mas de mil personas sin
        jefe (las que no traen el dato, mas aquellas cuyo jefe no resuelve), y el
        menu solo muestra las 10 primeras. Sin ordenar, esas 10 salian en orden
        de archivo y las cabezas reales quedaban sepultadas. No se filtra a
        nadie: una cabeza legitima cuyos reportes tengan el dato en blanco
        aparece con 0 subordinados, pero sigue estando en la lista.
        """
        cabezas = [p for p in self.personas if not p.supervisor_numero]
        directos = self.contar_subordinados_directos()
        cabezas.sort(key=lambda p: directos.get(p.numero_personal, 0), reverse=True)
        return cabezas

    def validar_estructura(self) -> Dict[str, any]:
        """
        Valida la estructura de datos y retorna un reporte.

        `cabezas_posibles` son objetos Persona, no nombres: quien las consuma
        debe quedarse con el Nº pers.
        """
        # Cada persona cae en exactamente un cubo: los conteos suman al total y
        # no se pisan entre si (antes un jefe ambiguo se contaba dos veces).
        sin_dato = resueltos = ambiguas = desconocidas = 0
        for persona in self.personas:
            if not persona.supervisor_nombre:
                sin_dato += 1
            elif persona.supervisor_numero:
                resueltos += 1
            elif normalizar_nombre(persona.supervisor_nombre) in self.nombres_ambiguos:
                ambiguas += 1
            else:
                desconocidas += 1

        reporte = {
            "total_personas": len(self.personas),
            "cabezas_posibles": self.obtener_todas_las_cabezas_posibles(),
            "jefes_resueltos": resueltos,
            "advertencias": [],
            "errores": [],
        }

        if sin_dato:
            reporte["advertencias"].append(
                f"{sin_dato} personas sin dato de jefe directo (Cal.Migratoria vacia)"
            )

        if desconocidas:
            # Sin recortar, esto vuelca cientos de nombres de empleados a consola.
            muestra = sorted(self.jefes_no_resueltos)[:5]
            resto = len(self.jefes_no_resueltos) - len(muestra)
            reporte["advertencias"].append(
                f"{desconocidas} personas cuyo jefe no existe en el Excel"
                f" ({len(self.jefes_no_resueltos)} nombres distintos"
                f"; ej.: {', '.join(muestra)}{f' y {resto} mas' if resto else ''})"
            )

        if ambiguas:
            reporte["advertencias"].append(
                f"{ambiguas} personas cuyo jefe coincide con mas de una persona"
                f" ({len(self.nombres_ambiguos)} nombres): se dejaron SIN resolver"
                " para no asignar subordinados al azar"
            )

        reporte["advertencias"].append(
            f"Jefe resuelto por Nº pers.: {resueltos}/{len(self.personas)} personas"
        )

        return reporte
