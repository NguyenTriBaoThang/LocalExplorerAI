import { useState, type FormEvent } from 'react'
import { Save } from 'lucide-react'
import { Alert, Button, Card, Field, Input, PageHeader, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { operatorApi, type OperatorOrg } from '../../lib/operatorApi'
import { useOperator } from './OperatorLayout'

const NUMBER_FIELDS: Array<{ key: keyof OperatorOrg; label: string; hint?: string; min: number; max: number }> = [
  { key: 'margin_floor_pct', label: 'Biên lợi nhuận tối thiểu (%)', hint: 'Báo giá thấp hơn mức này sẽ bị cảnh báo.', min: 0, max: 90 },
  { key: 'default_markup_pct', label: 'Markup mặc định (%)', min: 0, max: 300 },
  { key: 'deposit_pct', label: 'Tỷ lệ đặt cọc (%)', min: 0, max: 100 },
  { key: 'quote_validity_days', label: 'Số ngày hiệu lực báo giá', min: 1, max: 90 },
  { key: 'ota_commission_pct', label: 'Hoa hồng OTA (%)', hint: 'Dùng để tính ROI so với bán qua OTA.', min: 0, max: 60 },
  { key: 'manual_minutes_per_quote', label: 'Phút làm báo giá thủ công', hint: 'Dùng để tính thời gian tiết kiệm.', min: 1, max: 1440 },
]

export function OperatorSettingsPage() {
  const { org, reload } = useOperator()
  const toast = useToast()
  const [form, setForm] = useState<Record<string, string>>(() => ({ name: org.name, ...Object.fromEntries(NUMBER_FIELDS.map((f) => [f.key, String(org[f.key])])) }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await operatorApi.updateOrg({ name: form.name.trim(), ...Object.fromEntries(NUMBER_FIELDS.map((f) => [f.key, Number(form[f.key])])) })
      await reload()
      toast.success('Đã lưu cài đặt')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader title="Cài đặt" description="Thông số mặc định dùng khi lập báo giá." />
      <Card>
        <form onSubmit={save} className="grid gap-4 p-5 sm:grid-cols-2">
          {error && <div className="sm:col-span-2"><Alert tone="red">{error}</Alert></div>}
          <Field label="Tên doanh nghiệp" required className="sm:col-span-2">
            <Input value={form.name} minLength={2} maxLength={180} required onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          {NUMBER_FIELDS.map((f) => (
            <Field key={f.key} label={f.label} hint={f.hint}>
              <Input type="number" min={f.min} max={f.max} required value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
            </Field>
          ))}
          <div className="sm:col-span-2"><Button type="submit" icon={Save} loading={busy}>Lưu thay đổi</Button></div>
        </form>
      </Card>
    </div>
  )
}
