import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.stage1_read import read_documents

class PDF:
    pages = [None]*9
    def __enter__(self): return self
    def __exit__(self,*args): pass

class ExtractionBoundary(unittest.TestCase):
    def read(self, year=2025, disagree=False):
        pages=[(1,f'{year} Annual Report','text')]+[(n,'','image') for n in range(2,10)]
        first={'title':'Consolidated income statement','rows':[{'name':'Revenue','current':'101','prior':'88'}]}
        second={'title':first['title'],'rows':[{'name':'Revenue','current':'102' if disagree else '101','prior':'88'}]}
        with patch('pipeline.stage1_read.page_texts',return_value=pages), patch('pdfplumber.open',return_value=PDF()), patch('pipeline.stage1_read._page_image',return_value=None), patch('pipeline.stage1_read._transcribe',return_value={'votes':[first,second]}) as transcribe:
            ledger=read_documents(['report.pdf'],client=object(),known_values=[9876,8765,7654,6543],target_year=2025,log=lambda *a:None)
        return ledger,transcribe.call_count

    def test_clear_consensus_does_not_buy_another_read_to_match_the_model(self):
        import tempfile
        from unittest.mock import Mock
        from pipeline.stage1_read import _transcribe
        first={"title":"Statement", "rows":[{"name":"Revenue","current":"101","prior":"88"}]}
        conflict={"title":"Statement", "rows":[{"name":"Revenue","current":"102","prior":"88"}]}
        for second, expected in [(first,2),(conflict,3)]:
            client=SimpleNamespace(json=Mock(side_effect=[first,second,first]))
            with tempfile.TemporaryDirectory() as directory, patch('pipeline.stage1_read._cache_key',return_value='fixture'), patch('pipeline.stage1_read._encode',return_value=('image/png','fixture')):
                _transcribe('report.pdf',1,object(),client,[9876],2,directory,lambda *a:None)
            self.assertEqual(client.json.call_count,expected)

    def test_current_document_without_model_anchors_retains_agreed_evidence(self):
        ledger,calls=self.read()
        rows=[x for x in ledger.items if x.channel=='vision']
        self.assertEqual(calls,8)
        self.assertEqual({x.page for x in rows},set(range(2,10)))
        self.assertTrue(all(x.nums==[101,88] and x.scale_hint is None for x in rows))
        self.assertTrue(all(x.consensus==2 and not x.disputed for x in rows))

    def test_disagreeing_readings_remain_visible_but_cannot_auto_join(self):
        ledger,_=self.read(disagree=True)
        rows=[x for x in ledger.items if x.channel=='vision']
        self.assertEqual(len(rows),8)
        self.assertTrue(all(x.disputed and not x.joinable() for x in rows))

    def test_printed_prior_period_avoids_eager_vision_without_numeric_guessing(self):
        ledger,calls=self.read(year=2024)
        self.assertEqual(calls,0)
        self.assertFalse(any(x.channel=='vision' for x in ledger.items))

if __name__=='__main__': unittest.main()
