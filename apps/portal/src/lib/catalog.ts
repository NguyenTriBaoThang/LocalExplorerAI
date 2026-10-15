/** Fixed vocabularies used by the place forms and filters. Stored values are the keys. */
export const PLACE_CATEGORIES: Record<string, string> = {
  landmark: 'Danh lam thắng cảnh', history: 'Di tích lịch sử', museum: 'Bảo tàng', market: 'Chợ', religious: 'Tôn giáo',
  park: 'Công viên', food: 'Ẩm thực', craft: 'Làng nghề / Xưởng', other: 'Khác',
}

export const DISTRICTS = [
  'Quận 1', 'Quận 3', 'Quận 4', 'Quận 5', 'Quận 6', 'Quận 7', 'Quận 8', 'Quận 10', 'Quận 11', 'Quận 12',
  'Bình Thạnh', 'Phú Nhuận', 'Gò Vấp', 'Tân Bình', 'Tân Phú', 'Bình Tân', 'Thủ Đức', 'Bình Chánh', 'Hóc Môn', 'Nhà Bè', 'Củ Chi', 'Cần Giờ',
]

export const categoryLabel = (key: string) => PLACE_CATEGORIES[key] ?? key
