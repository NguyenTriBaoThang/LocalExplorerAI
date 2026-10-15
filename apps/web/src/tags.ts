/** Display names for the intent tags the catalogue uses, so Vietnamese and English pages do not show raw keys. */
const TAGS: Record<string, [vi: string, en: string]> = {
  handicraft: ['Thủ công', 'Handicraft'],
  hands_on: ['Tự tay làm', 'Hands-on'],
  local_life: ['Đời sống địa phương', 'Local life'],
  relaxation: ['Thư giãn', 'Relaxation'],
  food: ['Ẩm thực', 'Food'],
  culture: ['Văn hóa', 'Culture'],
  nature: ['Thiên nhiên', 'Nature'],
  family: ['Gia đình', 'Family'],
  weekend: ['Cuối tuần', 'Weekend'],
}

export function tagLabel(tag: string, locale: string): string {
  const entry = TAGS[tag]
  if (entry) return entry[locale === 'en' ? 1 : 0]
  const plain = tag.replaceAll('_', ' ')
  return plain.charAt(0).toUpperCase() + plain.slice(1)
}
