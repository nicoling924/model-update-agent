"""Pins for carrying exact source identity from context through a write."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_mvp_contract import museum
from pipeline.mapping import _entries, _apply, verdict, build_context, input_rows

class SourceHandoff(unittest.TestCase):
    def setUp(self):
        self.loop, self.pages, self.census = museum._map_model()
        self.pages[("report with spaces.pdf",17)] = "Other gains, net 460 420"
        self.proposal = {"ref":"Final!C3", "printed":460,
            "source_ref":{"doc":"report with spaces.pdf","page":17},
            "line":"Other gains, net 460 420", "because":"Disclosed input"}

    def test_structured_source_survives_batch_to_actual_write(self):
        proposal=dict(self.proposal); source=proposal.pop('source_ref')
        entries,bad=_entries(self.loop,{"sets":[proposal],"source_ref":source})
        self.assertFalse(bad)
        _apply(self.loop,entries,self.pages,{"report with spaces.pdf"},lambda *a:None)
        self.assertEqual(self.loop.wb['Final']['C3'].value,460)
        self.assertEqual(entries[0]['source_ref'],source)

    def test_wrong_page_does_not_write_or_report_a_unit_problem(self):
        self.proposal['source_ref']['page']=23
        entries,_=_entries(self.loop,self.proposal)
        value,_,why,_=verdict(self.loop,entries[0],self.pages,{'report with spaces.pdf'},lambda *a:None)
        self.assertIsNone(value)
        self.assertIn('document/page is unavailable',why)
        self.proposal['source_ref']['page']=17; self.proposal['printed']=999
        entries,_=_entries(self.loop,self.proposal)
        value,_,why,_=verdict(self.loop,entries[0],self.pages,{'report with spaces.pdf'},lambda *a:None)
        self.assertIsNone(value); self.assertIn('quoted line is absent',why)

    def test_conflicting_source_identity_is_not_guessed(self):
        self.proposal['doc']='another.pdf'
        entries,_=_entries(self.loop,self.proposal)
        value,_,why,_=verdict(self.loop,entries[0],self.pages,{'report with spaces.pdf'},lambda *a:None)
        self.assertIsNone(value); self.assertIn('conflicts',why)

    def test_verified_quote_without_scale_has_distinct_diagnostic(self):
        self.pages[("report with spaces.pdf",17)]='Other gains, net 460'
        self.proposal['line']='Other gains, net 460'
        entries,_=_entries(self.loop,self.proposal)
        with patch('pipeline.mapping._page_scales',return_value={}):
            value,_,why,_=verdict(self.loop,entries[0],self.pages,{'report with spaces.pdf'},lambda *a:None)
        self.assertIsNone(value); self.assertIn('quoted line is verified',why)

    def test_empty_batch_is_empty_work_not_a_missing_cell(self):
        self.assertEqual(_entries(self.loop,{'sets':[]}),([],[]))

if __name__=='__main__':unittest.main()
