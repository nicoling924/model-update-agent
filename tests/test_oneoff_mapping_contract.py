"""The mapper's semantic event decision reaches forecast-intent preservation."""
import copy
import runpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.mapping import _apply
from pipeline.freeze import hold_oneoff_forecasts


def test_mapped_event_preserves_zero_future_but_leaves_stock_roll_live():
    fixture = runpy.run_path(str(Path(__file__).with_name('test_pipeline_museum.py')))
    loop, pages, _ = fixture['_map_model']()
    ws = loop.wb['Final']
    loop.spec['year_axis']['Final']['columns'].update({'2026':'D','2027':'E'})
    ws['C3'] = 0; ws['D3'] = '=C3'; ws['E3'] = '=D3'
    ws['C11'] = 100; ws['D11'] = '=C11+D3'; ws['E11'] = '=D11+E3'
    before = copy.deepcopy(loop.wb)
    _apply(loop, [{'sheet':'Final','coord':'C3','printed':460,'doc':'ar.pdf','page':23,
                  'line':'Other gains, net 460 420','one_off':True,
                  'one_off_reason':'Discrete disposal gain; future event forecasts were zero.'}],
           pages, {'ar.pdf'}, lambda *_: None)
    # A rollover may materialize the event as a number; the original zero still owns intent.
    ws['E3'] = 460
    event = loop.writer.log['oneoff_inputs']['Final!3']
    hold_oneoff_forecasts(loop.wb,before,loop.spec,2025,'Final',3,loop.writer,event['because'])
    assert ws['C3'].value == 460
    assert ws['D3'].value == 0 and ws['E3'].value == 0
    assert ws['D11'].value == '=C11+D3' and ws['E11'].value == '=D11+E3'

if __name__ == '__main__':
    test_mapped_event_preserves_zero_future_but_leaves_stock_roll_live()
    print('PASS mapper event forecast contract')
