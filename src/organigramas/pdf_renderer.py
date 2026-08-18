"""Generador de PDFs con organigramas usando reportlab."""

import logging
from pathlib import Path
from typing import Tuple, List
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

from .models import Nodo, Persona

logger = logging.getLogger(__name__)


class Organigrama:
    """Representa un organigrama con posiciones calculadas para renderizado."""
    
    # Parámetros de diseño
    ANCHO_NODO = 2.2  # inches
    ALTO_NODO = 1.0
    ESPACIADO_VERTICAL = 2.0
    ESPACIADO_HORIZONTAL = 0.3
    
    def __init__(self, nodo_raiz: Nodo):
        """
        Inicializa el organigrama.
        
        Args:
            nodo_raiz: Nodo raíz del árbol
        """
        self.nodo_raiz = nodo_raiz
        self.nodos_posiciones = {}  # {id_nodo: (x, y)}
        self._calcular_posiciones()
    
    def _calcular_posiciones(self) -> None:
        """Calcula las posiciones de los nodos en el organigrama."""
        ancho_total = self._calcular_ancho_subtree(self.nodo_raiz)
        # Posicionar raíz en el centro arriba
        posicion_raiz = (ancho_total / 2, 0)
        self.nodos_posiciones[id(self.nodo_raiz)] = posicion_raiz
        
        # Calcular posiciones de hijos recursivamente
        self._calcular_posiciones_recursivo(
            self.nodo_raiz,
            posicion_raiz,
            ancho_total
        )
    
    def _calcular_ancho_subtree(self, nodo: Nodo) -> float:
        """Calcula el ancho necesario para renderizar un subárbol."""
        if not nodo.hijos:
            return self.ANCHO_NODO + self.ESPACIADO_HORIZONTAL
        
        ancho_hijos = sum(
            self._calcular_ancho_subtree(hijo)
            for hijo in nodo.hijos
        )
        return max(ancho_hijos, self.ANCHO_NODO + self.ESPACIADO_HORIZONTAL)
    
    def _calcular_posiciones_recursivo(
        self,
        nodo: Nodo,
        posicion_padre: Tuple[float, float],
        ancho_subtree: float
    ) -> None:
        """Calcula posiciones recursivamente para un nodo y sus hijos."""
        if not nodo.hijos:
            return
        
        x_padre, y_padre = posicion_padre
        y_hijos = y_padre + self.ESPACIADO_VERTICAL
        
        # Calcular ancho total de hijos
        anchos_hijos = [
            self._calcular_ancho_subtree(hijo)
            for hijo in nodo.hijos
        ]
        ancho_total_hijos = sum(anchos_hijos)
        
        # Posicionar hijos distribuidos horizontalmente
        x_inicial = x_padre - ancho_total_hijos / 2
        x_actual = x_inicial
        
        for hijo, ancho_hijo in zip(nodo.hijos, anchos_hijos):
            x_hijo = x_actual + ancho_hijo / 2
            posicion_hijo = (x_hijo, y_hijos)
            self.nodos_posiciones[id(hijo)] = posicion_hijo
            
            # Recursar
            self._calcular_posiciones_recursivo(hijo, posicion_hijo, ancho_hijo)
            x_actual += ancho_hijo
    
    def obtener_limites(self) -> Tuple[float, float, float, float]:
        """Retorna (min_x, min_y, max_x, max_y) del organigrama."""
        if not self.nodos_posiciones:
            return (0, 0, self.ANCHO_NODO, self.ALTO_NODO)
        
        posiciones = list(self.nodos_posiciones.values())
        xs = [p[0] for p in posiciones]
        ys = [p[1] for p in posiciones]
        
        min_x = min(xs) - self.ANCHO_NODO / 2
        max_x = max(xs) + self.ANCHO_NODO / 2
        min_y = min(ys)
        max_y = max(ys) + self.ALTO_NODO
        
        return (min_x, min_y, max_x, max_y)


class PDFRenderer:
    """Renderiza organigramas a PDF usando reportlab."""
    
    def __init__(self):
        self.fuente_nombre = "Helvetica"
        self.fuente_titulo = "Helvetica-Bold"

    def _textos_por_idioma(self, idioma: str = "es") -> dict:
        """Devuelve los textos del PDF según idioma."""
        if idioma.lower() == "en":
            return {
                "titulo": "Organization Chart",
                "posicion": "Position",
                "ceco": "Cost Center",
                "departamento": "Department",
                "responsable": "Responsible",
                "generado": "Generated automatically",
                "personas": "people",
            }
        return {
            "titulo": "Organigrama",
            "posicion": "Posición",
            "ceco": "CeCo",
            "departamento": "Departamento",
            "responsable": "Responsable",
            "generado": "Generado automáticamente",
            "personas": "personas",
        }
    
    def generar_pdf(self, nodo_raiz: Nodo, ruta_salida: str, idioma: str = "es", metadata: dict | None = None) -> None:
        """
        Genera un PDF con el organigrama.
        
        Args:
            nodo_raiz: Nodo raíz del árbol
            ruta_salida: Ruta donde guardar el PDF
            idioma: Idioma del documento ('es' o 'en')
            metadata: Metadatos a mostrar en el documento
        """
        ruta = Path(ruta_salida)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Generando PDF: {ruta} ({idioma})")
        
        # Crear organigrama con posiciones calculadas
        org = Organigrama(nodo_raiz)
        
        # Usar tamaño landscape A4 para mejor ajuste horizontal
        from reportlab.lib.pagesizes import landscape, A4
        page_width, page_height = landscape(A4)
        
        # Crear canvas
        c = canvas.Canvas(str(ruta), pagesize=(page_width, page_height))
        textos = self._textos_por_idioma(idioma)
        
        # Agregar título
        cabeza = nodo_raiz.persona
        titulo = f"{textos['titulo']}: {cabeza.nombre_abreviado}"
        c.setFont(self.fuente_titulo, 16)
        c.drawString(0.5 * inch, page_height - 0.5 * inch, titulo)
        
        # Información adicional
        info_y = page_height - 0.8 * inch
        c.setFont(self.fuente_nombre, 9)
        c.drawString(0.5 * inch, info_y, f"{textos['posicion']}: {cabeza.posicion or 'N/A'}")
        c.drawString(0.5 * inch, info_y - 0.2 * inch, f"{textos['ceco']}: {cabeza.ceco or 'N/A'}")
        if metadata:
            departamento = metadata.get('departamento') or 'N/A'
            responsable = metadata.get('responsable') or 'N/A'
            c.drawString(0.5 * inch, info_y - 0.4 * inch, f"{textos['departamento']}: {departamento}")
            c.drawString(0.5 * inch, info_y - 0.6 * inch, f"{textos['responsable']}: {responsable}")
        
        # Área de dibujo
        margin_left = 0.5 * inch
        margin_top = 1.6 * inch
        drawing_width = page_width - 2 * margin_left
        drawing_height = page_height - margin_top - 0.5 * inch
        
        # Dibujar organigrama
        self._dibujar_arbol(
            c, nodo_raiz, org,
            margin_left, page_height - margin_top,
            drawing_width, drawing_height
        )
        
        # Pie de página
        c.setFont(self.fuente_nombre, 8)
        c.drawString(
            0.5 * inch,
            0.3 * inch,
            f"{textos['generado']} - {len(nodo_raiz.obtener_todos_descendientes())} {textos['personas']}"
        )
        
        c.save()
        logger.info(f"PDF generado exitosamente: {ruta}")
    
    def _dibujar_arbol(
        self,
        c: canvas.Canvas,
        nodo_raiz: Nodo,
        organigrama: Organigrama,
        x_offset: float,
        y_offset: float,
        drawing_width: float,
        drawing_height: float
    ) -> None:
        """
        Dibuja recursivamente el árbol en el canvas.
        
        Args:
            c: Canvas de reportlab
            nodo_raiz: Nodo raíz
            organigrama: Objeto Organigrama con posiciones
            x_offset, y_offset: Posición de inicio en el canvas
            drawing_width, drawing_height: Dimensiones del área de dibujo
        """
        # Obtener límites del organigrama
        min_x, min_y, max_x, max_y = organigrama.obtener_limites()
        org_width = max_x - min_x
        org_height = max_y - min_y
        
        # Calcular escala para ajustar al área de dibujo
        scale_x = drawing_width / org_width if org_width > 0 else 1
        scale_y = drawing_height / org_height if org_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.9  # 0.9 para deixar margem
        
        # Transformar coordenadas
        def coord_transform(x: float, y: float) -> Tuple[float, float]:
            screen_x = x_offset + (x - min_x) * scale
            screen_y = y_offset - (y - min_y) * scale
            return (screen_x, screen_y)
        
        # Dibujar todas las líneas de conexión primero
        self._dibujar_conexiones(c, nodo_raiz, organigrama, coord_transform)
        
        # Dibujar todos los nodos
        self._dibujar_nodos(c, nodo_raiz, organigrama, coord_transform)
    
    def _dibujar_conexiones(
        self,
        c: canvas.Canvas,
        nodo: Nodo,
        organigrama: Organigrama,
        coord_transform
    ) -> None:
        """Dibuja las líneas de conexión entre nodos."""
        posicion_padre = organigrama.nodos_posiciones.get(id(nodo))
        if not posicion_padre:
            return
        
        x_padre, y_padre = posicion_padre
        
        for hijo in nodo.hijos:
            posicion_hijo = organigrama.nodos_posiciones.get(id(hijo))
            if posicion_hijo:
                x_hijo, y_hijo = posicion_hijo
                
                # Convertir a coordenadas del canvas
                x1, y1 = coord_transform(x_padre, y_padre + Organigrama.ALTO_NODO / 2)
                x2, y2 = coord_transform(x_hijo, y_hijo - Organigrama.ALTO_NODO / 2)
                
                # Dibujar línea
                c.setLineWidth(1)
                c.setStrokeColorRGB(0.3, 0.3, 0.3)
                c.line(x1, y1, x2, y2)
            
            # Recursar
            self._dibujar_conexiones(c, hijo, organigrama, coord_transform)
    
    def _dibujar_nodos(
        self,
        c: canvas.Canvas,
        nodo: Nodo,
        organigrama: Organigrama,
        coord_transform
    ) -> None:
        """Dibuja recursivamente los nodos."""
        posicion = organigrama.nodos_posiciones.get(id(nodo))
        if not posicion:
            return
        
        x, y = posicion
        canvas_x, canvas_y = coord_transform(x, y)
        
        # Dibujar rectángulo del nodo
        self._dibujar_nodo_box(c, nodo.persona, canvas_x, canvas_y)
        
        # Recursar para hijos
        for hijo in nodo.hijos:
            self._dibujar_nodos(c, hijo, organigrama, coord_transform)
    
    def _dibujar_nodo_box(
        self,
        c: canvas.Canvas,
        persona: Persona,
        x: float,
        y: float
    ) -> None:
        """Dibuja un cuadro de persona en el canvas."""
        ancho = Organigrama.ANCHO_NODO * inch
        alto = Organigrama.ALTO_NODO * inch
        
        # Dibujar rectángulo
        c.setLineWidth(1.5)
        c.setStrokeColorRGB(0.2, 0.2, 0.8)
        c.setFillColorRGB(0.95, 0.96, 1.0)
        c.rect(x - ancho/2, y - alto/2, ancho, alto, fill=True, stroke=True)
        
        # Área (columna O del Excel): sólo si el catálogo CeCo -> Área la resolvió
        c.setFont(self.fuente_nombre, 6)
        if persona.area:
            c.drawCentredString(x, y + 0.4 * inch, persona.area[:30])

        # Dibujar texto
        c.setFont(self.fuente_titulo, 9)
        c.drawCentredString(x, y + 0.25 * inch, persona.nombre_abreviado)

        # Posición y CeCo
        c.setFont(self.fuente_nombre, 7)
        posicion_text = persona.posicion[:25] if persona.posicion else "N/A"
        c.drawCentredString(x, y, posicion_text)

        ceco_text = f"[{persona.ceco}]" if persona.ceco else "[---]"
        c.drawCentredString(x, y - 0.2 * inch, ceco_text)
