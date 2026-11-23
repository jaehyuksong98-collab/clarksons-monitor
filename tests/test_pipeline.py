import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import openpyxl
from clarksons_monitor.sources import extract, listing
from clarksons_monitor.model import compare, write_model, sha
from clarksons_monitor.__main__ import main

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'models/scenario-original.xlsx'
FIX=ROOT/'tests/fixtures'


def disclosure():
    return extract((FIX/'h1-2026.pdf').read_bytes(),listing((FIX/'listing.html').read_bytes())[0])


class PipelineTests(unittest.TestCase):
    def test_real_pdf_values_and_page_provenance(self):
        d=disclosure()
        for key,value,page in [('revenue',413.5,1),('underlying_op_profit',56.8,19),('net_cash_available',178.8,32),('receivables',268.8,20)]:
            self.assertEqual((d['metrics'][key]['value'],d['metrics'][key]['page']),(value,page))
        self.assertEqual(len(d['metrics']),14)

    def test_period_mismatch_rejected(self):
        item=listing((FIX/'listing.html').read_bytes())[0]
        item.update(period='FY 2026',year=2026)
        with self.assertRaisesRegex(ValueError,'Period check'):
            extract((FIX/'h1-2026.pdf').read_bytes(),item)

    def test_broken_listing_rejected(self):
        with self.assertRaises(ValueError): listing('<html/>')

    def test_exact_original_parts_and_cache_preserved(self):
        before=sha(MODEL)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'copy.xlsx'
            write_model(MODEL,out,disclosure(),[])
            original=openpyxl.load_workbook(MODEL,data_only=True)
            changed=openpyxl.load_workbook(out,data_only=True)
            self.assertEqual(changed['Base Case']['D6'].value,original['Base Case']['D6'].value)
            self.assertEqual(changed['Actuals_Reported']['C2'].value,413.5)
            with ZipFile(MODEL) as a, ZipFile(out) as b:
                for n in a.namelist():
                    if n not in {'[Content_Types].xml','xl/workbook.xml','xl/_rels/workbook.xml.rels'}:
                        self.assertEqual(a.read(n),b.read(n),n)
            self.assertEqual(len(changed['Automation_Log']['A']),15)
        self.assertEqual(before,sha(MODEL))

    def test_source_overwrite_rejected(self):
        with self.assertRaises(ValueError): write_model(MODEL,MODEL,disclosure(),[])

    def test_invalid_metric_does_not_create_workbook(self):
        d=disclosure(); d['metrics']['revenue']['value']=float('nan')
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'bad.xlsx'
            with self.assertRaises(ValueError): write_model(MODEL,output,d,[])
            self.assertFalse(output.exists())

    def test_h1_is_not_scored_against_h2(self):
        self.assertEqual(compare(MODEL,disclosure()),[])

    def test_fy_comparison_math_synthetic_not_real_results(self):
        d=disclosure(); d['period']='FY 2026'  # Synthetic period only for arithmetic unit test.
        rows=compare(MODEL,d)
        revenue=next(r for r in rows if r['metric']=='revenue' and r['scenario']=='Base Case')
        self.assertEqual(revenue['actual'],0)
        self.assertAlmostEqual(revenue['difference'],-458.6198286050655)
        cash=next(r for r in rows if r['metric']=='net_cash_available' and r['scenario']=='Base Case')
        self.assertEqual(cash['actual'],178.8)  # Stocks are never FY minus H1.

    def test_no_new_result_does_not_touch_model(self):
        with tempfile.TemporaryDirectory() as t:
            args=['monitor','--model','/nonexistent/model.xlsx','--output',t,'--state',t+'/state.json']
            with patch('sys.argv',args), patch('clarksons_monitor.__main__.fetch',return_value=(FIX/'listing.html').read_bytes()), patch('clarksons_monitor.__main__.news',return_value=[]), patch('clarksons_monitor.__main__.write_model') as write:
                self.assertEqual(main(),0); write.assert_not_called()
            self.assertEqual(json.loads((Path(t)/'run.json').read_text())['status'],'no_new_result')
            self.assertFalse((Path(t)/'scenario-with-actuals.xlsx').exists())

    def test_extraction_failure_never_advances_state(self):
        with tempfile.TemporaryDirectory() as t:
            item=dict(period='FY 2026',year=2026,url='https://www.clarksons.com/bad.pdf')
            args=['monitor','--output',t,'--state',t+'/state.json']
            with patch('sys.argv',args), patch('clarksons_monitor.__main__.listing',return_value=[item]), patch('clarksons_monitor.__main__.fetch',return_value=b'bad'), patch('clarksons_monitor.__main__.news',return_value=[]):
                self.assertEqual(main(),1)
            self.assertFalse((Path(t)/'state.json').exists())
            self.assertFalse((Path(t)/'scenario-with-actuals.xlsx').exists())

if __name__=='__main__': unittest.main()
