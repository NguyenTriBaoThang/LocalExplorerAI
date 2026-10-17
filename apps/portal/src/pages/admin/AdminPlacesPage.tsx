import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Clock, Eye, ImageOff, LayoutGrid, List, MapPin, Plus, Search, Star } from 'lucide-react'
import { Badge, Button, Card, cx, EmptyState, IconButton, Input, PageHeader, Pagination, Select, Spinner, StatusBadge, Tabs, useToast } from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { categoryLabel, DISTRICTS, PLACE_CATEGORIES } from '../../lib/catalog'
import type { AdminPlace, PlaceStatus } from '../../lib/types'

type StatusFilter = PlaceStatus | 'all'
const number = new Intl.NumberFormat('vi-VN')
const PAGE_SIZE = 24

export function AdminPlacesPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [places, setPlaces] = useState<AdminPlace[] | null>(null)
  const [status, setStatus] = useState<StatusFilter>('all')
  const [category, setCategory] = useState('')
  const [district, setDistrict] = useState('')
  const [query, setQuery] = useState('')
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const [offset, setOffset] = useState(0)
  useEffect(() => setOffset(0), [status, category, district, query])

  useEffect(() => { adminApi.places().then(setPlaces).catch((err) => { toast.error(errorMessage(err)); setPlaces([]) }) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const counts = useMemo(() => {
    const all = places ?? []
    return { all: all.length, verified: all.filter((p) => p.status === 'verified').length, pending: all.filter((p) => p.status === 'pending').length, draft: all.filter((p) => p.status === 'draft').length, hidden: all.filter((p) => p.status === 'hidden').length, simulated: all.filter((p) => p.status === 'simulated').length }
  }, [places])

  const rows = (places ?? []).filter((place) =>
    (status === 'all' || place.status === status) && (!category || place.category === category) && (!district || place.district === district)
    && (place.name + place.address).toLowerCase().includes(query.trim().toLowerCase()))
  const pageRows = rows.slice(offset, offset + PAGE_SIZE)

  return (
    <>
      <PageHeader title="Địa điểm & Danh lam thắng cảnh" description="Quản lý điểm đến hiển thị trên bản đồ, lịch trình và trang khám phá."
        actions={<><Button icon={Plus} onClick={() => navigate('/admin/places/new')}>Thêm địa điểm</Button></>} />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Tabs value={status} onChange={setStatus} items={[
          { value: 'all', label: 'Tất cả', count: counts.all }, { value: 'verified', label: 'Đang hiển thị', count: counts.verified },
          { value: 'pending', label: 'Chờ duyệt', count: counts.pending }, { value: 'draft', label: 'Nháp', count: counts.draft }, { value: 'hidden', label: 'Đã ẩn', count: counts.hidden },
          ...(counts.simulated ? [{ value: 'simulated' as const, label: 'Dữ liệu demo', count: counts.simulated }] : []),
        ]} />
        <div className="ml-auto flex rounded-lg bg-slate-100 p-1">
          <IconButton icon={LayoutGrid} label="Dạng lưới" onClick={() => setView('grid')} className={cx('h-7 w-7', view === 'grid' && 'bg-white text-slate-900 shadow-sm')} />
          <IconButton icon={List} label="Dạng bảng" onClick={() => setView('table')} className={cx('h-7 w-7', view === 'table' && 'bg-white text-slate-900 shadow-sm')} />
        </div>
      </div>
      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm tên, địa chỉ…" className="pl-9" />
        </div>
        <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-auto">
          <option value="">Mọi loại</option>
          {Object.entries(PLACE_CATEGORIES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </Select>
        <Select value={district} onChange={(e) => setDistrict(e.target.value)} className="w-auto">
          <option value="">Mọi quận/huyện</option>
          {DISTRICTS.map((item) => <option key={item}>{item}</option>)}
        </Select>
      </div>

      {!places ? <Spinner /> : rows.length === 0 ? (
        <Card><EmptyState icon={MapPin} title="Không có địa điểm phù hợp" action={<Button icon={Plus} onClick={() => navigate('/admin/places/new')}>Thêm địa điểm</Button>} /></Card>
      ) : view === 'grid' ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {pageRows.map((place) => (
            <Link key={place.id} to={`/admin/places/${place.id}`} className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card transition hover:-translate-y-0.5 hover:shadow-pop">
              <div className="relative h-40 bg-slate-100">
                {place.image_urls[0]
                  ? <img src={place.image_urls[0]} alt="" className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]" />
                  : <div className="flex h-full items-center justify-center text-slate-300"><ImageOff className="h-8 w-8" /></div>}
                <div className="absolute left-3 top-3 flex gap-1.5">
                  <StatusBadge status={place.status} />
                  {place.is_landmark && <Badge tone="amber"><Star className="h-3 w-3" /> Danh thắng</Badge>}
                </div>
              </div>
              <div className="p-4">
                <p className="font-semibold text-slate-900">{place.name}</p>
                <p className="mt-0.5 truncate text-sm text-slate-500">{categoryLabel(place.category)}{place.district && ` · ${place.district}`}</p>
                <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1"><Eye className="h-3.5 w-3.5" />{number.format(place.views_30d)} / 30 ngày</span>
                  <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{place.opening_hours || '—'}</span>
                </div>
              </div>
            </Link>
          ))}
          {rows.length > PAGE_SIZE && <div className="sm:col-span-2 xl:col-span-3"><Card><Pagination offset={offset} limit={PAGE_SIZE} total={rows.length} onChange={setOffset} /></Card></div>}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3 font-medium">Địa điểm</th><th className="px-5 py-3 font-medium">Loại</th><th className="px-5 py-3 font-medium">Quận/Huyện</th>
                  <th className="px-5 py-3 font-medium">Trải nghiệm</th><th className="px-5 py-3 font-medium">Lượt xem 30 ngày</th><th className="px-5 py-3 font-medium">Cập nhật</th><th className="px-5 py-3 font-medium">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pageRows.map((place) => (
                  <tr key={place.id} onClick={() => navigate(`/admin/places/${place.id}`)} className="cursor-pointer hover:bg-slate-50/60">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-14 shrink-0 overflow-hidden rounded-md bg-slate-100">{place.image_urls[0] && <img src={place.image_urls[0]} alt="" className="h-full w-full object-cover" />}</div>
                        <div className="min-w-0"><p className="truncate font-medium text-slate-900">{place.name}</p><p className="truncate text-xs text-slate-500">{place.address}</p></div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{categoryLabel(place.category)}</td>
                    <td className="px-5 py-3 text-slate-600">{place.district ?? '—'}</td>
                    <td className="px-5 py-3 text-slate-600">{place.experience_count}</td>
                    <td className="px-5 py-3 text-slate-600">{number.format(place.views_30d)}</td>
                    <td className="whitespace-nowrap px-5 py-3 text-slate-600">{formatDate(place.updated_at)}</td>
                    <td className="px-5 py-3"><StatusBadge status={place.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination offset={offset} limit={PAGE_SIZE} total={rows.length} onChange={setOffset} />
        </Card>
      )}
    </>
  )
}
