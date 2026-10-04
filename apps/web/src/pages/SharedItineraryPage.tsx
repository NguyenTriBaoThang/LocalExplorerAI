import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getSharedItinerary, claimTicket } from '../api/client'
import { useAuth } from '../auth'
import { MapAdapter, LEG_COLORS, type MapPoint } from '../components/map/MapAdapter'
import type { Itinerary } from '../types'

export function SharedItineraryPage() {
  const { token: rawToken = '' } = useParams()
  const token = rawToken.split('[')[0].split('(')[0].replace(/[\]\)]+$/, '').trim()

  const { user, setUser, refresh } = useAuth()
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedStopId, setSelectedStopId] = useState<string | undefined>()

  // Claim form state
  const [claimEmail, setClaimEmail] = useState('')
  const [claimPassword, setClaimPassword] = useState('')
  const [claimName, setClaimName] = useState('')
  const [claimLoading, setClaimLoading] = useState(false)
  const [claimSuccess, setClaimSuccess] = useState(false)
  const [claimError, setClaimError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setLoading(true)
    getSharedItinerary(token)
      .then((data) => {
        setItinerary(data)
        setError('')
      })
      .catch(() => {
        setError('Mã vé không tồn tại hoặc liên kết chia sẻ đã hết hạn.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [token])

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  const scrollToMap = () => {
    const el = document.getElementById('ticket-map')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  const handleClaim = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!claimEmail || !claimPassword) {
      setClaimError('Vui lòng điền đầy đủ email và mật khẩu.')
      return
    }
    if (claimPassword.length < 8) {
      setClaimError('Mật khẩu tối thiểu 8 ký tự.')
      return
    }

    try {
      setClaimLoading(true)
      setClaimError('')
      const claimedUser = await claimTicket({
        share_token: token,
        email: claimEmail,
        password: claimPassword,
        display_name: claimName || undefined,
      })
      setUser(claimedUser)
      await refresh()
      setClaimSuccess(true)
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || 'Không thể liên kết tài khoản. Vui lòng thử lại.'
      setClaimError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setClaimLoading(false)
    }
  }

  const mapPoints: MapPoint[] = useMemo(() => {
    if (!itinerary?.stops) return []
    return itinerary.stops
      .filter((s) => s.poi && s.poi.latitude && s.poi.longitude)
      .map((s, idx) => ({
        id: s.id || `stop-${idx}`,
        latitude: s.poi.latitude,
        longitude: s.poi.longitude,
        name: s.name,
        category: s.category || s.poi.category,
        number: s.position || idx + 1,
      }))
  }, [itinerary])

  if (loading) {
    return (
      <div className="page-wrap" style={{ textAlign: 'center', paddingTop: 80 }}>
        <div className="loader-orbit" style={{ margin: '0 auto 20px' }} />
        <h2>Đang kiểm tra & kích hoạt Vé Smart Travel Pass…</h2>
        <p style={{ color: '#94a3b8' }}>Mã vé: {token}</p>
      </div>
    )
  }

  if (error || !itinerary) {
    return (
      <div className="page-wrap" style={{ textAlign: 'center', paddingTop: 60, maxWidth: 600, margin: '0 auto' }}>
        <div style={{ fontSize: 56, marginBottom: 16 }}>🎟️</div>
        <h1 style={{ fontSize: 24, marginBottom: 12 }}>{error || 'Không tìm thấy vé'}</h1>
        <p style={{ color: '#94a3b8', marginBottom: 24 }}>
          Mã vé này có thể đã hết hiệu lực hoặc chưa được tạo đúng. Bạn có thể lên lịch trình mới ngay lập tức.
        </p>
        <Link to="/planner" className="btn-primary" style={{ display: 'inline-block', padding: '10px 24px' }}>
          Tự thiết kế lịch trình mới
        </Link>
      </div>
    )
  }

  const startDate = itinerary.start_at ? new Date(itinerary.start_at) : new Date()

  return (
    <div className="page-wrap" style={{ maxWidth: 960, margin: '0 auto', padding: '32px 16px 80px' }}>
      {/* Ticket Header Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(59, 130, 246, 0.15) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: 20,
          padding: '24px 28px',
          marginBottom: 24,
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 12px 30px rgba(0, 0, 0, 0.25)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(16, 185, 129, 0.2)', padding: '4px 12px', borderRadius: 999, marginBottom: 12 }}>
              <span style={{ fontSize: 16 }}>🎫</span>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1, color: '#34d399', textTransform: 'uppercase' }}>
                Smart Travel Pass
              </span>
              <span style={{ color: '#94a3b8' }}>·</span>
              <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>{token}</span>
            </div>
            <h1 style={{ fontSize: 28, fontWeight: 800, margin: '0 0 8px', color: '#f8fafc' }}>
              Vé Khám Phá Điện Tử Sài Gòn
            </h1>
            <p style={{ color: '#94a3b8', margin: 0, fontSize: 14 }}>
              Lịch trình cá nhân hóa đồng bộ trực tiếp từ trợ lý Zalo Bot Local Explorer
            </p>
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              onClick={handleCopyLink}
              type="button"
              className="btn-secondary"
              style={{
                padding: '8px 16px',
                borderRadius: 10,
                fontSize: 13,
                cursor: 'pointer',
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.2)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>{copied ? '✅ Đã chép link' : '🔗 Chia sẻ vé'}</span>
            </button>
            <button
              type="button"
              onClick={scrollToMap}
              className="btn-primary"
              style={{
                padding: '8px 16px',
                borderRadius: 10,
                fontSize: 13,
                border: 'none',
                cursor: 'pointer',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: '#fff',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              🗺️ Xem Bản Đồ Lộ Trình
            </button>
          </div>
        </div>

        {/* Overview Stats Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 16,
            marginTop: 24,
            paddingTop: 20,
            borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Trạng thái</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#34d399', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#34d399' }} />
              Đã xác nhận
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Điểm dừng</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>
              {itinerary.stops.length} trải nghiệm
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Dự toán chi phí</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#38bdf8' }}>
              {itinerary.estimated_cost_vnd.toLocaleString('vi-VN')} ₫
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Thời gian di chuyển</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>
              ~{itinerary.total_travel_min} phút
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Thời gian khởi hành</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#f8fafc' }}>
              {startDate.toLocaleDateString('vi-VN')} · {startDate.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        </div>
      </div>

      {/* Claim / Account Conversion Card */}
      {!user && !claimSuccess ? (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: 16,
            padding: '24px',
            marginBottom: 28,
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 20 }}>✨</span>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#60a5fa' }}>
              Lưu vé vào tài khoản để mở mọi lúc
            </h3>
          </div>
          <p style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 16px', lineHeight: 1.5 }}>
            Vé này đang ở chế độ xem trực tiếp. Tạo mật khẩu nhanh (không cần xác minh rườm rà) để lưu vĩnh viễn vào tài khoản của bạn, cập nhật thời gian thực và lưu lại kỉ niệm sau chuyến đi!
          </p>

          {claimError && (
            <div style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: 8, padding: '8px 12px', color: '#f87171', fontSize: 13, marginBottom: 12 }}>
              {claimError}
            </div>
          )}

          <form onSubmit={handleClaim} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, alignItems: 'flex-end' }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#cbd5e1', marginBottom: 4 }}>Email của bạn *</label>
              <input
                type="email"
                required
                placeholder="vidu@gmail.com"
                value={claimEmail}
                onChange={(e) => setClaimEmail(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: 13 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#cbd5e1', marginBottom: 4 }}>Mật khẩu mong muốn * (≥ 8 ký tự)</label>
              <input
                type="password"
                required
                placeholder="Tối thiểu 8 ký tự"
                value={claimPassword}
                onChange={(e) => setClaimPassword(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: 13 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#cbd5e1', marginBottom: 4 }}>Tên của bạn (Tùy chọn)</label>
              <input
                type="text"
                placeholder="Tên du khách"
                value={claimName}
                onChange={(e) => setClaimName(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: 13 }}
              />
            </div>

            <div>
              <button
                type="submit"
                disabled={claimLoading}
                style={{
                  width: '100%',
                  padding: '10px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: claimLoading ? 'wait' : 'pointer',
                  opacity: claimLoading ? 0.7 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                }}
              >
                {claimLoading ? 'Đang tạo tài khoản...' : '💾 Lưu Vé Vào Tài Khoản'}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div
          style={{
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: 12,
            padding: '14px 20px',
            marginBottom: 24,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>🎉</span>
            <div>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#34d399' }}>
                Vé đã được liên kết với tài khoản: {user?.display_name || user?.email}
              </span>
              <p style={{ margin: 0, fontSize: 12, color: '#94a3b8' }}>
                Bạn có thể mở và quản lý lịch trình này mọi lúc trong mục Chuyến đi của tôi.
              </p>
            </div>
          </div>
          <Link to="/planner" style={{ fontSize: 13, color: '#60a5fa', textDecoration: 'none', fontWeight: 600 }}>
            Xem danh sách hành trình →
          </Link>
        </div>
      )}

      {/* Embedded Map Section Dedicated to this Ticket */}
      <div id="ticket-map" style={{ marginBottom: 36 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>🗺️</span> Bản đồ hành trình chuyên biệt ({itinerary.stops.length} điểm dừng)
          </h2>
          <span style={{ fontSize: 12, color: '#38bdf8', fontWeight: 600 }}>
            ● Lộ trình tối ưu hoá theo thời gian thực
          </span>
        </div>

        <div style={{ borderRadius: 16, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.15)', boxShadow: '0 8px 30px rgba(0,0,0,0.35)' }}>
          <MapAdapter
            points={mapPoints}
            routes={(itinerary?.routes ?? []).filter((r) => r.geometry && r.geometry.length > 1).map((r, i) => ({ id: `route-${i}`, coordinates: r.geometry!, color: LEG_COLORS[i % LEG_COLORS.length] }))}
            selectedId={selectedStopId}
            onSelect={(id: string) => setSelectedStopId(id)}
            className="w-full h-[460px]"
          />
        </div>
      </div>

      {/* Stops Timeline */}
      <div style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>📍</span> Chi tiết các điểm dừng trong hành trình
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {itinerary.stops.map((stop, index) => {
            const stopStart = new Date(stop.start_at)
            const stopEnd = new Date(stop.end_at)
            const routeLeg = itinerary.routes && itinerary.routes[index - 1]
            const isSelected = selectedStopId === (stop.id || `stop-${index}`)

            return (
              <div key={stop.id || index}>
                {/* Route Leg connector between stops */}
                {index > 0 && routeLeg && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '8px 24px',
                      color: '#94a3b8',
                      fontSize: 12,
                    }}
                  >
                    <div style={{ width: 2, height: 24, background: 'rgba(255,255,255,0.15)', margin: '0 16px' }} />
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(255,255,255,0.05)', padding: '2px 10px', borderRadius: 12 }}>
                      🚗 Di chuyển ~{routeLeg.duration_min} phút ({Math.round(routeLeg.distance_m / 100) / 10} km)
                    </span>
                  </div>
                )}

                {/* Stop Card */}
                <div
                  onClick={() => setSelectedStopId(stop.id || `stop-${index}`)}
                  style={{
                    background: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'rgba(30, 41, 59, 0.7)',
                    border: isSelected ? '1px solid #3b82f6' : '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 16,
                    padding: '20px 24px',
                    display: 'flex',
                    gap: 16,
                    alignItems: 'flex-start',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.2)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {/* Position Badge */}
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 12,
                      background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 800,
                      fontSize: 18,
                      flexShrink: 0,
                    }}
                  >
                    {stop.position || index + 1}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 6 }}>
                      <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#f8fafc' }}>
                        {stop.name}
                      </h3>
                      {stop.category && (
                        <span
                          style={{
                            fontSize: 11,
                            padding: '3px 10px',
                            borderRadius: 999,
                            background: 'rgba(59, 130, 246, 0.15)',
                            color: '#60a5fa',
                            fontWeight: 600,
                          }}
                        >
                          {stop.category}
                        </span>
                      )}
                    </div>

                    {stop.poi && stop.poi.address && (
                      <p style={{ margin: '0 0 10px', fontSize: 13, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>📍</span> {stop.poi.address}
                      </p>
                    )}

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: 12, color: '#cbd5e1' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span>🕒</span> {stopStart.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} - {stopEnd.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} ({stop.duration_min} phút)
                      </span>

                      <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#34d399', fontWeight: 600 }}>
                        <span>💵</span> {stop.cost_vnd ? `${stop.cost_vnd.toLocaleString('vi-VN')} ₫` : 'Miễn phí'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
