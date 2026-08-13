from pathlib import Path

from organigramas.heads_manager import HeadsManager
from organigramas.models import Persona, Nodo
from organigramas.pdf_renderer import PDFRenderer


def test_heads_manager_persists_metadata(tmp_path):
    archivo = tmp_path / "heads.json"
    manager = HeadsManager(str(archivo))

    manager.guardar_metadata(
        "J. Pérez",
        {
            "departamento": "Dirección General",
            "centro_costos": "DG-001",
            "responsable": "Ana López",
        },
    )

    assert manager.existe_cabeza("J. Pérez") is True
    assert manager.obtener_metadata("J. Pérez")["departamento"] == "Dirección General"


def test_pdf_renderer_generates_bilingual_outputs(tmp_path):
    root = Persona(
        numero_personal="001",
        nombre_completo="Juan Pérez",
        nombre_abreviado="J. Pérez",
        apellido_paterno="Pérez",
        posicion="Director General",
        ceco="DG-001",
    )
    child = Persona(
        numero_personal="002",
        nombre_completo="María García",
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
