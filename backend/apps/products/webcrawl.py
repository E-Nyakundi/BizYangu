"""
BizYangu — web-search-assisted barcode resolution.

Implements barcode-webcrawl-resolution-scoping.md end to end: given a
barcode that resolve_barcode() couldn't find internally, search Google
(via the Programmable Search Engine / Custom Search JSON API), score
every result using only its title/link/snippet, fetch only the results
that clear a minimum score, extract a product name from each, and
reconcile multiple hits into a single best candidate.

TRUST BOUNDARY (design doc §4.5) — the single most important rule in
this file: nothing here ever creates or upgrades a GlobalProduct to
VERIFIED. create_web_candidate() below only ever produces a CANDIDATE
via services.create_candidate-equivalent logic, with
source=GlobalProduct.Source.WEB_SEARCH. The existing internal
confirm/dispute loop (services.record_verification,
CONFIRMATIONS_REQUIRED / CONFLICTS_TO_DISPUTE) remains the only path to
VERIFIED. If you are editing this file and find yourself writing
`status=GlobalProduct.Status.VERIFIED` anywhere, stop — that is
exactly the shortcut this design doc rejects.

Nothing in this module is called synchronously from resolve_barcode().
It is only ever invoked from tasks.discover_barcode_via_web(), itself
only dispatched on UNRESOLVED — see tasks.py's module docstring for the
execution-model reasoning (design doc §4.6).
"""

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# GTIN-8/12/13/14 are the only barcode lengths this layer treats as
# plausibly-real product identifiers. Anything else (design doc §3.3's
# 20-digit case) is cheaper to reject here than to spend a search call
# finding out the same thing from all-noise results — see §4.2's
# "barcode-length pre-check, before the search call is even made."
VALID_GTIN_LENGTHS = (8, 12, 13, 14)

# Below this, a result is not fetched at all — the fail-closed rule in
# design doc §4.2. Chosen so that a single weak signal (e.g. just a
# price token, no barcode-list-style row and no SKU/stock language)
# doesn't clear the bar on its own; two weak signals or one strong one
# should. Deliberately a module constant like CONFIRMATIONS_REQUIRED in
# services.py, not buried in a function, so it's one place to tune.
MIN_SCORE_TO_FETCH = 3

# Domains that produced zero real product hits across all three test
# cases in the scoping doc's §3, and/or are structurally unsuited to
# ever hosting a barcode-keyed product listing (classifieds, social
# media, video, general marketplaces). Matched against the registrable
# domain of each result's link. This list is deliberately narrow and
# evidence-based rather than a giant generic blocklist — extend it as
# new noise domains are observed, per design doc §3.3.
EXCLUDED_DOMAINS = {
    'facebook.com', 'www.facebook.com',
    'instagram.com', 'www.instagram.com',
    'tiktok.com', 'www.tiktok.com',
    'pinterest.com', 'www.pinterest.com',
    'alibaba.com', 'www.alibaba.com',
    'commons.wikimedia.org', 'wikimedia.org',
    'youtube.com', 'www.youtube.com',
    # Case 3.1's noise: pet adoption, property rental, general
    # marketplace/classifieds sites are all the same shape of
    # "coincidental number match," not aggregator- or retailer-shaped.
    'adoptapet.com', 'www.adoptapet.com',
    'olx.co.ke', 'www.olx.co.ke',
    'jiji.co.ke', 'www.jiji.co.ke',
}

# barcode-list.com's exact repeating row shape from design doc §3.1/§3.2:
#   "61614215, VASELINE 95ML ALOE FRESH, 6. 76, 61614215, ..."
# i.e. digits, comma, an UPPERCASE-ish product name, comma, more
# digit/number tokens, repeating. We don't need to fully parse the
# grammar here for scoring — just detect the shape cheaply.
_AGGREGATOR_ROW_RE = re.compile(
    r'\d{6,14}\s*,\s*[A-Z0-9][A-Z0-9 ./%-]{3,60}\s*,'
)

# E-commerce signal per design doc §4.2: a price token, SKU label, or
# stock-status phrasing. KES-only for now (this app's home market) —
# extend to other currency symbols if BizYangu ever expands.
_PRICE_RE = re.compile(r'\bKES\s?\d|\bKsh\.?\s?\d|\b\d+(\.\d{2})?\s?/?=\b', re.IGNORECASE)
_SKU_RE = re.compile(r'\bSKU\b', re.IGNORECASE)
_STOCK_RE = re.compile(r'\bin stock\b|\badd to cart\b', re.IGNORECASE)


@dataclass
class ScoredResult:
    title: str
    link: str
    snippet: str
    domain: str
    score: int
    is_aggregator_shaped: bool
    is_ecommerce_shaped: bool


@dataclass
class ExtractedCandidate:
    name: str
    domain: str
    kind: str  # ExternalSource.Kind value
    weight: int  # relative evidence weight, used in reconcile()
    detail: str = ''


@dataclass
class DiscoveryResult:
    """What discover() hands back to the caller (tasks.py)."""
    candidate_name: str | None
    contributing_domains: list = field(default_factory=list)  # (domain, kind) pairs
    raw_hits_considered: int = 0
    raw_hits_fetched: int = 0


def is_plausible_gtin(barcode):
    """
    Cheap pre-check, before any search call is made. Design doc §3.3 /
    §4.2 / §6's test case 3: a 20-digit input should be rejected here,
    independently of the pre-fetch scorer also being able to catch it
    on its own — the doc is explicit both mechanisms should be
    verified, since either failing silently would be easy to miss.
    """
    digits = (barcode or '').strip()
    return digits.isdigit() and len(digits) in VALID_GTIN_LENGTHS


def _registrable_domain(url):
    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ''


def _score_result(title, link, snippet):
    """
    Scores one Custom Search JSON API result item using only its
    title/link/snippet — no page fetched yet. Returns a ScoredResult.

    This is the function design doc §4.2 calls "the core of the
    design" — it's what makes the difference between case 3.2 (clean
    signal amid two-thirds noise) and case 3.3 (100% noise) cheap and
    correct to tell apart before spending a single HTTP fetch.
    """
    domain = _registrable_domain(link)
    text = f'{title}\n{snippet}'

    if domain in EXCLUDED_DOMAINS:
        return ScoredResult(title, link, snippet, domain, score=0,
                             is_aggregator_shaped=False, is_ecommerce_shaped=False)

    is_aggregator = bool(_AGGREGATOR_ROW_RE.search(snippet))
    is_ecommerce = bool(_PRICE_RE.search(text) or _SKU_RE.search(text) or _STOCK_RE.search(text))

    score = 0
    if is_aggregator:
        score += 3
    if is_ecommerce:
        score += 3
    # A tiny bonus for the barcode digits appearing in the title itself
    # (as opposed to only buried in a long snippet) — mild signal, not
    # load-bearing on its own, per §4.2's framing that any single weak
    # signal shouldn't clear MIN_SCORE_TO_FETCH alone.
    if re.search(r'\d{8,14}', title):
        score += 1

    return ScoredResult(title, link, snippet, domain, score, is_aggregator, is_ecommerce)


def _search_google(barcode):
    """
    Calls the Google Programmable Search Engine (Custom Search JSON
    API) — design doc §4.1. Deliberately NOT scraping google.com/search
    directly (ToS violation, gets IPs banned — see §4.1 and §5's
    explicit non-goal). Returns the raw list of result items (dicts
    with 'title'/'link'/'snippet'), or [] on any error — a failed
    search should degrade to UNRESOLVED, never raise into the caller
    and never fall back to scraping.
    """
    api_key = getattr(settings, 'GOOGLE_CSE_API_KEY', '') or ''
    engine_id = getattr(settings, 'GOOGLE_CSE_ENGINE_ID', '') or ''
    if not api_key or not engine_id:
        logger.warning('webcrawl: GOOGLE_CSE_API_KEY/ENGINE_ID not configured, skipping search')
        return []

    try:
        resp = requests.get(
            'https://www.googleapis.com/customsearch/v1',
            params={'key': api_key, 'cx': engine_id, 'q': barcode, 'num': 10},
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json().get('items', []) or []
    except (requests.RequestException, ValueError) as exc:
        logger.warning('webcrawl: search failed for barcode=%s: %s', barcode, exc)
        return []


def _extract_aggregator_row(barcode, snippet):
    """
    Primary extractor (design doc §4.3.1): parse barcode-list.com's
    specific repeating row shape directly out of the snippet, rather
    than fetching the page — the payload is already sitting in the
    SERP snippet for this site, as seen in both successful test cases
    (§3.1, §3.2). Falls back to a page fetch only if the snippet-level
    parse fails (e.g. name got truncated mid-snippet).

    Returns the extracted product name, or None.
    """
    # Find the row whose leading digits match this barcode specifically
    # — a snippet can contain several rows (multiple barcodes on one
    # aggregator page), and we only want the one for our own query.
    pattern = re.compile(
        re.escape(barcode) + r'\s*,\s*([A-Z0-9][A-Z0-9 ./%-]{3,60}?)\s*,',
    )
    match = pattern.search(snippet)
    if match:
        return match.group(1).strip()
    return None


def _extract_generic_page(link):
    """
    Fallback extractor (design doc §4.3.2): fetch the page and read
    og:title or JSON-LD Product.name. Used for anything that passed
    scoring but isn't aggregator-shaped — retailer pages like
    cleanshelf.online in test case 3.2.

    Returns (name, extra_detail) or (None, ''). Never raises — a fetch
    or parse failure here should just mean "this result contributed
    nothing," not blow up the whole pipeline for one bad page.
    """
    try:
        resp = requests.get(link, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as exc:
        logger.info('webcrawl: fetch failed for %s: %s', link, exc)
        return None, ''

    # JSON-LD Product schema first — more structured / reliable than
    # OpenGraph when both are present.
    for ld_match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        block = ld_match.group(1)
        if '"@type"' in block and 'Product' in block:
            name_match = re.search(r'"name"\s*:\s*"([^"]{2,200})"', block)
            price_match = re.search(r'"price"\s*:\s*"?([\d.]+)"?', block)
            if name_match:
                detail = f'price={price_match.group(1)}' if price_match else ''
                return name_match.group(1).strip(), detail

    # OpenGraph fallback.
    og_match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']{2,200})["\']',
        html, re.IGNORECASE,
    )
    if og_match:
        return og_match.group(1).strip(), ''

    return None, ''


def reconcile(candidates):
    """
    Combines multiple ExtractedCandidate objects into one winning name
    plus the domains that back it, per design doc §4.4:

      - Retailer-with-own-SKU/price hits are weighted above generic
        aggregator re-listings (candidate.weight already encodes this
        at extraction time — retailer kind gets a higher weight).
      - Repeated hits from the SAME domain collapse into one weighted
        vote, not N independent confirmations — otherwise one chatty
        aggregator domain (case 3.2 had six barcode-list.com rows from
        a single crawl) could single-handedly satisfy the internal
        loop's CONFIRMATIONS_REQUIRED on its own once this candidate
        later goes through the normal confirm/dispute flow, defeating
        the point of requiring independent businesses to agree.

    Returns (winning_name, [(domain, kind), ...]) or (None, []) if
    given no candidates.
    """
    if not candidates:
        return None, []

    # Collapse same-domain hits: keep the highest-weight one per
    # domain, discard the rest of that domain's repeats entirely
    # rather than summing their weight — summing would just move the
    # "one domain dominates" problem from vote-count to weight-sum.
    best_per_domain = {}
    for c in candidates:
        existing = best_per_domain.get(c.domain)
        if existing is None or c.weight > existing.weight:
            best_per_domain[c.domain] = c

    collapsed = list(best_per_domain.values())

    # Winning name: highest total weight across the (already-collapsed,
    # one-per-domain) votes for that exact name. Names are compared
    # case-insensitively after whitespace normalization since the same
    # product shows up with minor formatting differences across sites
    # (e.g. "VASELINE 95ML ALOE FRESH" vs "Vaseline Aloe Vera Fresh 95G").
    def _norm(name):
        return re.sub(r'\s+', ' ', name.strip().upper())

    tally = {}
    for c in collapsed:
        key = _norm(c.name)
        tally.setdefault(key, {'weight': 0, 'display': c.name, 'domains': []})
        tally[key]['weight'] += c.weight
        tally[key]['domains'].append((c.domain, c.kind))
        # Prefer the more descriptive/longer display form once weight ties.
        if len(c.name) > len(tally[key]['display']):
            tally[key]['display'] = c.name

    winner_key = max(tally, key=lambda k: tally[k]['weight'])
    winner = tally[winner_key]
    return winner['display'], winner['domains']


def discover(barcode):
    """
    Full pipeline entry point — search, score, selectively fetch,
    extract, reconcile. Returns a DiscoveryResult. Safe to call
    repeatedly; makes no database writes itself (tasks.py owns
    persisting the outcome as a CANDIDATE) so it stays independently
    testable against the three fixture barcodes in design doc §6.
    """
    barcode = (barcode or '').strip()

    if not is_plausible_gtin(barcode):
        # Test case 3.3's first line of defense — reject before any
        # search call is made at all. See is_plausible_gtin's docstring.
        logger.info('webcrawl: barcode=%s not a plausible GTIN length, skipping search', barcode)
        return DiscoveryResult(candidate_name=None)

    raw_items = _search_google(barcode)
    scored = [
        _score_result(item.get('title', ''), item.get('link', ''), item.get('snippet', ''))
        for item in raw_items
    ]

    to_fetch = [r for r in scored if r.score >= MIN_SCORE_TO_FETCH]

    if not to_fetch:
        # Fail-closed rule (§4.2) — test case 3.3's second line of
        # defense, independent of the GTIN pre-check above. Both must
        # be able to catch this case on their own.
        logger.info('webcrawl: barcode=%s — no result cleared MIN_SCORE_TO_FETCH', barcode)
        return DiscoveryResult(candidate_name=None, raw_hits_considered=len(scored))

    extracted = []
    for result in to_fetch:
        if result.is_aggregator_shaped:
            name = _extract_aggregator_row(barcode, result.snippet)
            if name:
                extracted.append(ExtractedCandidate(
                    name=name, domain=result.domain,
                    kind='AGGREGATOR', weight=1,
                ))
                continue
            # Snippet-level parse failed even though it looked
            # aggregator-shaped — fall through to the generic fetch
            # rather than discarding a result that scored well.

        name, detail = _extract_generic_page(result.link)
        if name:
            # Retailer-shaped pages (own SKU/price/stock language)
            # outweigh aggregator re-listings per §4.4 — weight=3
            # vs. aggregator's weight=1 means one retailer hit beats
            # up to two same-name aggregator hits from *different*
            # domains, but not an overwhelming aggregator consensus.
            extracted.append(ExtractedCandidate(
                name=name, domain=result.domain,
                kind='RETAILER' if result.is_ecommerce_shaped else 'OTHER',
                weight=3 if result.is_ecommerce_shaped else 1,
                detail=detail,
            ))

    winning_name, domains = reconcile(extracted)
    return DiscoveryResult(
        candidate_name=winning_name,
        contributing_domains=domains,
        raw_hits_considered=len(scored),
        raw_hits_fetched=len(to_fetch),
    )
