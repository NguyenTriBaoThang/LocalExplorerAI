import { useEffect } from 'react'

/** Where the staff portal (admin and partner areas) lives. Set VITE_PORTAL_URL when it is not on the default dev address. */
const PORTAL_URL = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_PORTAL_URL || 'http://localhost:5174').replace(/\/$/, '')

/** The admin and partner screens moved to the portal app: send staff there instead of rendering them in the traveler web. */
export function PortalRedirect({ area }: { area: 'admin' | 'partner' }) {
  const target = `${PORTAL_URL}/${area}`
  useEffect(() => { window.location.replace(target) }, [target])
  return (
    <div className="page-wrap page-loading-3d">
      <span className="loader-orbit" />
      <p>Đang chuyển tới Portal {area === 'admin' ? 'Quản trị' : 'Đối tác'}…</p>
      <p><a href={target}>Bấm vào đây nếu trang không tự chuyển</a></p>
    </div>
  )
}
