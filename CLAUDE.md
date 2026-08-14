# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`organigramas` — a Python CLI tool (100% offline) that reads employee data from Excel and generates vertical hierarchical org charts as bilingual (ES/EN) PDFs. Entry point package is `src/organigramas`.

## Commands

```bash
# Install (uv is the project's package manager; uv.lock is present)
uv pip install -e .

# Run the CLI (interactive prompts)
organigramas
# or without installing the entry point:
python -c "from organigramas.cli import main; main()"

# Run tests (no pytest config in pyproject.toml — plain pytest discovery)
pytest
pytest tests/test_metadata_and_pdf.py::test_pdf_renderer_generates_bilingual_outputs

# Verify all modules import cleanly
python test_imports.py
```

Python >= 3.11 required (`.python-version` pins 3.14 locally). Dependencies: `pandas`, `openpyxl`, `reportlab`.

## Architecture

Pipeline, in the order `cli.py:main()` drives it:

1. **`excel_parser.py` (`ExcelParser`)** — reads an Excel file with `pandas`, fuzzy-matches column headers (case-insensitive, multiple accepted variants per field — see `ENCABEZADOS_ESPERADOS`) against expected fields, and builds a list of `Persona` objects. Required columns: número personal, nombre(s), apellido paterno. The supervisor relationship is read from a "supervisor/encargado/jefe" column, falling back to `Cal.Migratoria` if absent. Generates `nombre_abreviado` (e.g. "J.P. Pérez") from initials + apellido paterno — this abbreviated name is the primary key used for hierarchy lookups elsewhere.

2. **`hierarchy.py` (`HierarchyManager`)** — indexes `Persona` list by lowercased `nombre_abreviado` / `nombre_completo` (with/without periods) for case-insensitive lookup. `construir_arbol(cabeza_nombre)` builds a `Nodo` tree by recursively finding subordinates (people whose `supervisor_nombre` resolves to the current node), tracking a per-branch `visitados` set (copied at each recursion level) to detect and skip cycles rather than looping infinitely. `obtener_todas_las_cabezas_posibles()` finds root candidates: people with no supervisor, or whose supervisor name doesn't resolve to anyone in the dataset.

3. **`heads_manager.py` (`HeadsManager`)** — persists selected root people ("cabezas") and their metadata (departamento, centro_costos, responsable) to `data/heads.json`. Owns the interactive CLI menu (`interfaz_seleccion_interactiva`) for picking a saved cabeza, picking one from the current Excel's candidates, or adding a new one manually.

4. **`pdf_renderer.py` (`PDFRenderer` + `Organigrama`)** — `Organigrama` computes a layout (x, y positions per node, keyed by `id(nodo)`) via a two-pass tree-width algorithm (`_calcular_ancho_subtree` then `_calcular_posiciones_recursivo`), independent of any PDF library. `PDFRenderer` draws that layout onto a `reportlab` canvas (landscape A4), scaling the whole tree to fit the page, drawing connector lines before node boxes. `generar_pdf(..., idioma="es"|"en")` picks the label set via `_textos_por_idioma`; `cli.py` always calls this twice per run (once per language) producing `<name>_es.pdf` and `<name>_en.pdf`.

5. **`models.py`** — plain dataclasses: `Persona` (one row), `Nodo` (tree node wrapping a `Persona`, with helper methods `obtener_todos_descendientes`, `profundidad`, `cantidad_subordinados`). Head metadata (departamento, centro_costos, responsable) is passed around as plain dicts, not a dataclass.

`cli.py` wires these together interactively (prompt for Excel path → parse → validate hierarchy → pick/save a cabeza via `HeadsManager` → build tree → prompt for department/CeCo/responsable metadata, reusing prior values if the cabeza was seen before → prompt for output path → render both PDFs → offer to loop again).

### Key invariants
- All hierarchy/head lookups match on `nombre_abreviado` (case-insensitive), not on `numero_personal` — so naming collisions across different people would misattribute subordinates.
- Cycle detection in `hierarchy.py` uses a copied `visitados` set per branch, so a diamond (two branches reaching the same person) is not itself an error — the second occurrence is just silently dropped as a "cycle" via `continue`.
- `data/heads.json` is app-managed persisted state, not sample data — don't hand-edit its structure without checking `heads_manager.py`'s read/write helpers (`_leer_json`/`_guardar_json`).
