import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, ImagePlus, Link2, MapPin, Save, Send, Star, Trash2 } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, cx, Field, IconButton, Input, Select, Spinner, StatusBadge, Textarea, Toggle, useToast } from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { DISTRICTS, PLACE_CATEGORIES } from '../../lib/catalog'
import { formatDateTime } from '../../lib/format'
import type { AdminPlace, PlaceDraft } from '../../lib/types'

const EMPTY: PlaceDraft = {
  name: '', category: 'landmark', district: 'Quận 1', address: '', latitude: 10.7769, longitude: 106.7009, description: '', image_urls: [],
  opening_hours: '', ticket_info: '', tags: [], is_landmark: true, source_url: '',
}

function toDraft(place: AdminPlace): PlaceDraft {
  const { name, category, district, address, latitude, longitude, description, image_urls, opening_hours, ticket_info, tags, is_landmark, source_url } = place
  return { name, category, district, address, latitude, longitude, description, image_urls, opening_hours: opening_hours ?? '', ticket_info: ticket_info ?? '', tags, is_landmark, source_url: source_url ?? '' }
}

export function AdminPlaceEditorPage() {
  const { placeId } = useParams()
  const isNew = !placeId || placeId === 'new'
  const navigate = useNavigate()
  const toast = useToast()
  const [draft, setDraft] = useState<PlaceDraft | null>(isNew ? EMPTY : null)
  const [place, setPlace] = useState<AdminPlace | null>(null)
  const [imageUrl, setImageUrl] = useState('')
  const [tags, setTags] = useState('')
  const [busy, setBusy] = useState<'save' | 'publish' | 'hide' | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isNew) return
    adminApi.place(placeId).then((item) => { setPlace(item); setDraft(toDraft(item)); setTags(item.tags.join(', ')) })
      .catch(() => navigate('/admin/places', { replace: true }))
  }, [isNew, placeId, navigate])

  if (!draft) return <Spinner />
  const set = <K extends keyof PlaceDraft>(key: K, value: PlaceDraft[K]) => setDraft({ ...draft, [key]: value })
  const payload = (): PlaceDraft => ({
    ...draft, district: draft.district || null, opening_hours: draft.opening_hours?.trim() || null, ticket_info: draft.ticket_info?.trim() || null,
    source_url: draft.source_url?.trim() || null, tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
  })

  const run = async (kind: 'save' | 'publish' | 'hide') => {
    setBusy(kind)
    setError('')
    try {
      let saved = isNew ? await adminApi.createPlace(payload(), kind === 'publish') : await adminApi.updatePlace(place!.id, payload())
      if (!isNew && kind === 'publish' && saved.status !== 'verified') saved = await adminApi.setPlaceStatus(saved.id, 'publish', payload().source_url)
      if (kind === 'hide') saved = await adminApi.setPlaceStatus(saved.id, 'hide')
      toast.success(kind === 'publish' ? 'Đã xuất bản địa điểm.' : kind === 'hide' ? 'Đã ẩn địa điểm.' : 'Đã lưu địa điểm.')
      if (isNew) navigate(`/admin/places/${saved.id}`, { replace: true })
      setPlace(saved)
      setDraft(toDraft(saved))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }
  const submit = (event: FormEvent) => { event.preventDefault(); void run('save') }
  const addImage = () => { if (imageUrl.trim()) { set('image_urls', [...draft.image_urls, imageUrl.trim()]); setImageUrl('') } }
  const mapSrc = `https://www.openstreetmap.org/export/embed.html?bbox=${draft.longitude - 0.006},${draft.latitude - 0.004},${draft.longitude + 0.006},${draft.latitude + 0.004}&layer=mapnik&marker=${draft.latitude},${draft.longitude}`

  return (
    <form onSubmit={submit}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link to="/admin/places" className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"><ArrowLeft className="h-5 w-5" /></Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{isNew ? 'Thêm địa điểm' : place?.name}</h1>
              {place && <StatusBadge status={place.status} />}
            </div>
            {place && <p className="text-sm text-slate-500">Cập nhật {formatDateTime(place.updated_at)} · phiên bản dữ liệu {place.data_revision}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          {place && place.status !== 'hidden' && <Button type="button" variant="secondary" icon={EyeOff} loading={busy === 'hide'} onClick={() => run('hide')}>Ẩn</Button>}
          <Button type="submit" variant="secondary" icon={Save} loading={busy === 'save'}>{place?.status === 'verified' ? 'Lưu thay đổi' : 'Lưu nháp'}</Button>
          {place?.status !== 'verified' && (
            <Button type="button" icon={Send} loading={busy === 'publish'} disabled={!draft.name || !draft.address || !draft.source_url} onClick={() => run('publish')}>Xuất bản</Button>
          )}
        </div>
      </div>
      {error && <div className="mb-6"><Alert tone="red">{error}</Alert></div>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Thông tin chung" />
            <div className="grid gap-5 p-5 sm:grid-cols-2">
              <Field label="Tên địa điểm" required className="sm:col-span-2"><Input value={draft.name} onChange={(e) => set('name', e.target.value)} required minLength={2} placeholder="VD: Chợ Bến Thành" /></Field>
              <Field label="Loại địa điểm" required>
                <Select value={draft.category} onChange={(e) => set('category', e.target.value)}>
                  {Object.entries(PLACE_CATEGORIES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                  {!PLACE_CATEGORIES[draft.category] && <option value={draft.category}>{draft.category}</option>}
                </Select>
              </Field>
              <Field label="Quận/Huyện">
                <Select value={draft.district ?? ''} onChange={(e) => set('district', e.target.value)}>
                  <option value="">— Chưa chọn —</option>
                  {DISTRICTS.map((d) => <option key={d}>{d}</option>)}
                  {draft.district && !DISTRICTS.includes(draft.district) && <option>{draft.district}</option>}
                </Select>
              </Field>
              <Field label="Mô tả" className="sm:col-span-2" hint="Hiển thị trên trang chi tiết và trong gợi ý lịch trình.">
                <Textarea value={draft.description} onChange={(e) => set('description', e.target.value)} className="min-h-[140px]" />
              </Field>
              <Field label="Thẻ" hint="Phân cách bằng dấu phẩy" className="sm:col-span-2"><Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="lịch sử, kiến trúc, ngoài trời" /></Field>
              <div className="sm:col-span-2"><Toggle checked={draft.is_landmark} onChange={(v) => set('is_landmark', v)} label="Đánh dấu là danh lam thắng cảnh nổi bật" /></div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Hình ảnh" description="Ảnh đầu tiên là ảnh bìa. Dùng đường dẫn HTTPS hoặc đường dẫn trong website (/images/…)." />
            <div className="space-y-4 p-5">
              {draft.image_urls.length > 0 && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {draft.image_urls.map((url, index) => (
                    <div key={url + index} className={cx('group relative overflow-hidden rounded-lg border', index === 0 ? 'border-brand-400 ring-2 ring-brand-100' : 'border-slate-200')}>
                      <img src={url} alt="" className="h-28 w-full object-cover" />
                      {index === 0 && <span className="absolute left-2 top-2"><Badge tone="brand">Ảnh bìa</Badge></span>}
                      <div className="absolute right-1.5 top-1.5 flex gap-1 opacity-0 transition group-hover:opacity-100">
                        {index > 0 && <IconButton icon={Star} label="Đặt làm ảnh bìa" className="bg-white/90" onClick={() => set('image_urls', [url, ...draft.image_urls.filter((_, i) => i !== index)])} />}
                        <IconButton icon={Trash2} label="Xóa ảnh" className="bg-white/90 text-rose-600" onClick={() => set('image_urls', draft.image_urls.filter((_, i) => i !== index))} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <Input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="https://… hoặc /images/…" onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addImage() } }} />
                <Button type="button" variant="secondary" icon={ImagePlus} onClick={addImage}>Thêm</Button>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Vị trí" />
            <div className="grid gap-5 p-5 sm:grid-cols-2">
              <Field label="Địa chỉ" required className="sm:col-span-2"><Input value={draft.address} onChange={(e) => set('address', e.target.value)} required minLength={5} /></Field>
              <Field label="Vĩ độ"><Input type="number" step="any" value={draft.latitude} onChange={(e) => set('latitude', Number(e.target.value))} /></Field>
              <Field label="Kinh độ"><Input type="number" step="any" value={draft.longitude} onChange={(e) => set('longitude', Number(e.target.value))} /></Field>
              <div className="overflow-hidden rounded-lg border border-slate-200 sm:col-span-2"><iframe title="Bản đồ" src={mapSrc} className="h-64 w-full" loading="lazy" /></div>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Thông tin tham quan" />
            <div className="space-y-4 p-5">
              <Field label="Giờ mở cửa"><Input value={draft.opening_hours ?? ''} onChange={(e) => set('opening_hours', e.target.value)} placeholder="07:00 – 17:00" /></Field>
              <Field label="Giá vé"><Input value={draft.ticket_info ?? ''} onChange={(e) => set('ticket_info', e.target.value)} placeholder="Miễn phí / 40.000đ" /></Field>
            </div>
          </Card>
          <Card>
            <CardHeader title="Nguồn xác minh" description="Bắt buộc để xuất bản. Khi bạn xuất bản, tên, địa chỉ, tọa độ và loại được xác nhận theo nguồn này trong 12 tháng." />
            <div className="space-y-3 p-5">
              <Field label="Đường dẫn nguồn (HTTPS)"><Input type="url" value={draft.source_url ?? ''} onChange={(e) => set('source_url', e.target.value)} placeholder="https://" /></Field>
              {draft.source_url && <a href={draft.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-brand-600 hover:underline"><Link2 className="h-3.5 w-3.5" /> Mở nguồn</a>}
              {!draft.source_url && <Alert tone="amber">Chưa có nguồn nên chưa thể xuất bản địa điểm.</Alert>}
            </div>
          </Card>
          {place && (
            <Card>
              <CardHeader title="Thống kê" />
              <dl className="divide-y divide-slate-100 text-sm">
                <div className="flex justify-between px-5 py-2.5"><dt className="flex items-center gap-1.5 text-slate-500"><Eye className="h-4 w-4" /> Lượt xem 30 ngày</dt><dd className="font-semibold">{place.views_30d.toLocaleString('vi-VN')}</dd></div>
                <div className="flex justify-between px-5 py-2.5"><dt className="flex items-center gap-1.5 text-slate-500"><MapPin className="h-4 w-4" /> Trải nghiệm gắn kèm</dt><dd className="font-semibold">{place.experience_count}</dd></div>
              </dl>
            </Card>
          )}
        </div>
      </div>
    </form>
  )
}
