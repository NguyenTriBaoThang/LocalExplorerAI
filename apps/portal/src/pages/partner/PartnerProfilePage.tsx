import { useState, type FormEvent } from 'react'
import { ExternalLink, Pencil, Send } from 'lucide-react'
import { ApplicationForm, applicationFromProfile, cleanApplication } from '../../components/ApplicationForm'
import { Alert, Button, Card, CardHeader, DescriptionList, PageHeader, StatusBadge, useToast } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import { BUSINESS_TYPES, formatDateTime } from '../../lib/format'
import { usePartner } from './PartnerLayout'

export function PartnerProfilePage() {
  const { profile, reload } = usePartner()
  const toast = useToast()
  const editable = profile.verification_status === 'pending' || profile.verification_status === 'rejected'
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(() => applicationFromProfile(profile))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await partnerApi.updateApplication(cleanApplication(draft))
      await reload()
      setEditing(false)
      toast.success(profile.verification_status === 'rejected' ? 'Đã gửi lại hồ sơ để duyệt.' : 'Đã cập nhật hồ sơ.')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Hồ sơ đối tác" description="Thông tin cơ sở kinh doanh và trạng thái xét duyệt."
        actions={editable && !editing && <Button icon={Pencil} variant="secondary" onClick={() => { setDraft(applicationFromProfile(profile)); setEditing(true) }}>Chỉnh sửa hồ sơ</Button>} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {profile.verification_status === 'rejected' && (
            <Alert tone="red" title="Hồ sơ chưa được duyệt">
              {profile.review_note || 'Vui lòng bổ sung thông tin và gửi lại.'}
            </Alert>
          )}
          {editing ? (
            <Card>
              <CardHeader title="Cập nhật hồ sơ" description={profile.verification_status === 'rejected' ? 'Sau khi gửi, hồ sơ sẽ quay lại hàng chờ duyệt.' : undefined} />
              <form onSubmit={submit} className="space-y-5 p-5">
                {error && <Alert tone="red">{error}</Alert>}
                <ApplicationForm value={draft} onChange={setDraft} />
                <div className="flex justify-end gap-2 border-t border-slate-100 pt-5">
                  <Button type="button" variant="secondary" onClick={() => setEditing(false)}>Hủy</Button>
                  <Button type="submit" icon={Send} loading={busy}>{profile.verification_status === 'rejected' ? 'Gửi lại hồ sơ' : 'Lưu thay đổi'}</Button>
                </div>
              </form>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader title="Thông tin cơ sở" />
                <div className="px-5 py-2">
                  <DescriptionList items={[
                    ['Tên cơ sở', profile.name],
                    ['Loại hình', profile.business_type ? BUSINESS_TYPES[profile.business_type] : ''],
                    ['Email liên hệ', profile.contact_email],
                    ['Điện thoại', profile.contact_phone],
                    ['Địa chỉ', profile.address],
                    ['Website', profile.website && <a href={profile.website} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">{profile.website}</a>],
                    ['Giới thiệu', profile.description],
                  ]} />
                </div>
              </Card>
              <Card>
                <CardHeader title="Pháp lý & giấy tờ" />
                <div className="px-5 py-2">
                  <DescriptionList items={[
                    ['Mã số thuế', profile.tax_code],
                    ['Giấy phép KD', profile.business_license_no],
                    ['Giấy tờ', profile.document_urls.length > 0 && (
                      <ul className="space-y-1">
                        {profile.document_urls.map((url) => (
                          <li key={url}><a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">{url.replace(/^https?:\/\//, '').slice(0, 48)} <ExternalLink className="h-3 w-3" /></a></li>
                        ))}
                      </ul>
                    )],
                    ['Ghi chú', profile.application_note],
                  ]} />
                </div>
              </Card>
            </>
          )}
        </div>

        <Card className="h-fit">
          <CardHeader title="Trạng thái xét duyệt" />
          <div className="space-y-4 p-5 text-sm">
            <div className="flex items-center justify-between"><span className="text-slate-500">Trạng thái</span><StatusBadge status={profile.verification_status} /></div>
            <div className="flex items-center justify-between"><span className="text-slate-500">Ngày gửi</span><span className="text-slate-900">{formatDateTime(profile.applied_at)}</span></div>
            <div className="flex items-center justify-between"><span className="text-slate-500">Ngày duyệt</span><span className="text-slate-900">{formatDateTime(profile.reviewed_at)}</span></div>
            {profile.review_note && (
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Ghi chú từ quản trị viên</p>
                <p className="mt-1 text-slate-700">{profile.review_note}</p>
              </div>
            )}
          </div>
        </Card>
      </div>
    </>
  )
}
