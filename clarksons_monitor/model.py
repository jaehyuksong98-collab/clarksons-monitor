"""Write an output copy only. All existing worksheet XML is preserved verbatim."""
import hashlib
import math
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import openpyxl

SCENARIOS = ('Base Case', 'Bull Case', 'Bear Case')
# Model v5.3: (H2 forecast, FY forecast, H1 actual). Stocks use the same year-end forecast.
MAPPING = {'revenue': ('D6','E6','C6'), 'underlying_op_profit': ('D9','E9','C9'),
           'underlying_pbt': ('D12','E12','C12'), 'receivables': ('D23','D23','C23'),
           'net_cash_available': ('D40','D40','C33')}
for i,s in enumerate(('broking','financial','support','research'),52):
    MAPPING[s+'_revenue'] = (f'H{i}',None,f'B{i}')
    MAPPING[s+'_op_profit'] = (f'I{i}',None,f'C{i}')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(model, disclosure):
    values = openpyxl.load_workbook(model, data_only=True)
    rows = []
    if disclosure['period'] != 'FY 2026':
        return rows
    for key, metric in disclosure['metrics'].items():
        if key not in MAPPING:
            continue
        h2cell, fycell, h1cell = MAPPING[key]
        for scenario in SCENARIOS:
            sheet = values[scenario]
            actual = metric['value']
            if key in ('receivables','net_cash_available'):
                forecast = sheet[h2cell].value
                basis = '31 December 2026 stock'
            else:
                # H2 flows = reported FY minus the model's sourced H1 actual anchor.
                h1 = sheet[h1cell].value
                if not isinstance(h1,(int,float)):
                    raise ValueError('Missing cached H1 anchor')
                actual -= h1
                forecast = sheet[h2cell].value
                basis = f'H2 2026 derived: FY reported minus H1 anchor {scenario}!{h1cell}={h1}'
            if not isinstance(forecast,(int,float)) or not math.isfinite(forecast):
                raise ValueError('Missing cached forecast; Excel recalculation is manual')
            rows.append(dict(metric=key, scenario=scenario, actual=actual, forecast=forecast,
                             difference=actual-forecast, basis=basis, url=metric['url'], page=metric['page']))
    return rows


def write_model(model, output, disclosure, comparisons):
    model, output = Path(model), Path(output)
    if model.resolve() == output.resolve() or output.exists():
        raise ValueError('Output must be a new path; originals are immutable')
    original_hash = sha(model)
    w = openpyxl.load_workbook(model)
    if any(n in w.sheetnames for n in ('Actuals_Reported','Scenario_Comparison','Automation_Log')):
        raise ValueError('Expected pristine v5.3 template')
    if not all(n in w.sheetnames for n in SCENARIOS):
        raise ValueError('Unrecognised workbook')
    a = w.create_sheet('Actuals_Reported')
    a.append(['Metric','Period','Value','Unit','Source URL','PDF page','SHA256','Evidence'])
    for key,m in disclosure['metrics'].items():
        if not math.isfinite(m['value']) or m['period'] != disclosure['period'] or not m['page']:
            raise ValueError('Invalid metric')
        a.append([key,m['period'],m['value'],m['unit'],m['url'],m['page'],m['sha256'],m['raw']])
    c = w.create_sheet('Scenario_Comparison')
    c.append(['Metric','Scenario','Actual','Forecast','Actual minus forecast','Basis','Source URL','PDF page'])
    for r in comparisons:
        c.append([r[k] for k in ('metric','scenario','actual','forecast','difference','basis','url','page')])
    log = w.create_sheet('Automation_Log')
    log.append(['Action','Sheet/cell','Old','New','Period','Source','Page','Source SHA256'])
    for i,(key,m) in enumerate(disclosure['metrics'].items(),2):
        log.append(['insert',f'Actuals_Reported!C{i}',None,m['value'],m['period'],m['url'],m['page'],m['sha256']])
    for sheet in (a,c,log):
        sheet.freeze_panes='A2'
        sheet.auto_filter.ref=sheet.dimensions
        for col in 'ABCDEFGH': sheet.column_dimensions[col].width=24 if col not in 'EFGH' else 42
    output.parent.mkdir(parents=True,exist_ok=True)
    # openpyxl serialisation can drop formula caches. Restore all original worksheets,
    # charts/styles/sharedStrings intact, keeping only new sheets and package registrations.
    with tempfile.TemporaryDirectory() as tmp:
        generated=Path(tmp)/'generated.xlsx'
        w.save(generated)
        staged=Path(tmp)/'verified.xlsx'
        registration={'[Content_Types].xml','xl/workbook.xml','xl/_rels/workbook.xml.rels'}
        with ZipFile(model) as old, ZipFile(generated) as new, ZipFile(staged,'w',ZIP_DEFLATED) as final:
            oldnames=set(old.namelist())
            wb=ET.fromstring(old.read('xl/workbook.xml'))
            rels=ET.fromstring(old.read('xl/_rels/workbook.xml.rels'))
            types=ET.fromstring(old.read('[Content_Types].xml'))
            ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
            rn='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            pr='http://schemas.openxmlformats.org/package/2006/relationships'
            ct='http://schemas.openxmlformats.org/package/2006/content-types'
            sheets=wb.find('{'+ns+'}sheets')
            for i,title in enumerate(('Actuals_Reported','Scenario_Comparison','Automation_Log'),len(w.worksheets)-2):
                rid='automationSheet'+str(i)
                ET.SubElement(sheets,'{'+ns+'}sheet',{'name':title,'sheetId':str(i),'{'+rn+'}id':rid})
                ET.SubElement(rels,'{'+pr+'}Relationship',{'Id':rid,'Type':rn+'/worksheet','Target':'/xl/worksheets/sheet'+str(i)+'.xml'})
                ET.SubElement(types,'{'+ct+'}Override',{'PartName':'/xl/worksheets/sheet'+str(i)+'.xml','ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
            replacements={'xl/workbook.xml':ET.tostring(wb), 'xl/_rels/workbook.xml.rels':ET.tostring(rels),'[Content_Types].xml':ET.tostring(types)}
            for name in old.namelist():
                final.writestr(name,replacements.get(name,old.read(name)))
            for name in new.namelist():
                if name not in oldnames: final.writestr(name,new.read(name))
        check=openpyxl.load_workbook(staged,data_only=False)
        cached=openpyxl.load_workbook(staged,data_only=True)
        with ZipFile(model) as old, ZipFile(staged) as new:
            for name in old.namelist():
                if name not in registration and old.read(name)!=new.read(name):
                    raise ValueError('Original package member changed: '+name)
        if len(check['Actuals_Reported']['C']) != len(disclosure['metrics'])+1:
            raise ValueError('Written rows mismatch')
        if cached['Base Case']['D6'].value is None:
            raise ValueError('Forecast cache lost')
        if sha(model)!=original_hash:
            raise ValueError('Source changed')
        # Same-filesystem atomic publication, only after validation.
        fd, tempname=tempfile.mkstemp(dir=output.parent,suffix='.xlsx')
        os.close(fd)
        try:
            Path(tempname).write_bytes(staged.read_bytes())
            os.replace(tempname,output)
        finally:
            Path(tempname).unlink(missing_ok=True)
    return {'source_sha256':original_hash,'output_sha256':sha(output),'inserted_actuals':len(disclosure['metrics']),
            'original_package_parts_preserved':True}
