import { useEffect } from 'react'
import { PORTAL_URL } from '../portalUrl'
import { getLocale } from '../i18n'

/** The admin and partner screens moved to the portal app: send staff there instead of rendering them in the traveler web. */
export function PortalRedirect({ area }: { area: 'admin' | 'partner' }) {
  const target = `${PORTAL_URL}/${area}?lang=${getLocale()}`
  useEffect(() => { window.location.replace(target) }, [target])
  return (
    <div className="page-wrap page-loading-3d">
      <span className="loader-orbit" />
      <p>Đang chuyển tới Portal {area === 'admin' ? 'Quản trị' : 'Đối tác'}…</p>
      <p><a href={target}>Bấm vào đây nếu trang không tự chuyển</a></p>
    </div>
  )
}
