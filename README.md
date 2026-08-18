# Generador de Organigramas en PDF

## 📋 Descripción

Herramienta Python que genera organigramas en PDF a partir de datos de empleados en Excel. Permite seleccionar "cabezas" (personas raíz) y genera árboles jerárquicos verticales mostrando la estructura de supervisión.

**Características clave:**
- ✅ 100% offline — todo se ejecuta localmente sin conexión a internet
- ✅ Lectura de datos desde archivos Excel (.xlsx, .xls, .xlsm)
- ✅ Base de datos persistente de "cabezas" (personas raíz)
- ✅ Interfaz interactiva CLI para seleccionar/agregar cabezas
- ✅ Generación de organigramas en PDF con layout vertical
- ✅ Información visual: nombre abreviado, posición, departamento (CeCo)
- ✅ Detección de ciclos en la estructura jerárquica

## 🛠️ Instalación

### Requisitos
- Python >= 3.11
- pip o uv (gestor de paquetes)

### Paso 1: Instalar dependencias

Usando **uv** (recomendado):
```bash
cd c:\Prueba\Organigramas
uv pip install -e .
```

O usando **pip**:
```bash
cd c:\Prueba\Organigramas
pip install pandas openpyxl reportlab
```

### Paso 2: Verificar instalación

```bash
organigramas
```

Deberías ver el menú interactivo inicial.

## 📊 Formato del archivo Excel

Tu archivo Excel debe tener las siguientes columnas (en cualquier orden):

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| Nº pers. | Número único del empleado | ✅ Sí |
| Nombre(s) | Nombre del empleado | ✅ Sí |
| Apellido Paterno | Apellido paterno | ✅ Sí |
| Apellido Materno | Apellido materno | ⭕ No |
| Denominación de la posición | Puesto/cargo | ⭕ No |
| CeCo | Centro de costos/departamento | ⭕ No |
| Cal.Migratoria | Nombre del supervisor directo | ⭕ No |
| CURP | Número CURP | ⭕ No |
| Planta | Ubicación/planta | ⭕ No |

### Ejemplo de datos:

```
Nº pers. | Nombre del empleado | Nombre(s) | Apellido Paterno | Denominación de la posición | CeCo | Cal.Migratoria
1001     | Juan Pérez          | Juan      | Pérez           | Director General            | 1000 | 
1002     | María García        | María     | García          | Gerente de Operaciones      | 1100 | Juan Pérez
1003     | Carlos López        | Carlos    | López           | Supervisor                  | 1101 | María García
```

## 🚀 Uso

### Iniciar la herramienta

```bash
organigramas
```

### Flujo de la aplicación

1. **Ingresar ruta del Excel** — Proporciona la ruta del archivo (absoluta o relativa)
2. **Validación** — Se cargan y validan los datos
3. **Seleccionar cabeza** — Elige una de estas opciones:
   - Usar una cabeza guardada previamente
   - Seleccionar una cabeza disponible en el Excel actual
   - Agregar una nueva cabeza manualmente
4. **Guardar ubicación PDF** — Especifica dónde guardar el PDF (o presiona Enter para default)
5. **Generación** — Se crea el PDF con el organigrama
6. **Repetir** — Opción de generar otro organigrama con el mismo Excel

### Ejemplo de uso interactivo

```
============================================================
GENERADOR DE ORGANIGRAMAS
============================================================

📁 Ingresa la ruta al archivo Excel: datos/empleados.xlsx

📂 Cargando datos del Excel...
✓ Cargadas 150 personas

🔍 Analizando estructura jerárquica...
✓ Encontradas 5 cabezas posibles

👥 Seleccionando cabeza del organigrama...

============================================================
GENERADOR DE ORGANIGRAMAS
============================================================

📋 Cabezas guardadas:
   1. J. Pérez ✓
   2. M. García ✓

📊 Cabezas disponibles en Excel (5):
   1. J. Pérez
   2. M. García
   3. C. López
   (y 2 más)

Opciones:
  1. Seleccionar una cabeza guardada
  2. Seleccionar una cabeza del Excel
  3. Agregar una nueva cabeza y guardarla
  0. Cancelar

¿Qué deseas hacer? (0-3): 2

📊 Selecciona una cabeza del Excel:
  1. J. Pérez
  2. M. García
  3. C. López
  0. Atrás

Selección (0-3): 1
¿Guardar 'J. Pérez' para usos futuros? (s/n): s
✓ Seleccionada: J. Pérez

🌳 Construyendo árbol para: J. Pérez

📄 Generando PDF...
📄 Ubicación de salida (por defecto: organigrama_J_Perez.pdf)
Ruta completa del PDF (Enter para usar default): 

✅ ¡Éxito! Organigrama generado en: C:\Prueba\Organigramas\organigrama_J_Perez.pdf

¿Generar otro organigrama? (s/n): n
Gracias por usar el Generador de Organigramas.
```

### Interfaz gráfica (GUI)

Si prefieres no usar la terminal, hay una interfaz gráfica de escritorio equivalente:

```bash
organigramas-gui
```

Se abre una ventana con dos acciones — **Generar organigrama** e **Integrar Excels** — que siguen el mismo flujo que la CLI pero con diálogos, selección de archivos y formularios. Incluye búsqueda al elegir una cabeza o mapear columnas, e indicadores de progreso mientras se leen Excels o se generan los PDFs. Es igual de offline que la CLI; no requiere ningún paso de instalación adicional.

## 📁 Estructura del proyecto

```
Organigramas/
├── src/organigramas/
│   ├── __init__.py           # Punto de entrada
│   ├── cli.py               # Interfaz CLI principal
│   ├── gui.py                # Interfaz gráfica de escritorio (tkinter)
│   ├── models.py            # Dataclasses: Persona, Nodo
│   ├── excel_parser.py      # Lectura y parseo de Excel
│   ├── hierarchy.py         # Construcción de árboles jerárquicos
│   ├── heads_manager.py     # Gestión de cabezas (persistencia)
│   └── pdf_renderer.py      # Generación de PDFs
├── data/
│   └── heads.json          # Base de datos de cabezas guardadas
├── pyproject.toml          # Configuración del proyecto
└── README.md               # Este archivo
```

## 🔒 Privacidad y Seguridad

- ✅ **100% Offline** — Todo se ejecuta en tu equipo local
- ✅ **Sin transmisión de datos** — La información nunca sale del computador
- ✅ **Almacenamiento local** — Solo se guardan las cabezas en `data/heads.json`
- ✅ **Sin telemería** — No hay conexión a internet ni servicios externos

## 📖 Documentación técnica

### Módulo: excel_parser.py
Responsable de leer archivos Excel y extraer datos de empleados.

```python
from organigramas.excel_parser import ExcelParser

parser = ExcelParser()
personas = parser.leer_excel("datos.xlsx")
```

### Módulo: hierarchy.py
Construye árboles jerárquicos y valida la estructura.

```python
from organigramas.hierarchy import HierarchyManager

manager = HierarchyManager(personas)
arbol = manager.construir_arbol("J. Pérez")
```

### Módulo: pdf_renderer.py
Genera PDFs con visualización del organigrama.

```python
from organigramas.pdf_renderer import PDFRenderer

renderer = PDFRenderer()
renderer.generar_pdf(arbol_raiz, "salida.pdf")
```

## 🐛 Resolución de problemas

### Error: "Archivo no encontrado"
- Verifica que la ruta al Excel sea correcta
- Usa rutas absolutas si estás en un directorio diferente
- Evita rutas con espacios sin comillas

### Error: "No se encontró encabezado para..."
- Verifica que tu Excel tiene las columnas requeridas
- Los nombres de columnas deben coincidir (case-insensitive) con los esperados
- Consulta la tabla de formato en la sección "📊 Formato del archivo Excel"

### El organigrama no muestra subordinados
- Verifica que la columna "Cal.Migratoria" contiene los nombres de supervisores
- Los nombres deben coincidir exactamente (respetando mayúsculas/minúsculas en la búsqueda, pero con búsqueda case-insensitive)
- Revisa los logs para advertencias sobre supervisores no encontrados

### PDF no se genera o es muy grande
- Comprueba que el archivo Excel es válido (abre en Excel)
- Si el árbol es muy profundo, reportlab puede generar PDFs multipágina

## 📝 Licencia

Este proyecto es de uso local. No requiere conexión a internet.

## 📞 Soporte

Para reportar problemas o sugerencias, revisa los logs en la consola durante la ejecución.
