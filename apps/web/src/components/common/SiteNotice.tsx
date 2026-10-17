import { useEffect, useState } from 'react'
import { Megaphone, Wrench } from 'lucide-react'
import { loadSiteConfig, type SiteConfig } from '../../api/siteConfig'
import { useTranslation } from '../../i18n'

/** Announcement and maintenance notice set from the admin portal's "Cài đặt website" page. */
export function SiteNotice() {
  const { locale } = useTranslation()
  const [config, setConfig] = useState<SiteConfig | null>(null)
  useEffect(() => { loadSiteConfig().then(setConfig) }, [])
  if (!config) return null
  const announcement = config.site_announcement.trim()
  if (!announcement && !config.maintenance_mode) return null

  return (
    <div className="site-notice-stack" role="status">
      {config.maintenance_mode && (
        <div className="site-notice site-notice-warn">
          <Wrench size={15} />
          <span>{locale === 'vi' ? 'Hệ thống đang bảo trì, một số tính năng có thể gián đoạn.' : 'The service is under maintenance; some features may be interrupted.'}</span>
        </div>
      )}
      {announcement && (
        <div className="site-notice">
          <Megaphone size={15} />
          <span>{announcement}</span>
        </div>
      )}
    </div>
  )
}
