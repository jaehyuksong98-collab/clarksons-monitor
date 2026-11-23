import hashlib
import io
import re
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = 'https://www.clarksons.com'
LISTING = ROOT + '/home/investors/results-and-presentations/'


def fetch(url):
    # Validate every redirect before requesting it; never follow an off-host URL.
    for _ in range(5):
        if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'www.clarksons.com':
            raise ValueError('Unapproved source: ' + url)
        r = requests.get(url, headers={'User-Agent': 'ClarksonsScenarioMonitor/0.1 (independent portfolio research)'},
                         timeout=(15, 60), allow_redirects=False)
        if r.is_redirect:
            url = urljoin(url, r.headers['Location'])
            continue
        r.raise_for_status()
        return r.content
    raise ValueError('Too many redirects')


def listing(html):
    soup = BeautifulSoup(html, 'html.parser')
    nodes = soup.select('.download__item')
    if len(nodes) < 5:
        raise ValueError('Listing structure changed: fewer than five documents')
    found = []
    for node in nodes:
        title_node, link, date_node = node.select_one('.download__title'), node.select_one('a[href]'), node.select_one('.download__date')
        if not all((title_node, link, date_node)):
            raise ValueError('Incomplete listing item')
        title = title_node.get_text(' ', strip=True)
        m = re.fullmatch(r'Interim Results Announcement (\d{4})', title, re.I)
        f = re.fullmatch(r'Preliminary Results for the 12 months ended 31 December (\d{4}) Announcement', title, re.I)
        if not (m or f):
            continue
        year = int((m or f)[1])
        published = datetime.strptime(date_node.get_text(strip=True), '%d/%m/%Y').date()
        if published > date.today():
            raise ValueError('Future publication date')
        found.append(dict(title=title, period=f'{"H1" if m else "FY"} {year}', year=year,
                          published=published.isoformat(), url=urljoin(LISTING, link['href'])))
    if not found:
        raise ValueError('No recognised announcements')
    return sorted(found, key=lambda x: x['published'], reverse=True)


def extract(content, item):
    if not content.startswith(b'%PDF'):
        raise ValueError('Not a PDF')
    pages = [p.extract_text() or '' for p in PdfReader(io.BytesIO(content)).pages]
    first = ' '.join(pages[0].split())
    period = item['period']
    year = item['year']
    expected = (rf'six months ended 30 June {year}' if period.startswith('H1')
                else rf'(?:year|12 months) ended 31 December {year}')
    if not re.search(expected, first, re.I):
        raise ValueError('Period check failed on first page')
    metrics = {}

    def add(name, pattern, unit='GBP million', page_filter=None):
        matches = []
        for n, text in enumerate(pages, 1):
            if page_filter and not page_filter(text, n):
                continue
            for m in re.finditer(pattern, text, re.I | re.M):
                matches.append((float(m[1].replace(',', '')), n, m[0]))
        if not matches:
            raise ValueError('Manual extraction required: ' + name)
        if len({v for v, _, _ in matches}) != 1:
            raise ValueError('Conflicting values: ' + name)
        value, page, raw = matches[0]
        metrics[name] = dict(value=value, unit=unit, page=page, raw=raw, period=period,
                             url=item['url'], sha256=hashlib.sha256(content).hexdigest())

    num = r'([0-9][0-9,]*\.?[0-9]*)'
    add('revenue', r'^Revenue\s+£' + num + r'm', page_filter=lambda t,n: n == 1)
    add('underlying_pbt', r'^Underlying profit before taxation\*?\s+£' + num + r'm', page_filter=lambda t,n: n == 1)
    add('underlying_eps', r'^Underlying basic earnings per share\*?\s+' + num + 'p', 'pence', lambda t,n:n == 1)
    # Multiline financial-table patterns are intentionally strict. Unknown layouts stop all writes.
    for name, segment in [('broking','Broking'),('financial','Financial'),('support','Support'),('research','Research')]:
        add(name + '_revenue', segment + r'\s+Revenue:\s*£' + num + 'm')
        add(name + '_op_profit', segment + r'\s+Revenue:[^\n]*\n\s*Segmental operating profit:\s*£' + num + 'm')
    add('net_cash_available', r'^\s*Net cash and available funds\s+' + num + r'\s', page_filter=lambda t,n: 'Reconciliation of reported cash' in t)
    add('receivables', r'Current assets\s+Inventories\s+[^\n]+\nTrade and other receivables\s+\d+\s+' + num)
    add('underlying_op_profit', r'^Operating profit\s+\d+\s+' + num,
        page_filter=lambda t,n:'Consolidated income statement' in t and 'Before' in t and 'acquisition-' in t)
    total = sum(metrics[s+'_revenue']['value'] for s in ['broking','financial','support','research'])
    if abs(total - metrics['revenue']['value']) > .21:
        raise ValueError('Segment revenue does not reconcile')
    comments = []
    for n,t in enumerate(pages,1):
        if 'commented:' in t or 'Chief Executive Officer’s review' in t:
            # Evidence, not a generated explanation of numerical variance.
            comments.append(dict(page=n, url=item['url'], text=' '.join(t.split())[:2200]))
    return dict(**item, metrics=metrics, comments=comments, sha256=hashlib.sha256(content).hexdigest(), period_check='PASS')


def news():
    url = ROOT + '/home/news-and-insights/'
    soup = BeautifulSoup(fetch(url), 'html.parser')
    result, seen = [], set()
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href']).split('#')[0]
        if '/home/news-and-insights/' not in target or target.rstrip('/') == url.rstrip('/') or target in seen:
            continue
        if urlparse(target).hostname != 'www.clarksons.com':
            continue
        title = a.get_text(' ', strip=True)
        if len(title) < 15:
            continue
        seen.add(target)
        page = BeautifulSoup(fetch(target), 'html.parser')
        main = page.find('main') or page
        text = ' '.join(main.get_text(' ', strip=True).split())
        result.append(dict(title=title, url=target, text=text[:2500],
                           published=(page.find('time').get('datetime') if page.find('time') else None)))
        if len(result) == 5:
            break
    if not result:
        raise ValueError('No news articles recognised; manual review required')
    return result
