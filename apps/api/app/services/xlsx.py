"""Minimal stdlib XLSX reader (raw cell text only; no formulas, styles or dates)."""
import zipfile
import xml.etree.ElementTree as ET

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _column_number(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    value = 0
    for character in letters:
        value = value * 26 + ord(character.upper()) - ord("A") + 1
    return value


def _raw_cell_value(cell: ET.Element, shared_strings: list[str]) -> str | None:
    inline = cell.find("m:is", NS)
    if inline is not None:
        return "".join(inline.itertext())
    value = cell.find("m:v", NS)
    if value is None:
        return None
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value.text or "0")]
    return value.text


def read_xlsx_rows(path, sheet_name: str | None = None) -> list[list[str | None]]:
    """Rows of one worksheet as raw cell text. ``path`` may be a path or a file object; no name = first sheet."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml")) if "xl/sharedStrings.xml" in names else None
        shared_strings = ["".join(item.itertext()) for item in shared_root.findall("m:si", NS)] if shared_root is not None else []
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        sheets = workbook.findall("m:sheets/m:sheet", NS)
        sheet = next((item for item in sheets if item.attrib.get("name") == sheet_name), None) if sheet_name else (sheets[0] if sheets else None)
        if sheet is None:
            raise ValueError(f"Workbook does not contain worksheet {sheet_name!r}.")
        target = targets[sheet.attrib[REL_ID]].lstrip("/")
        target = target if target.startswith("xl/") else f"xl/{target}"
        sheet_xml = ET.fromstring(archive.read(target))
        xml_rows = sheet_xml.findall("m:sheetData/m:row", NS)

    rows: list[list[str | None]] = []
    for xml_row in xml_rows:
        values: list[str | None] = []
        for cell in xml_row.findall("m:c", NS):
            column = _column_number(cell.attrib["r"])
            while len(values) < column:
                values.append(None)
            values[column - 1] = _raw_cell_value(cell, shared_strings)
        rows.append(values)
    if not rows:
        raise ValueError(f"Worksheet {sheet_name!r} is empty.")
    return rows

