from pathlib import Path

from organigramas.heads_manager import HeadsManager
from organigramas.models import Persona, Nodo
from organigramas.pdf_renderer import PDFRenderer


def test_heads_manager_persists_metadata(tmp_path):
    archivo = tmp_path / "heads.json"
    manager = HeadsManager(str(archivo))

    manager.guardar_metadata(
        "1001",
        "J. Pérez",
        {
            "departamento": "Dirección General",
            "centro_costos": "DG-001",
            "responsable": "Ana López",
        },
    )

    # La cabeza se identifica por Nº pers., no por su nombre de despliegue
    assert manager.existe_cabeza("1001") is True
    assert manager.existe_cabeza("J. Pérez") is False
    assert manager.obtener_metadata("1001")["departamento"] == "Dirección General"

    # Y sobrevive a una recarga desde disco
    assert HeadsManager(str(archivo)).obtener_metadata("1001")["centro_costos"] == "DG-001"


def test_heads_manager_tolera_formato_viejo(tmp_path):
    """Una copia local con la forma antigua (solo nombres) no debe reventar."""
    import json

    archivo = tmp_path / "heads.json"
    archivo.write_text(
        json.dumps({"cabezas": ["J. Pérez"], "metadata": {}}), encoding="utf-8"
    )

    manager = HeadsManager(str(archivo))

    # Se carga, pero sin Nº pers. no identifica a nadie: el menu la marca ✗
    assert manager.cabezas == [{"numero_personal": "", "nombre": "J. Pérez"}]
    assert manager.existe_cabeza("J. Pérez") is False


def test_pdf_renderer_generates_bilingual_outputs(tmp_path):
    root = Persona(
        numero_personal="001",
        nombres="Juan Pérez",
        nombre_abreviado="J. Pérez",
        apellido_paterno="Pérez",
        posicion="Director General",
        ceco="DG-001",
    )
    child = Persona(
        numero_personal="002",
        nombres="María García",
        nombre_abreviado="M. García",
        apellido_paterno="García",
        posicion="Gerente de Operación",
        ceco="OPS-001",
        supervisor_nombre="J. Pérez",
    )

    nodo = Nodo(persona=root)
    nodo.agregar_hijo(Nodo(persona=child))

    renderer = PDFRenderer()
    es_pdf = tmp_path / "organigrama_es.pdf"
    en_pdf = tmp_path / "organigrama_en.pdf"

    renderer.generar_pdf(nodo, str(es_pdf), idioma="es")
    renderer.generar_pdf(nodo, str(en_pdf), idioma="en")

    assert es_pdf.exists()
    assert en_pdf.exists()
    assert es_pdf.stat().st_size > 0
    assert en_pdf.stat().st_size > 0
