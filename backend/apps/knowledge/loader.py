"""
BizYangu — Phase 8 knowledge base loader.

Reads knowledge/*.json (business_types, categories, subcategories, units,
templates/*.json) from disk and resolves the id-references between them
into the shape the frontend actually wants (onboarding category pickers,
reconciliation-queue suggestions, within-business brand suggestions).

Per the Build Plan v3 / knowledge/README.md split: Phase 8 produced the
JSON, Phase 9 is what actually reads it — this module is that read path.
The JSON lives at repo-root `knowledge/`, sibling to `backend/`, not
inside any Django app, so it stays a single source of truth shared with
whatever else might read it later (frontend build, admin tooling, etc).

Caching: loaded once per process and cached in memory — this is static,
version-controlled content that only changes on deploy, not per-request
data. Call `clear_cache()` (or restart the process) after editing the
JSON by hand during a dev session.
"""

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

KNOWLEDGE_DIR = Path(settings.BASE_DIR).parent / 'knowledge'


def _read_json(relative_path: str):
    path = KNOWLEDGE_DIR / relative_path
    with open(path, encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _business_types():
    return _read_json('business_types.json')['business_types']


@lru_cache(maxsize=1)
def _categories_by_id():
    return {c['id']: c for c in _read_json('categories.json')['categories']}


@lru_cache(maxsize=1)
def _subcategories_by_id():
    return {s['id']: s for s in _read_json('subcategories.json')['subcategories']}


@lru_cache(maxsize=1)
def _units_by_id():
    return {u['id']: u for u in _read_json('units.json')['units']}


@lru_cache(maxsize=32)
def _template(business_type_id: str):
    """Raises FileNotFoundError if no template exists for this type yet
    (e.g. the declared-but-not-built clothing_store niches — see
    knowledge/README.md)."""
    return _read_json(f'templates/{business_type_id}.json')


def clear_cache():
    """Drop all cached JSON — call after hand-editing knowledge/ files
    without restarting the server (dev convenience only)."""
    _business_types.cache_clear()
    _categories_by_id.cache_clear()
    _subcategories_by_id.cache_clear()
    _units_by_id.cache_clear()
    _template.cache_clear()


def list_business_types():
    """Public shape for GET /knowledge/business-types/ — drops internal
    notes, keeps id/name/kind/niches/notes-for-humans."""
    return [
        {
            'id': bt['id'],
            'name': bt['name'],
            'kind': bt['kind'],
            'niches': bt.get('niches', []),
            'sub_niche_capable': bt.get('sub_niche_capable', False),
            'combinable_with': bt.get('combinable_with', []),
        }
        for bt in _business_types()
    ]


def _resolve_unit(unit_id: str):
    u = _units_by_id().get(unit_id)
    if not u:
        return {'id': unit_id, 'label': unit_id, 'colloquial': []}
    return {'id': u['id'], 'label': u['label'], 'colloquial': u.get('colloquial', [])}


def _resolve_items(items):
    return [
        {
            'name': item['name'],
            'brands': item.get('brands', []),
            'units': [_resolve_unit(u) for u in item.get('units', [])],
            'stock_tracking': item.get('stock_tracking', 'tracked'),
        }
        for item in items
    ]


def get_taxonomy(business_type_id: str):
    """
    Resolved taxonomy for one business type, ready for the onboarding
    category picker and the reconciliation queue's "pick from taxonomy"
    flow: category -> (subcategories ->) items -> brands/units, with
    every id already turned into a display name.

    Returns None if no template exists yet for this type (declared but
    not built — e.g. clothing_store's school_uniforms/mitumba niches).
    """
    try:
        template = _template(business_type_id)
    except FileNotFoundError:
        return None

    categories_out = []
    for cat in template.get('categories', []):
        cat_id = cat['category_id']
        cat_meta = _categories_by_id().get(cat_id, {})
        entry = {
            'category_id': cat_id,
            'name': cat_meta.get('name', cat_id),
        }
        if 'subcategories' in cat:
            entry['subcategories'] = [
                {
                    'subcategory_id': sub['subcategory_id'],
                    'name': _subcategories_by_id().get(sub['subcategory_id'], {}).get('name', sub['subcategory_id']),
                    'items': _resolve_items(sub.get('items', [])),
                }
                for sub in cat['subcategories']
            ]
        else:
            entry['items'] = _resolve_items(cat.get('items', []))
        categories_out.append(entry)

    result = {
        'business_type_id': template['business_type_id'],
        'kind': template.get('kind', 'goods'),
        'categories': categories_out,
    }

    # salon_barbershop-style service templates carry a retail_addon block
    # for the physical goods they also sell (see knowledge/README.md) —
    # a single category object (own category_id + items), NOT a
    # `categories` list like the main taxonomy — resolved the same way
    # but kept in its own key so the frontend can render it as a distinct
    # "you might also sell" section rather than mixing it into services.
    if 'retail_addon' in template:
        addon = template['retail_addon']
        addon_cat_id = addon.get('category_id')
        result['retail_addon'] = {
            'category_id': addon_cat_id,
            'name': _categories_by_id().get(addon_cat_id, {}).get('name', addon_cat_id),
            'items': _resolve_items(addon.get('items', [])),
        }

    return result


def get_category_meta(category_id: str):
    return _categories_by_id().get(category_id)


def find_category_brands_and_names(category_id: str):
    """
    Every known item name + brand under a category, across whichever
    template(s) reference it — used for within-business suggestions
    (Build Plan v3 §2.3): once a business has 2+ items tagged with this
    taxonomy category, these are the "other common brands/names" offered
    as tap-to-accept suggestions.
    """
    names = set()
    brands = set()

    def _collect(items):
        for item in items:
            names.add(item['name'])
            for b in item.get('brands', []):
                brands.add(b)

    for bt in _business_types():
        try:
            template = _template(bt['id'])
        except FileNotFoundError:
            continue
        for cat in template.get('categories', []):
            if cat['category_id'] != category_id:
                continue
            if 'subcategories' in cat:
                for sub in cat['subcategories']:
                    _collect(sub.get('items', []))
            else:
                _collect(cat.get('items', []))
        addon = template.get('retail_addon')
        if addon and addon.get('category_id') == category_id:
            _collect(addon.get('items', []))

    return sorted(names), sorted(brands)
