/**
 * BizYangu — shared grouping helpers.
 */

/**
 * Groups any list of items with a category_name field into ordered
 * buckets — named categories alphabetically first, an "uncategorized"
 * bucket (category_name === null) last. Used by both Stock mode's
 * grouped list and Sell mode's category filter chips, so the two modes
 * agree on category ordering rather than each inventing its own.
 */
export function groupByCategory<T extends { category_name: string | null }>(
  items: T[]
): { categoryName: string | null; items: T[] }[] {
  const groups = new Map<string | null, T[]>()
  for (const item of items) {
    const key = item.category_name
    const bucket = groups.get(key)
    if (bucket) bucket.push(item)
    else groups.set(key, [item])
  }

  const entries = Array.from(groups.entries())
  entries.sort((a, b) => {
    if (a[0] === null) return 1
    if (b[0] === null) return -1
    return a[0].localeCompare(b[0])
  })

  return entries.map(([categoryName, items]) => ({ categoryName, items }))
}
