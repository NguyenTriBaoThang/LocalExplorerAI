import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  User,
  Lock,
  Calendar,
  ArrowRight,
  GitCompare,
  CheckCircle2,
  AlertCircle,
  Route,
  Shield,
  Brain,
} from 'lucide-react'
import {
  apiErrorMessage,
  changePassword,
  getMyItineraries,
  getRecommendationConsent,
  updateProfile,
  updateRecommendationConsent,
  type RecommendationConsent,
} from '../api/client'
import { useAuth } from '../auth'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { SessionsCard } from '../components/account/SessionsCard'
import { MfaCard } from '../components/account/MfaCard'
import { useTranslation } from '../i18n'
import { ReviewPrompt } from '../components/content/ReviewPrompt'

export function ProfilePage() {
  const { t, locale } = useTranslation()
  const { user, setUser } = useAuth()
  const [name, setName] = useState(user?.display_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [password, setPassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [trips, setTrips] = useState<
    Array<{ id: string; planned_date: string | null; status: string; estimated_cost_vnd: number }>
  >([])
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)
  const [recommendationConsent, setRecommendationConsent] = useState<RecommendationConsent | null>(null)
  const [loadingRecommendationConsent, setLoadingRecommendationConsent] = useState(false)
  const [savingRecommendationConsent, setSavingRecommendationConsent] = useState(false)

  useEffect(() => {
    if (user?.role !== 'traveler') {
      setTrips([])
      return
    }
    getMyItineraries()
      .then(setTrips)
      .catch(() => setTrips([]))
  }, [user?.role])

  useEffect(() => {
    let active = true
    if (user?.role !== 'traveler') {
      setRecommendationConsent(null)
      return
    }
    setLoadingRecommendationConsent(true)
    getRecommendationConsent()
      .then((consent) => {
        if (active) setRecommendationConsent(consent)
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(apiErrorMessage(reason))
          setRecommendationConsent({
            personalization_enabled: false,
            model_training_enabled: false,
            admin_history_enabled: false,
            consent_version: 'behavior-v2',
          })
        }
      })
      .finally(() => {
        if (active) setLoadingRecommendationConsent(false)
      })
    return () => { active = false }
  }, [user?.id, user?.role])

  async function save(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    setSavingProfile(true)
    try {
      setUser(await updateProfile(name, phone || null))
      setNotice(t('profile.updateSuccess'))
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setSavingProfile(false)
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    setSavingPassword(true)
    try {
      await changePassword(currentPassword || null, password)
      setPassword('')
      setCurrentPassword('')
      setNotice(locale === 'en' ? 'Password updated successfully!' : 'Đã thay đổi mật khẩu tài khoản thành công!')
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setSavingPassword(false)
    }
  }

  async function saveRecommendationConsent(
    changes: Partial<Pick<RecommendationConsent, 'personalization_enabled' | 'model_training_enabled' | 'admin_history_enabled'>>,
  ) {
    if (!recommendationConsent) return
    setError('')
    setNotice('')
    setSavingRecommendationConsent(true)
    try {
      const updated = await updateRecommendationConsent(
        changes.personalization_enabled ?? recommendationConsent.personalization_enabled,
        changes.model_training_enabled ?? recommendationConsent.model_training_enabled,
        changes.admin_history_enabled ?? recommendationConsent.admin_history_enabled,
      )
      setRecommendationConsent(updated)
      setNotice(locale === 'en' ? 'Recommendation data settings updated.' : 'Đã cập nhật lựa chọn dữ liệu gợi ý.')
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setSavingRecommendationConsent(false)
    }
  }

  const roleLabels: Record<string, string> = {
    traveler: t('profile.bannerRoleTraveler'),
    provider: t('profile.bannerRoleProvider'),
    admin: t('profile.bannerRoleAdmin'),
  }

  const userInitials = (user?.display_name || user?.email || 'U').slice(0, 2).toUpperCase()

  return (
    <div className="profile-page-3d page-wrap">
      {/* Profile Header Banner */}
      <div className="profile-banner-card">
        <div className="profile-banner-left">
          <div className="profile-avatar-giant">
            <span>{userInitials}</span>
          </div>
          <div className="profile-user-headline">
            <span className="profile-role-badge">
              <Shield size={12} className="text-emerald" />
              {roleLabels[user?.role || ''] || user?.role}
            </span>
            <h1 className="profile-user-name">{user?.display_name || (locale === 'en' ? 'User' : 'Người dùng')}</h1>
            <p className="profile-user-email">{user?.email}</p>
          </div>
        </div>

        {user?.role === 'traveler' && (
          <div className="profile-quick-stats">
            <div className="profile-stat-box">
              <small>{t('profile.savedTripsKpi')}</small>
              <strong>{trips.length}</strong>
            </div>
            <Link to="/planner" className="btn-primary-3d btn-sm">
              <span>{t('profile.createNewTrip')}</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        )}
      </div>

      {notice && (
        <div className="inline-alert-3d alert-success">
          <CheckCircle2 size={16} className="text-emerald" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="inline-alert-3d">
          <AlertCircle size={16} className="text-amber" />
          <span>{error}</span>
        </div>
      )}

      {/* 2-Column Split: Settings + Trip History */}
      <div className="profile-layout-grid" style={user?.role === 'traveler' ? undefined : { gridTemplateColumns: 'minmax(0, 1fr)' }}>
        {/* Left Column: Account & Security Forms */}
        <div className="profile-forms-col">
          {/* Personal Info Card */}
          <section className="profile-card-3d">
            <div className="profile-card-title-row">
              <div className="profile-title-icon-box text-emerald">
                <User size={18} />
              </div>
              <div>
                <h2>{t('profile.personalInfoTitle')}</h2>
                <p>{t('profile.personalInfoDesc')}</p>
              </div>
            </div>

            <form onSubmit={save} className="profile-form">
              <div className="field-group-3d">
                <span>{t('profile.nameLabel')}</span>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={locale === 'en' ? 'Enter display name...' : 'Nhập họ và tên...'}
                />
              </div>

              <div className="field-group-3d">
                <span>{t('profile.phoneLabel')}</span>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="09xx xxx xxx"
                />
              </div>

              <button className="btn-primary-3d" type="submit" disabled={savingProfile}>
                <span>{savingProfile ? t('profile.saving') : t('profile.saveChanges')}</span>
              </button>
            </form>
          </section>

          {user?.role === 'traveler' && (
            <section className="profile-card-3d">
              <div className="profile-card-title-row">
                <div className="profile-title-icon-box text-emerald">
                  <Brain size={18} />
                </div>
                <div>
                  <h2>{locale === 'en' ? 'Recommendation data' : 'Dữ liệu gợi ý cá nhân'}</h2>
                  <p>{locale === 'en' ? 'Choose separately how your Explore activity may be used.' : 'Bạn chọn riêng cách sử dụng hoạt động trên trang Khám phá.'}</p>
                </div>
              </div>

              {loadingRecommendationConsent || !recommendationConsent ? (
                <p>{locale === 'en' ? 'Loading settings…' : 'Đang tải lựa chọn…'}</p>
              ) : (
                <div className="profile-form">
                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                    <input
                      type="checkbox"
                      checked={recommendationConsent.personalization_enabled}
                      disabled={savingRecommendationConsent}
                      onChange={(event) => void saveRecommendationConsent({ personalization_enabled: event.target.checked })}
                      style={{ width: 18, marginTop: 3 }}
                    />
                    <span>
                      <strong>{locale === 'en' ? 'Use my activity for personal recommendations' : 'Dùng hoạt động của tôi để cá nhân hóa gợi ý'}</strong>
                      <small style={{ display: 'block' }}>
                        {locale === 'en'
                          ? 'Allow your Explore selections to shape future rankings. You can turn this off at any time.'
                          : 'Cho phép dùng các lượt bạn chọn trong Khám phá để xếp lại gợi ý. Bạn có thể tắt lựa chọn này bất cứ lúc nào.'}
                      </small>
                    </span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                    <input
                      type="checkbox"
                      checked={recommendationConsent.model_training_enabled}
                      disabled={savingRecommendationConsent}
                      onChange={(event) => void saveRecommendationConsent({ model_training_enabled: event.target.checked })}
                      style={{ width: 18, marginTop: 3 }}
                    />
                    <span>
                      <strong>{locale === 'en' ? 'Allow de-identified activity for model training' : 'Cho phép dùng dữ liệu đã giảm nhận diện để huấn luyện mô hình'}</strong>
                      <small style={{ display: 'block' }}>
                        {locale === 'en'
                          ? 'Eligible interaction records may be included in future recommendation-model datasets. Turning this off excludes them from future exports; earlier local exports are not changed automatically.'
                          : 'Các tương tác đủ điều kiện có thể được đưa vào tập huấn luyện mô hình gợi ý. Tắt lựa chọn này sẽ loại lịch sử khỏi lần xuất sau; file đã xuất trước đó không tự thay đổi.'}
                      </small>
                    </span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                    <input
                      type="checkbox"
                      checked={recommendationConsent.admin_history_enabled}
                      disabled={savingRecommendationConsent}
                      onChange={(event) => void saveRecommendationConsent({ admin_history_enabled: event.target.checked })}
                      style={{ width: 18, marginTop: 3 }}
                    />
                    <span>
                      <strong>{locale === 'en' ? 'Allow administrators to view my Explore activity' : 'Cho phép quản trị viên xem lịch sử Khám phá của tôi'}</strong>
                      <small style={{ display: 'block' }}>
                        {locale === 'en'
                          ? 'When enabled, administrators can see the experiences shown, selected, or dismissed in your Explore history. You can revoke this at any time.'
                          : 'Khi bật, quản trị viên có thể xem trải nghiệm đã hiển thị, được chọn hoặc bị bỏ qua trong Khám phá. Bạn có thể tắt quyền này bất cứ lúc nào.'}
                      </small>
                    </span>
                  </label>

                  <small>
                    {locale === 'en'
                      ? 'Turn all three options off to delete interaction history kept by the app. Any previously exported local dataset must be removed separately.'
                      : 'Tắt cả ba lựa chọn sẽ xóa lịch sử tương tác còn lưu trong ứng dụng. Dataset đã xuất trước đó cần được xóa riêng.'}
                  </small>
                </div>
              )}
            </section>
          )}

          {/* Change Password Card */}
          <section className="profile-card-3d">
            <div className="profile-card-title-row">
              <div className="profile-title-icon-box text-amber">
                <Lock size={18} />
              </div>
              <div>
                <h2>{t('profile.changePassTitle')}</h2>
                <p>{t('profile.changePassDesc')}</p>
              </div>
            </div>

            <form onSubmit={savePassword} className="profile-form">
              <div className="field-group-3d">
                <span>{t('profile.currentPassHint')}</span>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder={locale === 'en' ? 'Current password...' : 'Nhập mật khẩu hiện tại...'}
                />
              </div>

              <div className="field-group-3d">
                <span>{t('profile.newPassLabel')}</span>
                <input
                  required
                  minLength={12}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={locale === 'en' ? 'New secure password...' : 'Nhập mật khẩu mới...'}
                />
              </div>

              <button className="btn-secondary-3d" type="submit" disabled={savingPassword}>
                <span>{savingPassword ? t('profile.saving') : t('profile.changePassTitle')}</span>
              </button>
            </form>
          </section>

          <MfaCard />
          <SessionsCard />
          {user?.role === 'traveler' && <ReviewPrompt />}
        </div>

        {/* Right Column: Saved Itineraries Gallery */}
        {user?.role === 'traveler' && <section className="profile-trips-col">
          <div className="trips-section-header">
            <div>
              <span className="results-sub">{locale === 'en' ? 'YOUR COLLECTION' : 'BỘ SƯU TẬP CỦA BẠN'}</span>
              <h2 className="trips-main-title">{t('profile.savedTrips')}</h2>
            </div>
            {trips.length >= 2 && (
              <Link to="/compare" className="btn-compare-shortcut">
                <GitCompare size={15} />
                <span>{t('nav.compare')}</span>
              </Link>
            )}
          </div>

          {trips.length > 0 ? (
            <div className="trips-gallery-grid">
              {trips.map((trip) => (
                <TiltCard3D key={trip.id} maxTilt={6} className="trip-history-card">
                  <div className="trip-card-top">
                    <span className="trip-date-badge">
                      <Calendar size={13} className="text-emerald" />
                      {trip.planned_date || (locale === 'en' ? 'Date unassigned' : 'Chưa ấn định ngày')}
                    </span>
                    <span className="trip-status-chip">
                      {trip.status === 'confirmed' ? (locale === 'en' ? 'Confirmed' : 'Đã xác nhận') : (locale === 'en' ? 'Optimized Draft' : 'Bản nháp tối ưu')}
                    </span>
                  </div>

                  <h3 className="trip-card-id">{locale === 'en' ? 'Itinerary' : 'Lịch trình'} #{trip.id.slice(0, 8)}</h3>

                  <div className="trip-card-cost">
                    <small>{locale === 'en' ? 'Estimated cost' : 'Chi phí dự kiến'}</small>
                    <strong>{trip.estimated_cost_vnd.toLocaleString('vi-VN')}₫</strong>
                  </div>

                  <div className="trip-card-actions">
                    <Link to={`/itinerary/${trip.id}`} className="btn-view-trip">
                      <span>{locale === 'en' ? 'View Details' : 'Xem chi tiết'}</span>
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                </TiltCard3D>
              ))}
            </div>
          ) : (
            <div className="empty-trips-box">
              <Route size={36} className="text-slate-500 mb-3" />
              <h3>{locale === 'en' ? 'No saved itineraries yet' : 'Chưa có lịch trình nào được lưu'}</h3>
              <p>
                {locale === 'en'
                  ? 'Start by creating your first itinerary to discover unique time-slot aware experiences across Saigon.'
                  : 'Hãy bắt đầu tạo lịch trình đầu tiên để khám phá các khung giờ trải nghiệm độc đáo tại Sài Gòn.'}
              </p>
              <Link to="/planner" className="btn-primary-3d btn-sm">
                <span>{t('planner.submitBtn')}</span>
                <ArrowRight size={14} />
              </Link>
            </div>
          )}
        </section>}
      </div>
    </div>
  )
}
