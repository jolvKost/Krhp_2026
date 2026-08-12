# GUÍA DE INSTALACIÓN Y USO

## ⚠️ Requisitos previos

Necesitas tener **Python 3.11 o superior** instalado correctamente en tu sistema. 

### Verificar si Python está instalado

Abre PowerShell o CMD y ejecuta:
```powershell
python --version
```

Si no funciona, necesitas instalar Python desde: https://www.python.org/downloads/

**Asegúrate de marcar la opción "Add Python to PATH" durante la instalación.**

## 🛠️ Instalación paso a paso

### Opción 1: Usando pip (Recomendado)

1. Abre PowerShell o CMD
2. Navega al directorio del proyecto:
```powershell
cd c:\Prueba\Organigramas
```

3. Instala las dependencias:
```powershell
pip install pandas openpyxl reportlab
```

O si tienes pip en tu PATH pero python no:
```powershell
pip.exe install pandas openpyxl reportlab
```

4. Verifica la instalación:
```powershell
pip show pandas openpyxl reportlab
```

Deberías ver la versión de cada paquete.

### Opción 2: Usando uv (Más moderno)

Si tienes `uv` instalado:

```powershell
cd c:\Prueba\Organigramas
uv pip install -e .
```

### Opción 3: Instalación manual de dependencias

Si los comandos anteriores no funcionan, descarga los archivos .whl desde PyPI e instálalos manualmente:

1. Descarga desde: https://pypi.org/
   - pandas
   - openpyxl  
   - reportlab

2. Instala cada uno:
```powershell
pip install "ruta/a/archivo.whl"
```

## 🚀 Ejecución del programa

Una vez instaladas las dependencias:

### Desde Python directamente

```powershell
cd c:\Prueba\Organigramas
python src/organigramas/cli.py
```

O si prefieres importar el módulo:

```powershell
cd c:\Prueba\Organigramas
python -c "from src.organigramas.cli import main; main()"
```

### Usando el comando instalado (si instalaste con pip install -e .)

```powershell
organigramas
```

## 📊 Crear un archivo Excel de prueba

Para probar el programa, crea un archivo Excel con este contenido:

**Archivo: test_empleados.xlsx**

| Nº pers. | Nombre(s) | Apellido Paterno | Denominación de la posición | CeCo | Cal.Migratoria |
|----------|-----------|------------------|-------|------|----------------|
| 1001     | Juan      | Pérez            | Director General | 1000 |                |
| 1002     | María     | García           | Gerente de RRHH  | 1100 | Juan Pérez     |
| 1003     | Carlos    | López            | Supervisor       | 1101 | María García   |
| 1004     | Ana       | Rodríguez        | Asistente        | 1102 | Carlos López   |

Guarda este archivo en: `c:\Prueba\Organigramas\test_empleados.xlsx`

## ✅ Verificación de la instalación

Ejecuta el script de prueba para verificar que todos los módulos están correctos:

```powershell
cd c:\Prueba\Organigramas
python test_imports.py
```

Deberías ver:

```
🧪 Prueba de importaciones...
  1. Importando models... ✓
  2. Importando excel_parser... ✓
  3. Importando hierarchy... ✓
  4. Importando heads_manager... ✓
  5. Importando pdf_renderer... ✓
  6. Importando cli... ✓

✅ Todas las importaciones exitosas!
```

## 🐛 Solución de problemas

### "No se encuentra el módulo 'pandas'"
- Instala con: `pip install pandas`
- Verifica: `pip show pandas`

### "No se encuentra el módulo 'openpyxl'"
- Instala con: `pip install openpyxl`

### "No se encuentra el módulo 'reportlab'"
- Instala con: `pip install reportlab`

### "python no se reconoce"
- Reinstala Python desde https://www.python.org/downloads/
- Asegúrate de marcar "Add Python to PATH"
- Reinicia PowerShell/CMD después de la instalación

### "El script no encuentra mi archivo Excel"
- Usa rutas absolutas: `C:\Prueba\Organigramas\datos.xlsx`
- O rutas relativas desde el directorio actual
- Verifica que el archivo existe: `Test-Path "C:\ruta\archivo.xlsx"`

## 📝 Estructura completa del proyecto

```
c:\Prueba\Organigramas\
├── src/
│   └── organigramas/
│       ├── __init__.py           # ✅ Punto de entrada
│       ├── cli.py               # ✅ Interfaz CLI principal
│       ├── models.py            # ✅ Modelos de datos (Persona, Nodo)
│       ├── excel_parser.py      # ✅ Lectura de Excel
│       ├── hierarchy.py         # ✅ Construcción de árboles
│       ├── heads_manager.py     # ✅ Gestión de cabezas (persistencia)
│       └── pdf_renderer.py      # ✅ Generación de PDF
├── data/
│   └── heads.json              # ✅ Base de datos de cabezas (creada automáticamente)
├── pyproject.toml              # ✅ Configuración del proyecto
├── README.md                   # ✅ Documentación completa
├── test_imports.py             # ✅ Script de verificación
└── INSTALACION.md              # ✅ Este archivo
```

## ✨ Características implementadas

✅ Lectura de archivos Excel con validación de encabezados
✅ Extracción de datos de empleados
✅ Generación automática de nombres abreviados (Inicial + Apellido)
✅ Construcción de árboles jerárquicos
✅ Detección de ciclos en la estructura
✅ Gestor de cabezas con persistencia en JSON
✅ Interfaz interactiva CLI para seleccionar/agregar cabezas
✅ Generación de organigramas en PDF con layout vertical
✅ Información visual: nombre, posición, departamento (CeCo)
✅ 100% offline - sin conexión a internet
✅ Almacenamiento local - datos nunca salen del equipo
✅ Validación de estructura jerárquica
✅ Manejo de errores y advertencias
✅ Documentación completa

## 🔒 Seguridad y Privacidad

✅ Toda la ejecución es **100% local**
✅ Sin conexión a internet
✅ Sin transmisión de datos
✅ Sin telemería ni analytics
✅ Solo almacenamiento en `data/heads.json`

## 📞 Siguiente paso

Una vez que tengas Python instalado correctamente:

1. Instala las dependencias: `pip install pandas openpyxl reportlab`
2. Crea un archivo Excel de prueba
3. Ejecuta: `python src/organigramas/cli.py`
4. Sigue el menú interactivo

¡Listo! Deberías tener tu primer organigrama en PDF.
