import { kindStyle } from '../place'

/** Ảnh Place; chưa có photo_url thì ô màu theo loại (ảnh thật về cùng mốc dữ liệu 15/10). */
export default function PlaceThumb({ kind, photo, className = 'size-12 rounded-lg text-2xl' }: {
  kind: string; photo?: string | null; className?: string
}) {
  if (photo) return <img src={photo} alt="" className={`${className} object-cover`} />
  return (
    <div aria-hidden className={`${className} grid shrink-0 place-items-center bg-linear-to-br ${kindStyle(kind).className}`}>
      {kindStyle(kind).icon}
    </div>
  )
}
