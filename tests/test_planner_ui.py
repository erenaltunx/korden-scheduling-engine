"""Accessible three-step planner UI contracts, preserving the tested optimization API."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re

from fastapi.testclient import TestClient
from optera.api import app

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
JS=(ROOT/"static"/"app.js").read_text(encoding="utf-8")
CSS=(ROOT/"static"/"planner.css").read_text(encoding="utf-8")


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.tags={}
        self.details=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
            self.tags[a["id"]]=(tag,a)
        if tag=="details":
            self.details.append(a)


def test_all_js_element_references_exist_once():
    doc=Markup()
    doc.feed(HTML)
    duplicates=[id for id,n in Counter(doc.ids).items() if n!=1]
    assert not duplicates,duplicates
    references=set(re.findall(r"\$\(['\"]([^'\"]+)['\"]\)",JS))
    assert references.issubset(set(doc.ids)), sorted(references-set(doc.ids))


def test_first_screen_is_simple_and_advanced_options_collapsed():
    doc=Markup()
    doc.feed(HTML)
    assert HTML.index('id="step-input"')<HTML.index('id="step-run"')<HTML.index('id="results"')
    assert doc.tags["modeDemo"][0]=="button"
    assert doc.tags["modeDemo"][1]["aria-pressed"]=="true"
    assert doc.tags["modeExcel"][1]["aria-pressed"]=="false"
    assert doc.tags["demoPanel"][0]=="div"
    assert "hidden" in doc.tags["excelPanel"][1]
    assert all("open" not in attrs for attrs in doc.details)
    assert doc.tags["advancedOptions"][0]=="details"
    assert doc.tags["runButton"][0]=="button"


def test_ui_keeps_excel_import_and_core_expert_controls():
    doc=Markup()
    doc.feed(HTML)
    for required in ("enterpriseWorkbook","enterpriseWorkbookImport",
                     "enterpriseFeedback","enterpriseFiles","engineSelect",
                     "limitInput","outageMachine","applyShift","jsonEditor",
                     "tabOptimized","tabBaseline","timeline","downloadButton",
                     "exportBiButton"):
        assert required in doc.tags
    assert 'setInputMode(' in JS
    assert "scrollIntoView" in JS


def test_responsive_styles_and_hidden_state_are_explicit():
    assert "[hidden]{display:none!important}" in CSS
    assert "@media(max-width:600px)" in CSS
    assert ":focus-visible" in CSS
    assert "prefers-reduced-motion" in CSS


def test_public_frontend_serves_new_ui_without_changing_api():
    client=TestClient(app)
    page=client.get("/")
    assert page.status_code==200
    assert "A better production plan." in page.text
    stylesheet=client.get("/static/planner.css")
    assert stylesheet.status_code==200
    assert stylesheet.headers["content-type"].startswith("text/css")
    js=client.get("/static/app.js")
    assert js.status_code==200
    assert "setInputMode" in js.text
    config=client.get("/api/config")
    assert config.status_code==200
    assert "max_solver_seconds" in config.json()


def test_initial_run_requires_loaded_data_and_export_label_is_honest():
    doc=Markup()
    doc.feed(HTML)
    assert "disabled" in doc.tags["runButton"][1]
    assert "hidden" in doc.tags["exportBiButton"][1]
    assert "CSV for Power BI (.zip)" in HTML
    assert "favicon.svg" in HTML


def test_upload_mode_keeps_a_validation_gate_and_discard_rule():
    assert "loadedInputKind !== selectedInputMode" in JS
    assert "invalidateExcelImport" in JS
    assert "runRevision!==inputRevision" in JS
    assert "syncRunAvailability" in JS
