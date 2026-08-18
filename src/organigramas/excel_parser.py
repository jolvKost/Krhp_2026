"""Parser de archivos Excel para extraer datos de empleados."""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List
import logging

from .models import Persona

logger = logging.getLogger(__name__)

# Catálogo CeCo -> Área, equivalente a la hoja "CC" del Excel HC_Controlling.
# Formato: {"1234": "Producción", ...}
CATALOGO_AREAS = Path("data/areas.json")


def _clave_ceco(valor) -> str:
    """Normaliza un CeCo a string sin decimales: pandas puede leerlo como 1234.0."""
    texto = str(valor).strip()
    return texto[:-2] if texto.endswith(".0") else texto


def cargar_catalogo_areas(ruta: str | Path = CATALOGO_AREAS) -> Dict[str, str]:
    """
    Carga el catálogo CeCo -> Área desde JSON.

    Si el archivo no existe devuelve {}: el área queda en None y el resto del
    pipeline sigue funcionando igual.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        logger.info(f"Catálogo de áreas no encontrado: {ruta}")
        return {}

    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return {_clave_ceco(k): str(v).strip() for k, v in datos.items()}
    except Exception as e:
        logger.error(f"Error al leer catálogo de áreas: {e}")
        return {}

# Encabezados esperados en el Excel (case-insensitive matching)
ENCABEZADOS_ESPERADOS = {
    "numero_personal": ["Nº pers.", "nº pers", "numero personal", "n° pers"],
    "nombre_empleado": ["Nombre del empleado o candidat", "nombre del empleado", "nombre empleado"],
    "nombres": ["Nombre(s)", "nombre"],
    "apellido_paterno": ["Apellido Paterno", "apellido paterno"],
    "apellido_materno": ["Apellido Materno", "apellido materno"],
    "posicion": ["Denominación de la posición", "denominacion posicion", "posicion"],
    "ceco": ["CeCo", "ceco", "centro de costos"],
    "supervisor": ["Nombre del encargado", "encargado", "jefe", "supervisor"],
    "cal_migratoria": ["Cal.Migratoria", "cal. migratoria", "calmigratoria"],
    "curp": ["CURP", "curp"],
    "planta": ["Planta", "planta"],
    "nimss": ["NIMSS", "nimss"],
    "alta": ["Alta", "alta", "fecha alta"],
}


class ExcelParser:
    """Parser para archivos Excel con datos de empleados."""
    
    def __init__(self, catalogo_areas: Dict[str, str] | None = None):
        self.encabezados_mapa = {}  # Mapeo de Excel a nuestros campos
        self.catalogo_areas = (
            catalogo_areas if catalogo_areas is not None else cargar_catalogo_areas()
        )
    
    def leer_excel(self, ruta_archivo: str) -> List[Persona]:
        """
        Lee un archivo Excel y retorna lista de Persona.
        
        Args:
            ruta_archivo: Ruta al archivo Excel
            
        Returns:
            Lista de objetos Persona
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el Excel no tiene los encabezados esperados
        """
        ruta = Path(ruta_archivo)
        
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")
        
        try:
            df = pd.read_excel(ruta, sheet_name=0)
        except Exception as e:
            raise ValueError(f"Error al leer Excel: {e}")
        
        logger.info(f"Excel cargado: {df.shape[0]} filas, {df.shape[1]} columnas")
        
        # Mapear encabezados
        self._mapear_encabezados(df.columns)
        
        # Extraer personas
        personas = []
        for idx, row in df.iterrows():
            try:
                persona = self._crear_persona_desde_fila(row)
                if persona:
                    personas.append(persona)
            except Exception as e:
                logger.warning(f"Error en fila {idx + 2}: {e}")
                continue

        logger.info(f"Se extrajeron {len(personas)} personas del Excel")
        self._advertir_numeros_duplicados(personas)
        return personas

    @staticmethod
    def _advertir_numeros_duplicados(personas: List[Persona]) -> List[str]:
        """
        Reporta Nº pers. repetidos: el Nº pers. es la llave de todo el pipeline,
        y un duplicado hace que una persona sobreescriba a otra en el indice.

        Solo se emiten numeros, nunca nombres, para no volcar PII a consola.
        """
        vistos, duplicados = set(), []
        for persona in personas:
            if persona.numero_personal in vistos:
                duplicados.append(persona.numero_personal)
            vistos.add(persona.numero_personal)

        if duplicados:
            muestra = ", ".join(sorted(set(duplicados))[:5])
            logger.warning(
                f"{len(duplicados)} filas con Nº pers. duplicado (ej.: {muestra}). "
                "Se conservara la ultima de cada uno."
            )
        return duplicados
    
    def _mapear_encabezados(self, encabezados_excel: List[str]) -> None:
        """Mapea los encabezados del Excel a nuestros campos esperados."""
        self.encabezados_mapa = {}
        
        for encabezado in encabezados_excel:
            encabezado_lower = encabezado.strip().lower()
            
            for campo, variantes in ENCABEZADOS_ESPERADOS.items():
                if encabezado_lower in [v.lower() for v in variantes]:
                    self.encabezados_mapa[campo] = encabezado
                    logger.debug(f"Mapeado '{encabezado}' -> {campo}")
                    break
        
        # Validar que tenemos los campos críticos
        campos_requeridos = ["numero_personal", "nombres", "apellido_paterno"]
        for campo in campos_requeridos:
            if campo not in self.encabezados_mapa:
                raise ValueError(
                    f"No se encontró encabezado para '{campo}'. "
                    f"Encabezados disponibles: {list(encabezados_excel)}"
                )
    
    def _crear_persona_desde_fila(self, row) -> Persona | None:
        """Crea un objeto Persona a partir de una fila del DataFrame."""
        
        # Campos obligatorios
        numero_personal = str(row.get(self.encabezados_mapa["numero_personal"], "")).strip()
        nombres = str(row.get(self.encabezados_mapa["nombres"], "")).strip()
        apellido_paterno = str(row.get(self.encabezados_mapa["apellido_paterno"], "")).strip()

        # Validar campos obligatorios
        if not numero_personal or pd.isna(numero_personal) or numero_personal == "nan":
            return None
        if not nombres or pd.isna(nombres) or nombres == "nan":
            return None
        if not apellido_paterno or pd.isna(apellido_paterno) or apellido_paterno == "nan":
            return None
        
        # Campos opcionales
        apellido_materno = self._obtener_valor_opcional(
            row, self.encabezados_mapa.get("apellido_materno")
        )
        nombre_abreviado = self._generar_nombre_abreviado(
            nombres, apellido_paterno, apellido_materno
        )
        posicion = self._obtener_valor_opcional(
            row, self.encabezados_mapa.get("posicion")
        )
        ceco = self._obtener_valor_opcional(
            row, self.encabezados_mapa.get("ceco")
        )
        curp = self._obtener_valor_opcional(
            row, self.encabezados_mapa.get("curp")
        )
        cal_migratoria = self._obtener_valor_opcional(
            row, self.encabezados_mapa.get("cal_migratoria")
        )
        planta = self._obtener_valor_opcional(
            row, self.encabezados_mapa.get("planta")
        )
        
        # El jefe DIRECTO viene en Cal.Migratoria, en formato "Apellido, Nombre(s)"
        # (la columna está reutilizada en este extracto de SAP).
        #
        # "Nombre del encargado" NO sirve para el árbol: es una etiqueta de área
        # ("Ing Calidad K1" y similares, 56 valores para 2874 personas), no un
        # puntero a un empleado. Usarla como respaldo inventaría jefes falsos.
        supervisor_nombre = cal_migratoria
        
        return Persona(
            numero_personal=numero_personal,
            nombres=nombres,
            nombre_abreviado=nombre_abreviado,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            posicion=posicion,
            ceco=ceco,
            area=self.catalogo_areas.get(_clave_ceco(ceco)) if ceco else None,
            supervisor_nombre=supervisor_nombre,
            curp=curp,
            cal_migratoria=cal_migratoria,
            planta=planta,
        )
    
    @staticmethod
    def _generar_nombre_abreviado(
        nombres: str,
        apellido_paterno: str,
        apellido_materno: str | None = None,
    ) -> str:
        """
        Genera nombre abreviado: inicial del nombre + apellidos.
        Ej: "Juan Pedro" + "Pérez" + "López" -> "J. Pérez López"

        Replica la columna AA del Excel HC_Controlling:
        =LEFT(Nombre(s),1) & "." & " " & Apellido Paterno & " " & Apellido Materno

        Es texto para DESPLEGAR, no una llave: dos personas distintas pueden
        generar el mismo abreviado.
        """
        inicial = nombres.strip()[:1].upper()
        partes = [f"{inicial}." if inicial else "", apellido_paterno, apellido_materno]
        return " ".join(p for p in partes if p)
    
    @staticmethod
    def _obtener_valor_opcional(row, encabezado: str | None) -> str | None:
        """Obtiene un valor opcional del row del DataFrame."""
        if not encabezado:
            return None
        
        valor = row.get(encabezado, None)
        
        if valor is None or pd.isna(valor):
            return None
        
        valor_str = str(valor).strip()
        return valor_str if valor_str and valor_str != "nan" else None
