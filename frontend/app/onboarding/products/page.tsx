'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createProduct, importProductsCsv } from '@/lib/catalog'
import { fetchBusiness } from '@/lib/business'
import { fetchTaxonomy, fetchCategorySuggestions, taxonomyUnitToProductUnit } from '@/lib/knowledge'
import { apiErrorMessage, useAuthStore } from '@/lib/auth'
import { goToApp } from '@/lib/post-login'
import Deepfield from '@/components/deepfield'
import { COPY } from '@/lib/copy'
import type { Taxonomy, TaxonomyCategory, TaxonomyItem, CategorySuggestions } from '@/lib/types'

interface DraftProduct {
  name: string
  selling_price: string
  current_stock: string
}

const EMPTY_ROW: DraftProduct = { name: '', selling_price: '', current_stock: '' }

// A picked taxonomy/suggestion item awaiting a price before it becomes a
// real product. Keyed by `${categoryId}::${name}` so the same item name
// appearing under two different categories (rare, but the JSON doesn't
// forbid it) doesn't collide.
interface TaxonomySelection {
  name: string
  unit: string
  price: string
  categoryId: string
  // The taxonomy category's real display name (e.g. "Spirits & Wines"),
  // not the onboarding screen's titleOverride label — this is what gets
  // sent to the backend to find-or-create a real Category row, which is
  // what lets Stock and Sell mode group products sensibly afterward.
  categoryName: string
}

export default function ProductOnboardingPage() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const [mode, setMode] = useState<'taxonomy' | 'manual' | 'csv'>('manual')
  const [rows, setRows] = useState<DraftProduct[]>([{ ...EMPTY_ROW }])
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [csvResult, setCsvResult] = useState<{ imported: number; skipped: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Taxonomy tab state ──────────────────────────────────────────────────
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null)
  const [loadingTaxonomy, setLoadingTaxonomy] = useState(true)
  const [taxonomyError, setTaxonomyError] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Record<string, TaxonomySelection>>({})
  const [suggestions, setSuggestions] = useState<Record<string, CategorySuggestions>>({})
  const fetchingSuggestions = useRef<Set<string>>(new Set())

  useEffect(() => {
    fetchBusiness()
      .then((business) => {
        if (!business.taxonomy_type_id) {
          setLoadingTaxonomy(false)
          return
        }
        return fetchTaxonomy(business.taxonomy_type_id).then((t) => {
          if (!t) return
          setTaxonomy(t)
          setMode('taxonomy')
          // Open the first category by default so the tab doesn't look
          // empty on first render — the rest stay collapsed to avoid
          // dumping the entire taxonomy on screen at once.
          if (t.categories[0]) setExpanded(new Set([t.categories[0].category_id]))
        })
      })
      .catch(() => setTaxonomyError(true))
      .finally(() => setLoadingTaxonomy(false))
  }, [])

  const selectedCount = Object.keys(selected).length
  const selectedList = Object.entries(selected)

  function selectedCountForCategory(categoryId: string) {
    return selectedList.filter(([, s]) => s.categoryId === categoryId).length
  }

  function toggleCategory(categoryId: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(categoryId)) next.delete(categoryId)
      else next.add(categoryId)
      return next
    })
  }

  function toggleItem(categoryId: string, categoryName: string, item: TaxonomyItem) {
    const key = `${categoryId}::${item.name}`
    setSelected((prev) => {
      const next = { ...prev }
      if (next[key]) {
        delete next[key]
      } else {
        next[key] = {
          name: item.name,
          unit: taxonomyUnitToProductUnit(item.units[0]?.id ?? 'piece'),
          price: '', categoryId, categoryName,
        }
      }
      return next
    })
  }

  function addSuggestion(categoryId: string, categoryName: string, name: string) {
    const key = `${categoryId}::${name}`
    setSelected((prev) => (
      prev[key] ? prev : { ...prev, [key]: { name, unit: 'piece', price: '', categoryId, categoryName } }
    ))
  }

  function setSelectionPrice(key: string, price: string) {
    setSelected((prev) => ({ ...prev, [key]: { ...prev[key], price } }))
  }

  // Fetch suggestions for a category once it has 2+ picks — a light nudge
  // toward "other common items here" (Phase 9.5 scope), not shown before
  // the owner's shown some interest in that category.
  useEffect(() => {
    if (!taxonomy) return
    for (const category of taxonomy.categories) {
      const count = selectedCountForCategory(category.category_id)
      if (
        count >= 2 &&
        !suggestions[category.category_id] &&
        !fetchingSuggestions.current.has(category.category_id)
      ) {
        fetchingSuggestions.current.add(category.category_id)
        fetchCategorySuggestions(category.category_id)
          .then((s) => {
            if (!s) return
            setSuggestions((prev) => ({ ...prev, [category.category_id]: s }))
          })
          .catch(() => {/* non-critical — just skip the nudge for this category */})
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, taxonomy])

  const allSelectedPriced = selectedList.every(([, s]) => s.price.trim())

  async function handleSaveTaxonomy() {
    if (selectedCount === 0) {
      await goToApp(router, user)
      return
    }
    if (!allSelectedPriced) {
      setError(COPY.ONBOARD_TAXONOMY_PRICE_HINT)
      return
    }
    setIsSaving(true)
    setError('')
    try {
      for (const [, s] of selectedList) {
        await createProduct({
          name: s.name,
          selling_price: s.price.trim(),
          unit: s.unit,
          current_stock: '0',
          category_name: s.categoryName,
          created_via: 'taxonomy',
        })
      }
      await goToApp(router, user)
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ONBOARD_SAVE_ERROR))
      setIsSaving(false)
    }
  }

  function updateRow(index: number, field: keyof DraftProduct, value: string) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)))
  }

  function addRow() {
    if (rows.length >= 5) return
    setRows((prev) => [...prev, { ...EMPTY_ROW }])
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  const validRows = rows.filter((r) => r.name.trim() && r.selling_price.trim())

  async function handleSaveManual() {
    if (validRows.length === 0) {
      await goToApp(router, user)
      return
    }
    setIsSaving(true)
    setError('')
    try {
      for (const row of validRows) {
        await createProduct({
          name: row.name.trim(),
          selling_price: row.selling_price.trim(),
          current_stock: row.current_stock.trim() || '0',
        })
      }
      await goToApp(router, user)
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ONBOARD_SAVE_ERROR))
      setIsSaving(false)
    }
  }

  async function handleCsvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setIsSaving(true)
    setError('')
    setCsvResult(null)
    try {
      const result = await importProductsCsv(file)
      setCsvResult({ imported: result.imported, skipped: result.skipped })
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ONBOARD_CSV_UPLOAD_ERROR))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.25} />
      <div className="card" style={{ width: '100%', maxWidth: 480 }}>
        <h2 style={{ marginBottom: 'var(--sp-2)' }}>{COPY.ONBOARD_TITLE}</h2>
        <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-5)' }}>
          {COPY.ONBOARD_SUBTITLE}
        </p>

        <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-5)', flexWrap: 'wrap' }}>
          {taxonomy && taxonomy.categories.length > 0 && (
            <button type="button" className={mode === 'taxonomy' ? 'btn-primary' : 'btn-secondary'} onClick={() => setMode('taxonomy')}>
              {COPY.ONBOARD_TAXONOMY_TAB}
            </button>
          )}
          <button type="button" className={mode === 'manual' ? 'btn-primary' : 'btn-secondary'} onClick={() => setMode('manual')}>
            {COPY.ONBOARD_MANUAL_TAB}
          </button>
          <button type="button" className={mode === 'csv' ? 'btn-primary' : 'btn-secondary'} onClick={() => setMode('csv')}>
            {COPY.ONBOARD_CSV_TAB}
          </button>
        </div>

        {mode === 'taxonomy' && (
          <div>
            {loadingTaxonomy ? (
              <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)' }}>{COPY.ONBOARD_TAXONOMY_LOADING}</p>
            ) : taxonomyError ? (
              <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)' }}>{COPY.ONBOARD_TAXONOMY_LOAD_ERROR}</p>
            ) : !taxonomy || taxonomy.categories.length === 0 ? (
              <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)' }}>{COPY.ONBOARD_TAXONOMY_EMPTY}</p>
            ) : (
              <>
                <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-4)' }}>
                  {COPY.ONBOARD_TAXONOMY_INTRO}
                </p>

                <div style={{ maxHeight: 380, overflowY: 'auto', marginBottom: 'var(--sp-4)' }}>
                  {taxonomy.categories.map((cat) => (
                    <CategoryBlock
                      key={cat.category_id}
                      category={cat}
                      isExpanded={expanded.has(cat.category_id)}
                      onToggle={() => toggleCategory(cat.category_id)}
                      selected={selected}
                      onToggleItem={(item) => toggleItem(cat.category_id, cat.name, item)}
                      suggestions={suggestions[cat.category_id]}
                      onAddSuggestion={(name) => addSuggestion(cat.category_id, cat.name, name)}
                      onPriceChange={setSelectionPrice}
                    />
                  ))}

                  {taxonomy.retail_addon && (
                    <CategoryBlock
                      key={taxonomy.retail_addon.category_id}
                      category={taxonomy.retail_addon}
                      titleOverride={COPY.ONBOARD_TAXONOMY_RETAIL_ADDON_TITLE}
                      isExpanded={expanded.has(taxonomy.retail_addon.category_id)}
                      onToggle={() => toggleCategory(taxonomy.retail_addon!.category_id)}
                      selected={selected}
                      onToggleItem={(item) => toggleItem(taxonomy.retail_addon!.category_id, taxonomy.retail_addon!.name, item)}
                      suggestions={suggestions[taxonomy.retail_addon.category_id]}
                      onAddSuggestion={(name) => addSuggestion(taxonomy.retail_addon!.category_id, taxonomy.retail_addon!.name, name)}
                      onPriceChange={setSelectionPrice}
                    />
                  )}
                </div>

                {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

                <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                  <button type="button" className="btn-ghost" onClick={() => goToApp(router, user)} disabled={isSaving}>
                    {COPY.ONBOARD_SKIP}
                  </button>
                  <button type="button" className="btn-primary" onClick={handleSaveTaxonomy} disabled={isSaving} style={{ flex: 1, justifyContent: 'center' }}>
                    {isSaving ? COPY.ONBOARD_SAVING : COPY.ONBOARD_TAXONOMY_ADD_BTN.replace('{count}', String(selectedCount))}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {mode === 'manual' && (
          <>
            {rows.map((row, i) => (
              <div key={i} className="card-stat" style={{ marginBottom: 'var(--sp-3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-2)' }}>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.ONBOARD_PRODUCT_LABEL.replace('{n}', String(i + 1))}</span>
                  {rows.length > 1 && (
                    <button type="button" className="btn-ghost" onClick={() => removeRow(i)} style={{ padding: 0, fontSize: 'var(--fs-xs)' }}>
                      {COPY.ONBOARD_REMOVE}
                    </button>
                  )}
                </div>
                <input
                  className="input"
                  placeholder={COPY.ONBOARD_NAME_PLACEHOLDER}
                  value={row.name}
                  onChange={(e) => updateRow(i, 'name', e.target.value)}
                  style={{ marginBottom: 'var(--sp-2)' }}
                />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
                  <input
                    className="input"
                    placeholder={COPY.ONBOARD_PRICE_PLACEHOLDER}
                    inputMode="decimal"
                    value={row.selling_price}
                    onChange={(e) => updateRow(i, 'selling_price', e.target.value)}
                  />
                  <input
                    className="input"
                    placeholder={COPY.ONBOARD_QTY_PLACEHOLDER}
                    inputMode="numeric"
                    value={row.current_stock}
                    onChange={(e) => updateRow(i, 'current_stock', e.target.value)}
                  />
                </div>
              </div>
            ))}

            {rows.length < 5 && (
              <button type="button" className="btn-secondary" onClick={addRow} style={{ width: '100%', justifyContent: 'center', marginBottom: 'var(--sp-5)' }}>
                {COPY.ONBOARD_ADD_ANOTHER}
              </button>
            )}

            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

            <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-4)' }}>
              <button type="button" className="btn-ghost" onClick={() => goToApp(router, user)} disabled={isSaving}>
                {COPY.ONBOARD_SKIP}
              </button>
              <button type="button" className="btn-primary" onClick={handleSaveManual} disabled={isSaving} style={{ flex: 1, justifyContent: 'center' }}>
                {isSaving ? COPY.ONBOARD_SAVING : COPY.ONBOARD_SAVE_CONTINUE.replace('{count}', String(validRows.length))}
              </button>
            </div>
          </>
        )}

        {mode === 'csv' && (
          <div>
            <div className="card-terminal" style={{ marginBottom: 'var(--sp-4)' }}>
              {COPY.ONBOARD_CSV_REQUIRED_COLS} <strong>name, selling_price</strong><br />
              {COPY.ONBOARD_CSV_OPTIONAL_COLS}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleCsvUpload}
              style={{ display: 'none' }}
            />
            <button
              type="button"
              className="btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={isSaving}
              style={{ width: '100%', justifyContent: 'center', marginBottom: 'var(--sp-4)' }}
            >
              {isSaving ? COPY.ONBOARD_CSV_UPLOADING : COPY.ONBOARD_CSV_CHOOSE_FILE}
            </button>

            {csvResult && (
              <div className="card-accent" style={{ marginBottom: 'var(--sp-4)' }}>
                <p>{COPY.ONBOARD_CSV_IMPORTED.replace('{count}', String(csvResult.imported))}</p>
                {csvResult.skipped > 0 && <p style={{ color: 'var(--color-muted)' }}>{COPY.ONBOARD_CSV_SKIPPED.replace('{count}', String(csvResult.skipped))}</p>}
              </div>
            )}

            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button type="button" className="btn-ghost" onClick={() => goToApp(router, user)}>
                {COPY.ONBOARD_SKIP}
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => goToApp(router, user)}
                disabled={!csvResult}
                style={{ flex: 1, justifyContent: 'center' }}
              >
                {COPY.ONBOARD_CONTINUE_DASHBOARD}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}

// ── Taxonomy picker helpers ─────────────────────────────────────────────────

function CategoryBlock({
  category, titleOverride, isExpanded, onToggle, selected, onToggleItem, suggestions, onAddSuggestion, onPriceChange,
}: {
  category: TaxonomyCategory
  titleOverride?: string
  isExpanded: boolean
  onToggle: () => void
  selected: Record<string, TaxonomySelection>
  onToggleItem: (item: TaxonomyItem) => void
  suggestions?: CategorySuggestions
  onAddSuggestion: (name: string) => void
  onPriceChange: (key: string, price: string) => void
}) {
  const categoryId = category.category_id
  const selectedCount = Object.values(selected).filter((s) => s.categoryId === categoryId).length

  // A category has either subcategories (each holding its own items) or
  // items directly — never both. Flatten to a uniform list of
  // (groupLabel | null, items) pairs so the render below doesn't need to
  // branch on which shape it got.
  const groups: { label: string | null; items: TaxonomyItem[] }[] = category.subcategories
    ? category.subcategories.map((sub) => ({ label: sub.name, items: sub.items }))
    : [{ label: null, items: category.items ?? [] }]

  const suggestedNames = (suggestions?.suggested_names ?? []).filter(
    (name) => !selected[`${categoryId}::${name}`]
  )

  return (
    <div className="card-stat" style={{ marginBottom: 'var(--sp-2)' }}>
      <button
        type="button"
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
          color: 'var(--color-text)', fontSize: 'var(--fs-sm)', fontWeight: 600,
        }}
      >
        <span>{titleOverride ?? category.name}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
          {selectedCount > 0 && (
            <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)' }}>
              {COPY.ONBOARD_TAXONOMY_SELECTED_COUNT.replace('{count}', String(selectedCount))}
            </span>
          )}
          <span style={{ color: 'var(--color-muted)' }}>{isExpanded ? '−' : '+'}</span>
        </span>
      </button>

      {isExpanded && (
        <div style={{ marginTop: 'var(--sp-3)' }}>
          {groups.map((group, gi) => (
            <div key={gi} style={{ marginBottom: 'var(--sp-3)' }}>
              {group.label && (
                <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                  {group.label}
                </div>
              )}
              {group.items.map((item) => (
                <ItemRow
                  key={item.name}
                  item={item}
                  selection={selected[`${categoryId}::${item.name}`]}
                  onToggle={() => onToggleItem(item)}
                  onPriceChange={(price) => onPriceChange(`${categoryId}::${item.name}`, price)}
                />
              ))}
            </div>
          ))}

          {suggestedNames.length > 0 && (
            <div style={{ marginTop: 'var(--sp-2)' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                {COPY.ONBOARD_TAXONOMY_SUGGESTIONS_LABEL}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)' }}>
                {suggestedNames.map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => onAddSuggestion(name)}
                    className="btn-secondary"
                    style={{ fontSize: 'var(--fs-xs)', padding: 'var(--sp-1) var(--sp-3)' }}
                  >
                    + {name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ItemRow({ item, selection, onToggle, onPriceChange }: {
  item: TaxonomyItem
  selection: TaxonomySelection | undefined
  onToggle: () => void
  onPriceChange: (price: string) => void
}) {
  const isSelected = !!selection
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', padding: 'var(--sp-1) 0' }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', flex: 1, cursor: 'pointer', fontSize: 'var(--fs-sm)' }}>
        <input type="checkbox" checked={isSelected} onChange={onToggle} />
        {item.name}
      </label>
      {isSelected && (
        <input
          className="input"
          type="number" min="0" step="any" inputMode="decimal"
          placeholder={COPY.ONBOARD_TAXONOMY_PRICE_PLACEHOLDER}
          value={selection.price}
          onChange={(e) => onPriceChange(e.target.value)}
          style={{ width: 90, flexShrink: 0 }}
        />
      )}
    </div>
  )
}
