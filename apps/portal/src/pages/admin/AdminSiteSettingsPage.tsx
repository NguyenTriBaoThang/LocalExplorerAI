import { useEffect, useState } from 'react'
import { Megaphone, Save } from 'lucide-react'
import { Alert, Button, Card, CardHeader, Field, PageHeader, Spinner, Textarea, Toggle, useToast } from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import type { SiteSettings } from '../../lib/types'

const MAX_LENGTH = 300

/** What travelers see on every page of the web app: an announcement bar and a maintenance notice. */
export function AdminSiteSettingsPage() {
  const toast = useToast()
  const [saved, setSaved] = useState<SiteSettings | null>(null)
  const [draft, setDraft] = useState<SiteSettings | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    adminApi.siteSettings().then((data) => { setSaved(data); setDraft(data) }).catch((err) => toast.error(errorMessage(err)))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!draft || !saved) return <Spinner />
  const dirty = draft.site_announcement !== saved.site_announcement || draft.maintenance_mode !== saved.maintenance_mode

  const save = async () => {
    setSaving(true)
    try {
      const next = await adminApi.saveSiteSettings(draft)
      setSaved(next); setDraft(next)
      toast.success('Đã lưu. Khách truy cập sẽ thấy thay đổi khi tải lại trang.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader title="Cài đặt website" description="Thông báo hiển thị cho du khách trên website." />
      <div className="grid max-w-3xl gap-5">
        <Card>
          <CardHeader title="Thông báo toàn site" description="Một dòng hiển thị phía trên mọi trang của website. Để trống để ẩn." />
          <div className="space-y-4 p-5">
            <Field label="Nội dung thông báo" hint={`${draft.site_announcement.length}/${MAX_LENGTH} ký tự`}>
              <Textarea rows={2} maxLength={MAX_LENGTH} value={draft.site_announcement} onChange={(e) => setDraft({ ...draft, site_announcement: e.target.value })} placeholder="Ví dụ: Lễ hội áo dài 9–11/03, một số tuyến đường tạm đóng." />
            </Field>
            {draft.site_announcement.trim() && (
              <div className="flex items-start gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800"><Megaphone size={16} className="mt-0.5 shrink-0" /><span>{draft.site_announcement.trim()}</span></div>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Chế độ bảo trì" description="Hiện thông báo bảo trì trên website. Du khách vẫn dùng được các tính năng bình thường." />
          <div className="space-y-3 p-5">
            <Toggle checked={draft.maintenance_mode} onChange={(value) => setDraft({ ...draft, maintenance_mode: value })} label="Hiện thông báo bảo trì" />
            {draft.maintenance_mode && <Alert tone="amber">Website sẽ hiện banner “đang bảo trì, một số tính năng có thể gián đoạn” cho mọi du khách.</Alert>}
          </div>
        </Card>
        <div className="flex justify-end"><Button icon={Save} loading={saving} disabled={!dirty} onClick={save}>Lưu thay đổi</Button></div>
      </div>
    </>
  )
}
