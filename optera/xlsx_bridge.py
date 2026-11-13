"""Excel workbook adapter for Optera's existing strictly validated CSV contract.

All workbook data stays in-memory. No formulas, macros, external links or dynamic
Excel execution are supported. This module does not infer manufacturing data.
"""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
from zipfile import BadZipFile, ZipFile

from openpyxl import Workbook, load_workbook

REQUIRED = ('resources', 'orders', 'steps')
OPTIONAL = ('unavailability',)
KNOWN = set(REQUIRED + OPTIONAL)
MAX_WORKBOOK_BYTES = 320 * 1024
MAX_UNCOMPRESSED_BYTES = 3 * 1024 * 1024
MAX_ROWS = 500
MAX_COLUMNS = 12


def _check_archive(raw: bytes) -> None:
    if not isinstance(raw, bytes) or len(raw) > MAX_WORKBOOK_BYTES or len(raw) < 20:
        raise ValueError('Excel workbook must be .xlsx and at most 320 KiB')
    try:
        with ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > 120 or sum(f.file_size for f in infos) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('Workbook has too many or oversized internal files')
            if any(f.filename.lower().endswith(('.bin', '.vba')) or 'externallinks/' in f.filename.lower()
                   for f in infos):
                raise ValueError('Macros and external workbook links are not supported')
    except BadZipFile as exc:
        raise ValueError('Not a valid .xlsx Excel workbook') from exc


def _value(cell, sheet: str) -> str:
    if cell.data_type == 'f':
        raise ValueError(f'{sheet}!{cell.coordinate}: formulas are not supported; paste values only')
    if cell.data_type == 'e':
        raise ValueError(f'{sheet}!{cell.coordinate}: Excel error cells are not allowed')
    value = cell.value
    if value is None:
        return ''
    if isinstance(value, bool):
        raise ValueError(f'{sheet}!{cell.coordinate}: use a number or text, not TRUE/FALSE')
    if isinstance(value, (int, float)):
        if not float(value).is_integer():
            raise ValueError(f'{sheet}!{cell.coordinate}: only whole-number time units are supported')
        return str(int(value))
    if not isinstance(value, str):
        raise ValueError(f'{sheet}!{cell.coordinate}: dates and other cell types are not supported')
    if len(value) > 500:
        raise ValueError(f'{sheet}!{cell.coordinate}: value is too long')
    return value.strip()


def workbook_to_csv_tables(raw: bytes) -> dict[str, str]:
    """Extract declared tabs into existing CSV importer, preserving strict checks."""
    _check_archive(raw)
    try:
        workbook = load_workbook(BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    except (BadZipFile, OSError, ValueError, KeyError) as exc:
        raise ValueError('Workbook cannot be opened as a standard .xlsx file') from exc
    try:
        names = set(workbook.sheetnames)
        extras = names - KNOWN - {'Guide'}
        missing = set(REQUIRED) - names
        if missing or extras:
            raise ValueError(f'Workbook tabs must be resources, orders, steps, optional unavailability and Guide; '
                             f'missing: {sorted(missing)}, unknown: {sorted(extras)}')
        output = {}
        for sheet_name in REQUIRED + OPTIONAL:
            if sheet_name not in names:
                continue
            sheet = workbook[sheet_name]
            if (sheet.max_row or 0) > MAX_ROWS + 1 or (sheet.max_column or 0) > MAX_COLUMNS:
                raise ValueError(f'{sheet_name}: maximum {MAX_ROWS} data rows and {MAX_COLUMNS} columns')
            contents = []
            for r, row in enumerate(sheet.iter_rows(), start=1):
                if r > MAX_ROWS + 1:
                    raise ValueError(f'{sheet_name}: too many rows')
                values = [_value(cell, sheet_name) for cell in row]
                if r == 1:
                    if not values or not any(values):
                        raise ValueError(f'{sheet_name}!A1: column headings are required')
                    headers = values
                    if len(set(headers)) != len(headers) or any(not h for h in headers):
                        raise ValueError(f'{sheet_name}!1: missing or duplicate column headings')
                    contents.append(values)
                elif any(values):
                    contents.append(values[:len(headers)] + [''] * max(0, len(headers)-len(values)))
                    if any(values[len(headers):]):
                        raise ValueError(f'{sheet_name}!{r}: unexpected cells beyond the table headers')
            if not contents:
                raise ValueError(f'{sheet_name}: sheet is empty')
            buffer = StringIO(newline='')
            writer = csv.writer(buffer, lineterminator='\n')
            writer.writerows(contents)
            output[sheet_name] = buffer.getvalue()
        return output
    finally:
        workbook.close()


def make_example_workbook(tables: dict[str, str]) -> bytes:
    """Prepare an Excel-editable manufacturing example with valid column headers."""
    if not all(key in tables for key in REQUIRED):
        raise ValueError('Example requires resources, orders and steps')
    workbook = Workbook()
    guide = workbook.active
    guide.title = 'Guide'
    help_lines = [
        'OPTERA — Manufacturing Scheduling Import Template',
        'Edit the example rows in resources, orders and steps; save as .xlsx.',
        'resources: machine/worker IDs and capability tags separated with semicolons.',
        'orders: order ID, release time, due time and integer priority.',
        'steps: operation sequence, processing duration, required capability.',
        'unavailability: optional resource downtime windows (start inclusive, end exclusive).',
        'Time values are whole numbers. Never use Excel formulas or confidential factory data in a public demo.',
        'Import the workbook, review validation feedback, then click Run optimization.',
    ]
    for line in help_lines:
        guide.append([line])
    guide.column_dimensions['A'].width = 105
    for name in REQUIRED + OPTIONAL:
        if name not in tables:
            continue
        sheet = workbook.create_sheet(name)
        for record in csv.reader(StringIO(tables[name])):
            sheet.append(record)
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = min(38, max(16, max(len(str(c.value or '')) for c in column)+2))
    target = BytesIO()
    workbook.save(target)
    workbook.close()
    return target.getvalue()
