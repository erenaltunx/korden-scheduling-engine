"""Excel import contract: editable example, bad headers, malicious formulas, bad archive."""
from io import BytesIO
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from optera.xlsx_bridge import make_example_workbook, workbook_to_csv_tables

TABLES = {
  'resources': 'resource_id,name,kind,capabilities\nCNC1,CNC 1,cnc_machine,milling\nQC1,Inspection,inspection_station,inspection\n',
  'orders': 'order_id,name,available_at,due_at,priority\nJOB1,Part A,0,15,5\nJOB2,Part B,1,18,3\n',
  'steps': 'order_id,sequence,step_id,name,duration,requires_all,eligible_resources,reserve_resources,choose_one_support_from,choose_one_support_with\nJOB1,1,mill,Milling,5,milling,,,,\nJOB1,2,qc,Inspect,2,inspection,,,,\nJOB2,1,mill,Milling,5,milling,,,,\n',
  'unavailability': 'resource_id,start,end\nCNC1,8,10\n',
}


def mutate(data: bytes, f) -> bytes:
    wb = load_workbook(BytesIO(data))
    f(wb)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_template_roundtrip():
    raw = make_example_workbook(TABLES)
    parsed = workbook_to_csv_tables(raw)
    assert set(parsed) == set(TABLES)
    assert 'JOB1,Part A,0,15,5' in parsed['orders']
    assert 'CNC1,8,10' in parsed['unavailability']
    assert len(raw) < 320 * 1024


def test_formula_rejected_with_cell_coordinates():
    raw = mutate(make_example_workbook(TABLES), lambda w: setattr(w['steps']['E2'], 'value', '=2+3'))
    with pytest.raises(ValueError, match=r'steps!E2.*formula'):
        workbook_to_csv_tables(raw)


def test_unsupported_sheet_rejected():
    raw = mutate(make_example_workbook(TABLES), lambda w: w.create_sheet('secret'))
    with pytest.raises(ValueError, match='unknown'):
        workbook_to_csv_tables(raw)


def test_missing_headers_rejected():
    raw = mutate(make_example_workbook(TABLES), lambda w: setattr(w['orders']['A1'], 'value', None))
    with pytest.raises(ValueError, match='column headings'):
        workbook_to_csv_tables(raw)


def test_non_integer_processing_time_rejected():
    raw = mutate(make_example_workbook(TABLES), lambda w: setattr(w['steps']['E2'], 'value', 3.5))
    with pytest.raises(ValueError, match='steps!E2'):
        workbook_to_csv_tables(raw)


def test_bad_archive_rejected():
    with pytest.raises(ValueError, match='valid.*xlsx'):
        workbook_to_csv_tables(b'A' * 100)
    with pytest.raises(ValueError, match='320 KiB'):
        workbook_to_csv_tables(b'A' * (321 * 1024))


def test_oversized_internal_files_rejected():
    target = BytesIO()
    with ZipFile(target, 'w') as z:
        z.writestr('large.xml', 'X' * (3 * 1024 * 1024 + 1), compress_type=8)
    with pytest.raises(ValueError, match='oversized'):
        workbook_to_csv_tables(target.getvalue())
