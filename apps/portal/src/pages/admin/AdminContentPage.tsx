import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Check, EyeOff, FileText, ImagePlus, Layers, Pencil, Plus, Trash2, X } from 'lucide-react'
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Field, IconButton, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Tabs, Textarea, Toggle, useToast,
} from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import type { AdminPlace, Article, Banner, Collection, ModerationQueue } from '../../lib/types'

type Tab = 'review' | 'banners' | 'articles' | 'collections'

export function AdminContentPage() {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') ?? 'review') as Tab
  return (
    <>
      <PageHeader title="Nội dung" description="Kiểm duyệt nội dung từ đối tác và quản lý nội dung hiển thị trên website." />
      <div className="mb-6">
        <Tabs value={tab} onChange={(value) => setParams({ tab: value })} items={[
          { value: 'review', label: 'Kiểm duyệt' }, { value: 'banners', label: 'Banner trang chủ' },
          { value: 'articles', label: 'Bài viết & Cẩm nang' }, { value: 'collections', label: 'Bộ sưu tập' },
        ]} />
      </div>
      {tab === 'review' && <ReviewQueue />}
      {tab === 'banners' && <Banners />}
      {tab === 'articles' && <Articles />}
      {tab === 'collections' && <Collections />}
    </>
  )
}

/* ---------- Moderation (live API) ---------- */

function ReviewQueue() {
  const toast = useToast()
  const [status, setStatus] = useState('pending')
  const [queue, setQueue] = useState<ModerationQueue | null>(null)
  const [partners, setPartners] = useState<Record<string, string>>({})
  useEffect(() => { adminApi.providers({ limit: 500, offset: 0 }).then((page) => setPartners(Object.fromEntries(page.items.map((p) => [p.id, p.name])))).catch(() => undefined) }, [])
  const load = useCallback(() => { setQueue(null); adminApi.moderation(status).then(setQueue).catch((err) => { toast.error(errorMessage(err)); setQueue({ pois: [], experiences: [], evidence: [] }) }) }, [status]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load])

  const act = async (type: 'poi' | 'experience' | 'evidence', id: string, action: 'approve' | 'reject' | 'hide') => {
    try {
      await adminApi.moderate(type, id, action)
      toast.success('Đã cập nhật trạng thái.')
      load()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }
  const actions = (type: 'poi' | 'experience' | 'evidence', id: string) => (
    <div className="flex justify-end gap-1">
      <IconButton icon={EyeOff} label="Ẩn" onClick={() => act(type, id, 'hide')} />
      <Button size="sm" variant="secondary" icon={X} onClick={() => act(type, id, 'reject')}>Từ chối</Button>
      <Button size="sm" variant="success" icon={Check} onClick={() => act(type, id, 'approve')}>Duyệt</Button>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-auto">
          <option value="pending">Chờ duyệt</option><option value="verified">Đã duyệt</option><option value="rejected">Từ chối</option><option value="hidden">Đã ẩn</option>
        </Select>
        <p className="text-sm text-slate-500">Duyệt trải nghiệm/địa điểm cần có minh chứng hợp lệ còn hiệu lực cho mọi trường bắt buộc.</p>
      </div>
      {!queue ? <Spinner /> : (
        <>
          <ModerationTable title="Trải nghiệm" count={queue.experiences.length} empty="Không có trải nghiệm nào"
            rows={queue.experiences.map((item) => ({ id: item.id, main: item.title, sub: `Đối tác: ${partners[item.provider_id] ?? '…'}`, status: item.status, actions: status === 'pending' && actions('experience', item.id) }))} />
          <ModerationTable title="Địa điểm do đối tác gửi" count={queue.pois.length} empty="Không có địa điểm nào"
            rows={queue.pois.map((item) => ({ id: item.id, main: item.name, sub: item.address, status: item.status, actions: status === 'pending' && actions('poi', item.id) }))} />
          <ModerationTable title="Minh chứng" count={queue.evidence.length} empty="Không có minh chứng nào"
            rows={queue.evidence.map((item) => ({
              id: item.id, status: item.status, actions: status === 'pending' && actions('evidence', item.id),
              main: <a href={item.source_uri} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">{item.source_label || item.source_uri}</a>,
              sub: `${item.target_type ?? '—'} · ${item.fields_covered.length} trường · hết hạn ${formatDate(item.expires_at)}`,
            }))} />
        </>
      )}
    </div>
  )
}

function ModerationTable({ title, count, empty, rows }: { title: string; count: number; empty: string; rows: Array<{ id: string; main: React.ReactNode; sub: string; status: string; actions: React.ReactNode }> }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader title={<span className="flex items-center gap-2">{title} <Badge>{count}</Badge></span>} />
      {rows.length === 0 ? <p className="px-5 py-6 text-center text-sm text-slate-500">{empty}</p> : (
        <ul className="divide-y divide-slate-100">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center gap-4 px-5 py-3">
              <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-slate-900">{row.main}</p><p className="truncate text-xs text-slate-500">{row.sub}</p></div>
              <StatusBadge status={row.status} />
              {row.actions}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/* ---------- Banners (sample data) ---------- */

const EMPTY_BANNER: Banner = { id: '', title: '', subtitle: '', image_url: '', link_url: '/', is_active: true, sort_order: 0, starts_at: null, ends_at: null }

function Banners() {
  const toast = useToast()
  const [items, setItems] = useState<Banner[] | null>(null)
  const [editing, setEditing] = useState<Banner | null>(null)
  const load = () => adminApi.banners().then(setItems).catch((err) => { toast.error(errorMessage(err)); setItems([]) })
  useEffect(() => { void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!editing) return
    try {
      await adminApi.saveBanner(editing)
      setEditing(null)
      toast.success('Đã lưu banner.')
      void load()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between"><p className="text-sm text-slate-500">Banner đang bật hiển thị ở đầu trang chủ web theo thứ tự.</p><Button icon={Plus} onClick={() => setEditing({ ...EMPTY_BANNER, sort_order: items?.length ?? 0 })}>Thêm banner</Button></div>
      {!items ? <Spinner /> : items.length === 0 ? <Card><EmptyState icon={ImagePlus} title="Chưa có banner" /></Card> : (
        <div className="grid gap-5 md:grid-cols-2">
          {items.map((banner) => (
            <Card key={banner.id} className="overflow-hidden">
              <div className="relative h-40 bg-slate-100">
                {banner.image_url && <img src={banner.image_url} alt="" className="h-full w-full object-cover" />}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/70 via-slate-900/10 to-transparent" />
                <div className="absolute bottom-3 left-4 right-4 text-white">
                  <p className="font-semibold">{banner.title}</p>
                  <p className="text-sm text-white/80">{banner.subtitle}</p>
                </div>
                <span className="absolute left-3 top-3">{banner.is_active ? <Badge tone="green" dot>Đang hiển thị</Badge> : <Badge dot>Tắt</Badge>}</span>
              </div>
              <div className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="truncate text-slate-500">#{banner.sort_order + 1} · Liên kết: {banner.link_url}</span>
                <div className="flex gap-1">
                  <IconButton icon={Pencil} label="Sửa" onClick={() => setEditing(banner)} />
                  <IconButton icon={Trash2} label="Xóa" className="text-rose-600" onClick={async () => { await adminApi.deleteBanner(banner.id).catch((err) => toast.error(errorMessage(err))); void load() }} />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.id ? 'Sửa banner' : 'Thêm banner'}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Hủy</Button><Button type="submit" form="banner-form">Lưu</Button></>}>
        {editing && (
          <form id="banner-form" onSubmit={save} className="space-y-4">
            <Field label="Tiêu đề" required><Input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} required /></Field>
            <Field label="Mô tả ngắn"><Input value={editing.subtitle} onChange={(e) => setEditing({ ...editing, subtitle: e.target.value })} /></Field>
            <Field label="Ảnh (URL)" required><Input value={editing.image_url} onChange={(e) => setEditing({ ...editing, image_url: e.target.value })} required /></Field>
            {editing.image_url && <img src={editing.image_url} alt="" className="h-32 w-full rounded-lg object-cover" />}
            <div className="grid gap-4 sm:grid-cols-[1fr_120px]">
              <Field label="Liên kết khi bấm" hint="Đường dẫn trong web (/explore) hoặc HTTPS"><Input value={editing.link_url} onChange={(e) => setEditing({ ...editing, link_url: e.target.value })} /></Field>
              <Field label="Thứ tự"><Input type="number" min={0} value={editing.sort_order} onChange={(e) => setEditing({ ...editing, sort_order: Number(e.target.value) })} /></Field>
            </div>
            <Toggle checked={editing.is_active} onChange={(v) => setEditing({ ...editing, is_active: v })} label="Hiển thị trên trang chủ" />
          </form>
        )}
      </Modal>
    </>
  )
}

/* ---------- Articles (sample data) ---------- */

const EMPTY_ARTICLE: Article = { id: '', title: '', slug: '', excerpt: '', body: '', cover_url: '', status: 'draft', category: 'Cẩm nang', published_at: null, updated_at: '' }
const slugify = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

function Articles() {
  const toast = useToast()
  const [items, setItems] = useState<Article[] | null>(null)
  const [editing, setEditing] = useState<Article | null>(null)
  const load = () => adminApi.articles().then(setItems).catch((err) => { toast.error(errorMessage(err)); setItems([]) })
  useEffect(() => { void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const open = async (article: Article) => {
    try {
      setEditing(await adminApi.article(article.id))  // the list omits the body
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const save = async (status: Article['status']) => {
    if (!editing) return
    try {
      await adminApi.saveArticle({ ...editing, status })
      setEditing(null)
      toast.success(status === 'published' ? 'Đã đăng bài viết.' : 'Đã lưu nháp.')
      void load()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between"><p className="text-sm text-slate-500">Bài đã đăng hiển thị ở mục Cẩm nang trên web.</p><Button icon={Plus} onClick={() => setEditing({ ...EMPTY_ARTICLE })}>Viết bài</Button></div>
      <Card className="overflow-hidden">
        {!items ? <Spinner /> : items.length === 0 ? <EmptyState icon={FileText} title="Chưa có bài viết" /> : (
          <ul className="divide-y divide-slate-100">
            {items.map((article) => (
              <li key={article.id} className="flex items-center gap-4 px-5 py-3.5">
                <div className="h-14 w-20 shrink-0 overflow-hidden rounded-lg bg-slate-100">{article.cover_url && <img src={article.cover_url} alt="" className="h-full w-full object-cover" />}</div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-900">{article.title}</p>
                  <p className="truncate text-xs text-slate-500">{article.category} · /{article.slug} · cập nhật {formatDateTime(article.updated_at)}</p>
                </div>
                <StatusBadge status={article.status} />
                <IconButton icon={Pencil} label="Sửa" onClick={() => void open(article)} />
                <IconButton icon={Trash2} label="Xóa" className="text-rose-600" onClick={async () => { await adminApi.deleteArticle(article.id).catch((err) => toast.error(errorMessage(err))); void load() }} />
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Modal open={!!editing} onClose={() => setEditing(null)} size="lg" title={editing?.id ? 'Sửa bài viết' : 'Viết bài mới'}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Hủy</Button><Button variant="secondary" onClick={() => save('draft')}>Lưu nháp</Button><Button onClick={() => save('published')} disabled={!editing?.title}>Đăng bài</Button></>}>
        {editing && (
          <div className="space-y-4">
            <Field label="Tiêu đề" required><Input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Đường dẫn" hint={`/${editing.slug || slugify(editing.title) || '…'}`}><Input value={editing.slug} onChange={(e) => setEditing({ ...editing, slug: slugify(e.target.value) })} placeholder="tự tạo từ tiêu đề" /></Field>
              <Field label="Chuyên mục">
                <Select value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value })}>
                  <option>Cẩm nang</option><option>Trải nghiệm</option><option>Sự kiện</option><option>Tin tức</option>
                </Select>
              </Field>
            </div>
            <Field label="Ảnh bìa (URL)"><Input value={editing.cover_url} onChange={(e) => setEditing({ ...editing, cover_url: e.target.value })} /></Field>
            <Field label="Tóm tắt"><Textarea value={editing.excerpt} onChange={(e) => setEditing({ ...editing, excerpt: e.target.value })} className="min-h-[64px]" /></Field>
            <Field label="Nội dung" hint="Hỗ trợ Markdown"><Textarea value={editing.body ?? ''} onChange={(e) => setEditing({ ...editing, body: e.target.value })} className="min-h-[220px] font-mono text-[13px]" /></Field>
          </div>
        )}
      </Modal>
    </>
  )
}

/* ---------- Collections (sample data) ---------- */

function Collections() {
  const toast = useToast()
  const [items, setItems] = useState<Collection[] | null>(null)
  const [places, setPlaces] = useState<AdminPlace[]>([])
  const [editing, setEditing] = useState<Collection | null>(null)
  const load = () => adminApi.collections().then(setItems).catch((err) => { toast.error(errorMessage(err)); setItems([]) })
  useEffect(() => { void load(); adminApi.places().then(setPlaces).catch(() => undefined) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const name = (id: string) => places.find((p) => p.id === id)?.name ?? id

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!editing) return
    try {
      await adminApi.saveCollection(editing)
      setEditing(null)
      toast.success('Đã lưu bộ sưu tập.')
      void load()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between"><p className="text-sm text-slate-500">Chỉ địa điểm đang hiển thị mới xuất hiện trong bộ sưu tập trên web.</p><Button icon={Plus} onClick={() => setEditing({ id: '', title: '', description: '', place_ids: [], is_active: true, sort_order: items?.length ?? 0 })}>Tạo bộ sưu tập</Button></div>
      {!items ? <Spinner /> : items.length === 0 ? <Card><EmptyState icon={Layers} title="Chưa có bộ sưu tập" /></Card> : (
        <div className="grid gap-5 md:grid-cols-2">
          {items.map((collection) => (
            <Card key={collection.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div><p className="font-semibold text-slate-900">{collection.title}</p><p className="mt-0.5 text-sm text-slate-500">{collection.description}</p></div>
                <div className="flex gap-1">
                  <IconButton icon={Pencil} label="Sửa" onClick={() => setEditing(collection)} />
                  <IconButton icon={Trash2} label="Xóa" className="text-rose-600" onClick={async () => { await adminApi.deleteCollection(collection.id).catch((err) => toast.error(errorMessage(err))); void load() }} />
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">{collection.place_ids.map((id) => <Badge key={id} tone="brand">{name(id)}</Badge>)}</div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.id ? 'Sửa bộ sưu tập' : 'Tạo bộ sưu tập'}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Hủy</Button><Button type="submit" form="collection-form">Lưu</Button></>}>
        {editing && (
          <form id="collection-form" onSubmit={save} className="space-y-4">
            <Field label="Tên bộ sưu tập" required><Input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} required /></Field>
            <Field label="Mô tả"><Textarea value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} className="min-h-[64px]" /></Field>
            <div>
              <p className="mb-2 text-sm font-medium text-slate-700">Địa điểm</p>
              <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
                {places.map((place) => (
                  <label key={place.id} className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-slate-50">
                    <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-brand-600" checked={editing.place_ids.includes(place.id)}
                      onChange={(e) => setEditing({ ...editing, place_ids: e.target.checked ? [...editing.place_ids, place.id] : editing.place_ids.filter((id) => id !== place.id) })} />
                    {place.name} <span className="text-slate-400">· {place.district ?? '—'}</span> <StatusBadge status={place.status} />
                  </label>
                ))}
              </div>
            </div>
            <Toggle checked={editing.is_active} onChange={(v) => setEditing({ ...editing, is_active: v })} label="Hiển thị trên trang chủ web" />
          </form>
        )}
      </Modal>
      {places.length === 0 && items && <Alert tone="brand">Thêm địa điểm trước để đưa vào bộ sưu tập.</Alert>}
    </>
  )
}

