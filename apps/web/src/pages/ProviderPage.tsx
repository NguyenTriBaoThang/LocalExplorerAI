import { useEffect, useState } from 'react'
import {
  CalendarClock,
  CircleAlert,
  CircleCheck,
  Clock3,
  Pencil,
  Users,
  Search,
  Plus,
  Compass,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { apiErrorMessage, getExperiences } from '../api/client'
import { VerificationBadge } from '../components/common/StatusBadge'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import type { Experience } from '../types'
import { useTranslation } from '../i18n'

const today = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date())

const hour = (value: string, locale: string) =>
  new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(new Date(value))

export function ProviderPage() {
  const { t, locale } = useTranslation()
  const [experiences, setExperiences] = useState<Experience[]>([])
  const [error, setError] = useState('')
  const [selected, setSelected] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    const start = new Date(`${today()}T00:00:00+07:00`).toISOString()
    const end = new Date(`${today()}T23:59:59+07:00`).toISOString()
    getExperiences({ start_at: start, end_at: end })
      .then(setExperiences)
      .catch((reason) => setError(apiErrorMessage(reason)))
  }, [])

  const slotCount = experiences.reduce((total, exp) => total + exp.slots.length, 0)
  const uncertain = experiences
    .flatMap((exp) => exp.slots)
    .filter((slot) => slot.available_reported === null).length

  const filtered = experiences.filter(
    (e) =>
      e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.poi.name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="provider-page-3d page-wrap">
      {/* Partner Banner */}
      <div className="provider-banner-3d">
        <div className="banner-glow-shape" />
        <div className="banner-content-row">
          <div>
            <span className="eyebrow-3d text-emerald-300">
              <span className="eyebrow-dot bg-emerald-400" /> {locale === 'en' ? 'LOCAL PROVIDER PORTAL' : 'CỔNG THÔNG TIN ĐỐI TÁC'}
            </span>
            <h1 className="provider-banner-title">
              {locale === 'en' ? 'Your experiences,' : 'Trải nghiệm của bạn,'} <br />
              <em>{locale === 'en' ? 'better scheduled & discovered.' : 'được lên kế hoạch tốt hơn.'}</em>
            </h1>
            <p className="provider-banner-sub">
              {t('provider.subtitle')}
            </p>
          </div>
          <div className="banner-badge-mark">
            <div className="mark-circle">
              <CalendarClock size={36} className="text-emerald-400" />
            </div>
            <span>{locale === 'en' ? '3D PARTNER WORKSPACE' : 'WORKSPACE ĐỐI TÁC 3D'}</span>
          </div>
        </div>
      </div>

      {/* 3D KPI Metrics Cards */}
      <div className="provider-stats-grid">
        <TiltCard3D maxTilt={6} className="provider-stat-card">
          <span className="stat-label">{t('provider.activeOpen')}</span>
          <div className="stat-main">
            <strong>{experiences.length}</strong>
            <span className="stat-pill-ok">
              <CircleCheck size={13} /> {t('provider.ready')}
            </span>
          </div>
          <small>{t('provider.todayActivities')}</small>
        </TiltCard3D>

        <TiltCard3D maxTilt={6} className="provider-stat-card">
          <span className="stat-label">{t('provider.totalSlots')}</span>
          <div className="stat-main">
            <strong>{slotCount}</strong>
            <span className="stat-pill-info">
              <Clock3 size={13} /> {t('provider.realtime')}
            </span>
          </div>
          <small>{locale === 'en' ? 'Verified slots with current partner confirmation' : 'Ca đã xác minh, còn xác nhận từ đối tác'}</small>
        </TiltCard3D>

        <TiltCard3D maxTilt={6} className="provider-stat-card">
          <span className="stat-label">{t('provider.needsCapacityConfirm')}</span>
          <div className="stat-main">
            <strong className="text-amber">{uncertain}</strong>
            <span className="stat-pill-warn">
              <CircleAlert size={13} /> {t('provider.awaitingPartner')}
            </span>
          </div>
          <small>{t('provider.unclearRemaining')}</small>
        </TiltCard3D>
      </div>

      {/* Table Header & Search */}
      <div className="table-controls-bar">
        <div>
          <span className="results-sub">{locale === 'en' ? 'MANAGE EXPERIENCES CATALOG' : 'QUẢN LÝ DANH MỤC TRẢI NGHIỆM'}</span>
          <h2 className="table-heading-title">{t('provider.tableHeading')}</h2>
        </div>

        <div className="table-actions-group">
          <div className="table-search-box">
            <Search size={15} />
            <input
              placeholder={t('provider.filterActivities')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <button
            className="btn-primary-3d btn-sm"
            type="button"
            onClick={() =>
              window.alert(
                locale === 'en'
                  ? 'Adding experiences will be activated after signing in with a provider account.'
                  : 'Tính năng thêm mới hoạt động sẽ được kích hoạt sau khi đăng nhập tài khoản nhà cung cấp.'
              )
            }
          >
            <Plus size={15} />
            <span>{t('provider.addExperience')}</span>
          </button>
        </div>
      </div>

      {error && <div className="inline-alert-3d">{error}</div>}

      {/* 3D Modern Table */}
      <div className="provider-table-card-3d">
        <div className="table-header-row">
          <span>{locale === 'en' ? 'EXPERIENCE & VENUE' : 'TRẢI NGHIỆM & ĐỊA ĐIỂM'}</span>
          <span>{locale === 'en' ? 'NEXT SLOT' : 'KHUNG GIỜ TIẾP THEO'}</span>
          <span>{locale === 'en' ? 'CAPACITY' : 'SỨC CHỨA'}</span>
          <span>{locale === 'en' ? 'STATUS' : 'TRẠNG THÁI'}</span>
          <span>{locale === 'en' ? 'ACTIONS' : 'HÀNH ĐỘNG'}</span>
        </div>

        <div className="table-rows-container">
          {filtered.map((experience) => {
            const slot = experience.slots[0]
            const capacity =
              slot?.available_reported == null
                ? (locale === 'en' ? 'Unconfirmed' : 'Chưa xác nhận')
                : (locale === 'en' ? `${slot.available_reported} open seats` : `${slot.available_reported} chỗ trống`)
            const isOpen = selected === experience.id

            return (
              <div
                key={experience.id}
                className={`table-interactive-row ${isOpen ? 'row-expanded' : ''}`}
                onClick={() => setSelected(isOpen ? '' : experience.id)}
              >
                <div className="row-main-grid">
                  <div className="col-experience">
                    <span className="exp-glyph">
                      {experience.poi.category.slice(0, 1).toUpperCase()}
                    </span>
                    <div className="exp-details">
                      <strong>{experience.name}</strong>
                      <small>{experience.poi.name}</small>
                    </div>
                  </div>

                  <div className="col-time">
                    {slot ? (
                      <>
                        <strong>
                          {hour(slot.start_at, locale)} – {hour(slot.end_at, locale)}
                        </strong>
                        <small>
                          {new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
                            dateStyle: 'medium',
                            timeZone: 'Asia/Ho_Chi_Minh',
                          }).format(new Date(slot.start_at))}
                        </small>
                      </>
                    ) : (
                      <span className="text-muted">{locale === 'en' ? 'No slot scheduled' : 'Chưa có slot'}</span>
                    )}
                  </div>

                  <div className={`col-capacity ${slot?.available_reported == null ? 'text-amber' : ''}`}>
                    <Users size={14} />
                    <span>{capacity}</span>
                  </div>

                  <div className="col-badge">
                    <VerificationBadge status={experience.data_mode === 'real' ? 'verified' : 'unverified'} />
                  </div>

                  <div className="col-action">
                    <button type="button" className="btn-table-inspect">
                      {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      <span>{isOpen ? (locale === 'en' ? 'Close' : 'Đóng') : (locale === 'en' ? 'View' : 'Xem')}</span>
                    </button>
                  </div>
                </div>

                {isOpen && (
                  <div className="row-expanded-panel">
                    <p className="exp-full-desc">{experience.description}</p>
                    <div className="exp-extra-info">
                      <span>{locale === 'en' ? `Duration: ${experience.duration_min} mins` : `Thời lượng: ${experience.duration_min} phút`}</span>
                      <span>
                        {locale === 'en' ? `Price: ${experience.price_vnd.toLocaleString('vi-VN')}₫ / person` : `Giá: ${experience.price_vnd.toLocaleString('vi-VN')}₫ / người`}
                      </span>
                      <span>{locale === 'en' ? `Address: ${experience.poi.address}` : `Địa chỉ: ${experience.poi.address}`}</span>
                    </div>
                    <button
                      type="button"
                      className="btn-edit-action"
                      onClick={(e) => {
                        e.stopPropagation()
                        window.alert(locale === 'en' ? 'Editing requires provider role permission.' : 'Tính năng chỉnh sửa yêu cầu phân quyền quản trị viên.')
                      }}
                    >
                      <Pencil size={13} />
                      <span>{locale === 'en' ? 'Edit Experience Details' : 'Chỉnh sửa thông tin trải nghiệm'}</span>
                    </button>
                  </div>
                )}
              </div>
            )
          })}

          {!filtered.length && !error && (
            <div className="empty-table-state">
              <Compass size={24} className="text-emerald" />
              <span>{locale === 'en' ? 'No experiences match your search query.' : 'Không tìm thấy hoạt động phù hợp với từ khóa.'}</span>
            </div>
          )}
        </div>
      </div>

      <p className="provider-disclaimer">
        {locale === 'en'
          ? 'Only source-verified catalog entries and recently confirmed slots are shown. Manage listings after signing in with a provider account.'
          : 'Chỉ hiển thị địa điểm có nguồn đã xác minh và ca còn xác nhận mới. Đăng nhập bằng tài khoản đối tác để quản lý dữ liệu.'}
      </p>
    </div>
  )
}
