import { useLayoutEffect, useSyncExternalStore } from 'react'
import { portalEnglish, portalEnglishFragments } from './portalEnglish'

export type PortalLocale = 'vi' | 'en'
const storageKey = 'localexplorerai.portal.locale'
const eventName = 'portal-locale-change'
const sourceText = new WeakMap<Text, { original: string; rendered: string }>()
const sourceAttributes = new WeakMap<Element, Map<string, { original: string; rendered: string }>>()
const translatedAttributes = ['placeholder', 'title', 'aria-label', 'alt'] as const

function currentLocale(): PortalLocale {
  try {
    const requested = new URLSearchParams(location.search).get('lang')
    if (requested === 'vi' || requested === 'en') return requested
    const saved = localStorage.getItem(storageKey)
    if (saved === 'vi' || saved === 'en') return saved
    const siteLocale = localStorage.getItem('locale')
    if (siteLocale === 'vi' || siteLocale === 'en') return siteLocale
  } catch { /* Storage may be disabled. */ }
  return navigator.language.toLowerCase().startsWith('en') ? 'en' : 'vi'
}

function subscribe(listener: () => void) {
  window.addEventListener(eventName, listener)
  return () => window.removeEventListener(eventName, listener)
}

export function usePortalLocale() {
  return useSyncExternalStore(subscribe, currentLocale)
}

function setPortalLocale(locale: PortalLocale) {
  try { localStorage.setItem(storageKey, locale) } catch { /* Storage may be disabled. */ }
  const url = new URL(window.location.href)
  if (url.searchParams.has('lang')) {
    url.searchParams.delete('lang')
    window.history.replaceState(window.history.state, '', url)
  }
  window.dispatchEvent(new Event(eventName))
}

function translate(value: string): string {
  const normalized = value.replace(/\s+/g, ' ').trim()
  let english = portalEnglish[normalized]
  if (!english && /[À-ỹđĐ]/u.test(normalized)) {
    let updated = normalized
    for (const [vi, en] of portalEnglishFragments) {
      if (updated.includes(vi)) updated = updated.replaceAll(vi, en)
    }
    if (updated !== normalized) english = updated
  }
  if (!english) return value
  const leading = value.match(/^\s*/)?.[0] ?? ''
  const trailing = value.match(/\s*$/)?.[0] ?? ''
  return `${leading}${english}${trailing}`
}

function renderText(node: Text, locale: PortalLocale) {
  if (node.parentElement?.closest('script, style, [contenteditable="true"], [data-portal-no-translate]')) return
  const value = node.nodeValue ?? ''
  const previous = sourceText.get(node)
  const original = previous && (value === previous.original || value === previous.rendered) ? previous.original : value
  const rendered = locale === 'en' ? translate(original) : original
  sourceText.set(node, { original, rendered })
  if (value !== rendered) node.nodeValue = rendered
}

function renderAttributes(element: Element, locale: PortalLocale) {
  if (element.closest('[data-portal-no-translate]')) return
  const records = sourceAttributes.get(element) ?? new Map<string, { original: string; rendered: string }>()
  for (const name of translatedAttributes) {
    const value = element.getAttribute(name)
    if (value === null) continue
    const previous = records.get(name)
    const original = previous && (value === previous.original || value === previous.rendered) ? previous.original : value
    const rendered = locale === 'en' ? translate(original) : original
    records.set(name, { original, rendered })
    if (value !== rendered) element.setAttribute(name, rendered)
  }
  sourceAttributes.set(element, records)
}

function renderTree(root: Node, locale: PortalLocale) {
  if (root.nodeType === Node.TEXT_NODE) { renderText(root as Text, locale); return }
  if (root.nodeType !== Node.ELEMENT_NODE) return
  const element = root as Element
  renderAttributes(element, locale)
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT)
  while (walker.nextNode()) {
    const node = walker.currentNode
    if (node.nodeType === Node.TEXT_NODE) renderText(node as Text, locale)
    else renderAttributes(node as Element, locale)
  }
}

/** Localizes visible Portal UI without changing values submitted to the API. */
export function usePortalLocaleBridge() {
  const locale = usePortalLocale()
  useLayoutEffect(() => {
    document.documentElement.lang = locale
    try { localStorage.setItem(storageKey, locale) } catch { /* Storage may be disabled. */ }
    renderTree(document.body, locale)
    const observer = new MutationObserver((changes) => {
      for (const change of changes) {
        if (change.type === 'characterData') renderText(change.target as Text, locale)
        else if (change.type === 'attributes') renderAttributes(change.target as Element, locale)
        else for (const node of change.addedNodes) renderTree(node, locale)
      }
    })
    observer.observe(document.body, { subtree: true, childList: true, characterData: true,
      attributes: true, attributeFilter: [...translatedAttributes] })
    return () => observer.disconnect()
  }, [locale])
}

export function PortalLanguageSwitcher() {
  const locale = usePortalLocale()
  return <div className="flex rounded-lg border border-slate-200 p-0.5 text-xs font-semibold" role="group" aria-label="Language">
    <button type="button" data-portal-no-translate aria-pressed={locale === 'vi'} onClick={() => setPortalLocale('vi')}
      className={`rounded-md px-2 py-1 ${locale === 'vi' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>VI</button>
    <button type="button" data-portal-no-translate aria-pressed={locale === 'en'} onClick={() => setPortalLocale('en')}
      className={`rounded-md px-2 py-1 ${locale === 'en' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>EN</button>
  </div>
}