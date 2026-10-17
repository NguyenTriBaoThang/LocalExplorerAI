import { Plus, Trash2 } from 'lucide-react'
import { BUSINESS_TYPES } from '../lib/format'
import type { BusinessType, PartnerApplication, ProviderProfile } from '../lib/types'
import { Field, IconButton, Input, Select, Textarea, Button } from './ui'

export const EMPTY_APPLICATION: PartnerApplication = {
  business_name: '', business_type: 'household', description: '', contact_phone: '', address: '',
  tax_code: '', business_license_no: '', website: '', document_urls: [], application_note: '',
}

export function applicationFromProfile(profile: ProviderProfile): PartnerApplication {
  return {
    business_name: profile.name, business_type: profile.business_type ?? 'household', description: profile.description,
    contact_phone: profile.contact_phone ?? '', address: profile.address, tax_code: profile.tax_code ?? '',
    business_license_no: profile.business_license_no ?? '', website: profile.website ?? '',
    document_urls: profile.document_urls, application_note: profile.application_note,
  }
}

/** Send optional blanks as null so the API validators (e.g. website URL) skip them. */
export function cleanApplication(value: PartnerApplication): PartnerApplication {
  return {
    ...value,
    tax_code: value.tax_code?.trim() || null,
    business_license_no: value.business_license_no?.trim() || null,
    website: value.website?.trim() || null,
    document_urls: value.document_urls.map((url) => url.trim()).filter(Boolean),
  }
}

type Section = 'business' | 'legal' | 'all'

export function ApplicationForm({ value, onChange, section = 'all' }: { value: PartnerApplication; onChange: (value: PartnerApplication) => void; section?: Section }) {
  const set = <K extends keyof PartnerApplication>(key: K, next: PartnerApplication[K]) => onChange({ ...value, [key]: next })
  const showBusiness = section === 'all' || section === 'business'
  const showLegal = section === 'all' || section === 'legal'

  return (
    <div className="space-y-5">
      {showBusiness && (
        <>
          <div className="grid gap-5 sm:grid-cols-[1fr_200px]">
            <Field label="Tên cơ sở / thương hiệu" required>
              <Input value={value.business_name} onChange={(e) => set('business_name', e.target.value)} placeholder="VD: Xưởng gốm Lái Thiêu" required minLength={2} />
            </Field>
            <Field label="Loại hình" required>
              <Select value={value.business_type} onChange={(e) => set('business_type', e.target.value as BusinessType)}>
                {Object.entries(BUSINESS_TYPES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </Select>
            </Field>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Số điện thoại liên hệ" required>
              <Input value={value.contact_phone} onChange={(e) => set('contact_phone', e.target.value)} placeholder="09xx xxx xxx" required minLength={6} inputMode="tel" />
            </Field>
            <Field label="Website / Fanpage" hint="Không bắt buộc">
              <Input value={value.website ?? ''} onChange={(e) => set('website', e.target.value)} placeholder="https://" type="url" />
            </Field>
          </div>
          <Field label="Địa chỉ" required>
            <Input value={value.address} onChange={(e) => set('address', e.target.value)} placeholder="Số nhà, đường, phường/xã, quận/huyện" required minLength={5} />
          </Field>
          <Field label="Giới thiệu ngắn" hint="Khách du lịch sẽ thấy mô tả này khi xem trải nghiệm của bạn.">
            <Textarea value={value.description} onChange={(e) => set('description', e.target.value)} placeholder="Bạn cung cấp trải nghiệm gì, điều gì làm nên sự khác biệt…" />
          </Field>
        </>
      )}
      {showLegal && (
        <>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Mã số thuế" hint="Không bắt buộc với cá nhân">
              <Input value={value.tax_code ?? ''} onChange={(e) => set('tax_code', e.target.value)} />
            </Field>
            <Field label="Số giấy phép kinh doanh" hint="Không bắt buộc">
              <Input value={value.business_license_no ?? ''} onChange={(e) => set('business_license_no', e.target.value)} />
            </Field>
          </div>
          <div>
            <p className="mb-1.5 text-sm font-medium text-slate-700">Liên kết giấy tờ</p>
            <p className="mb-3 text-xs text-slate-500">Dán link Google Drive/Dropbox tới giấy phép, CCCD người đại diện, hình ảnh cơ sở… (tối đa 10).</p>
            <div className="space-y-2">
              {value.document_urls.map((url, index) => (
                <div key={index} className="flex gap-2">
                  <Input value={url} type="url" placeholder="https://" onChange={(e) => set('document_urls', value.document_urls.map((item, i) => (i === index ? e.target.value : item)))} />
                  <IconButton icon={Trash2} label="Xóa liên kết" className="h-[38px] w-[38px] shrink-0" onClick={() => set('document_urls', value.document_urls.filter((_, i) => i !== index))} />
                </div>
              ))}
              {value.document_urls.length < 10 && (
                <Button type="button" variant="secondary" size="sm" icon={Plus} onClick={() => set('document_urls', [...value.document_urls, ''])}>Thêm liên kết</Button>
              )}
            </div>
          </div>
          <Field label="Ghi chú cho đội ngũ duyệt" hint="Không bắt buộc">
            <Textarea value={value.application_note} onChange={(e) => set('application_note', e.target.value)} className="min-h-[72px]" />
          </Field>
        </>
      )}
    </div>
  )
}
