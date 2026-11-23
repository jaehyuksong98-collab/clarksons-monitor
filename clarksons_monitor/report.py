from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn


def report(path, result):
    d=Document()
    sec=d.sections[0]
    sec.top_margin=sec.bottom_margin=Inches(.7)
    style=d.styles['Normal']; style.font.name='Calibri'; style.font.size=Pt(10)
    for element in d.element.iter(qn('w:pBdr')):
        element.getparent().remove(element)
    for sty in d.styles:
        for element in list(sty.element.iter(qn('w:pBdr'))): element.getparent().remove(element)
    d.add_heading('Clarksons results monitor',0)
    d.add_paragraph(result['started']+' | Human review required')
    d.add_heading('Run outcome',1)
    d.add_paragraph(result['status'])
    for note in result['notes']: d.add_paragraph(note)
    item=result.get('disclosure')
    if item:
        d.add_heading('Reported financial metrics',1)
        d.add_paragraph(item['period']+' | Period check: '+item['period_check'])
        d.add_paragraph('Source: '+item['url'])
        t=d.add_table(rows=1,cols=4); t.style='Light Shading Accent 1'
        for c,v in zip(t.rows[0].cells,['Metric','Value','Unit','PDF page']): c.text=v
        for k,m in item['metrics'].items():
            for c,v in zip(t.add_row().cells,[k,str(m['value']),m['unit'],str(m['page'])]): c.text=v
        d.add_heading('Management evidence',1)
        d.add_paragraph('Extracts are management statements, not independently established causes of a forecast difference.')
        for c in item['comments']:
            d.add_paragraph(c['text']); d.add_paragraph(f"Source: {c['url']} | PDF p.{c['page']}")
    if result.get('comparisons'):
        d.add_heading('Actual minus forecast',1)
        for r in result['comparisons']:
            d.add_paragraph(f"{r['scenario']} / {r['metric']}: actual {r['actual']:.2f}, forecast {r['forecast']:.2f}, difference {r['difference']:+.2f} GBP million. {r['basis']}. Source: {r['url']} p.{r['page']}.")
        d.add_paragraph('Why: manual attribution required. Review management evidence and news below. No causal allocation to activity, margins, FX, acquisitions or credit losses is inferred.')
    else:
        d.add_paragraph('H2/FY2026 forecast accuracy: not scored. No eligible FY2026 actuals were processed.')
    d.add_heading('Company news and insights',1)
    d.add_paragraph('Official company articles only; not independent media coverage. Article dates may require manual verification. These items are not proven explanations of a result.')
    for n in result['news']:
        d.add_heading(n['title'][:150],2)
        d.add_paragraph(n['text']); d.add_paragraph('Source: '+n['url'])
    if result.get('errors'):
        d.add_heading('Failures requiring attention',1)
        for e in result['errors']: d.add_paragraph(e)
    d.add_heading('Manual review',1)
    d.add_paragraph('Confirm units, accounting basis, restated H1 comparatives and source pages before accepting actuals. ROIC reconciliation, independent media research and causal attribution remain manual. Existing forecasts are frozen; Excel does not recalculate in openpyxl. No LLM or API key is used.')
    d.save(path)
