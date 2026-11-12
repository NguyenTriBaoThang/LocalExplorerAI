import type { PriceMode } from '../../lib/operatorApi'

export const vnd = (n: number) => `${Math.round(n).toLocaleString('vi-VN')}đ`
export const DESTINATION_LABEL: Record<string, string> = { cu_chi: 'Củ Chi', mekong: 'Mekong', can_gio: 'Cần Giờ', vung_tau: 'Vũng Tàu', city: 'TP.HCM' }
export const SEGMENT_LABEL: Record<string, string> = { family: 'Gia đình / nhóm bạn', corporate: 'Doanh nghiệp', school: 'Trường học' }
export const MODE_LABEL: Record<PriceMode, string> = { safe: 'An toàn', balanced: 'Cân bằng', max_profit: 'Tối đa lãi' }
export const MODE_HINT: Record<PriceMode, string> = {
  safe: 'Ưu tiên chốt được đơn (P ≥ 75%).', balanced: 'Gần lãi tối đa nhưng dễ chốt hơn.', max_profit: 'Lãi kỳ vọng cao nhất.',
}
export const STATUS_LABEL: Record<string, string> = {
  draft: 'Nháp', sent: 'Đã gửi', viewed: 'Khách đã xem', accepted: 'Khách chấp nhận', deposit_paid: 'Đã đặt cọc', won: 'Đã chốt', lost: 'Không chốt', expired: 'Hết hạn',
}
