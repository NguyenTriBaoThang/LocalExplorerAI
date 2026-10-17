import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, MapPin } from 'lucide-react'
import { contentApi } from '../../api/content'
import { useTranslation } from '../../i18n'
import type { HomeContent } from '../../types'
import { ArticleCard } from './ArticleCard'
import './content.css'

/** Banners, place collections and guides published from the admin portal. Renders nothing until there is content. */
export function HomeContentSections() {
  const { locale } = useTranslation()
  const [content, setContent] = useState<HomeContent | null>(null)
  useEffect(() => { contentApi.home().then(setContent).catch(() => setContent(null)) }, [])
  if (!content) return null
  const vi = locale === 'vi'

  return (
    <>
      {content.banners.length > 0 && (
        <section className="content-section">
          <div className="banner-rail">
            {content.banners.map((banner) => {
              const external = /^https:\/\//.test(banner.link_url)
              const inner = (
                <>
                  <img src={banner.image_url} alt="" loading="lazy" />
                  <div className="banner-card-body"><h3>{banner.title}</h3>{banner.subtitle && <p>{banner.subtitle}</p>}</div>
                </>
              )
              return external
                ? <a key={banner.id} href={banner.link_url} className="banner-card" target="_blank" rel="noreferrer">{inner}</a>
                : <Link key={banner.id} to={banner.link_url} className="banner-card">{inner}</Link>
            })}
          </div>
        </section>
      )}

      {content.collections.map((collection) => (
        <section key={collection.id} className="content-section">
          <div className="section-header-split">
            <div>
              <span className="section-eyebrow">{vi ? 'BỘ SƯU TẬP' : 'COLLECTION'}</span>
              <h2 className="section-title-3d">{collection.title}</h2>
              {collection.description && <p style={{ color: 'var(--text-muted)', fontSize: '13.5px', marginTop: '4px' }}>{collection.description}</p>}
            </div>
          </div>
          <div className="content-grid" style={{ marginTop: 20 }}>
            {collection.places.map((place) => (
              <Link key={place.id} to={`/places/${place.id}`} className="place-card">
                <div className="place-card-photo">
                  {place.image_url && <img src={place.image_url} alt={place.name} loading="lazy" />}
                  {place.is_landmark && <span className="place-card-badge">{vi ? 'Danh thắng' : 'Landmark'}</span>}
                </div>
                <div className="place-card-body">
                  <h4>{place.name}</h4>
                  <p><MapPin size={11} style={{ display: 'inline', marginRight: 4 }} />{place.district ?? 'TP. Hồ Chí Minh'}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      ))}

      {content.articles.length > 0 && (
        <section className="content-section">
          <div className="section-header-split">
            <div>
              <span className="section-eyebrow">{vi ? 'CẨM NANG' : 'TRAVEL GUIDES'}</span>
              <h2 className="section-title-3d">{vi ? 'Đọc trước khi đi' : 'Read before you go'}</h2>
            </div>
            <Link to="/guides" className="view-all-link"><span>{vi ? 'Xem tất cả' : 'View all'}</span><ArrowRight size={16} /></Link>
          </div>
          <div className="content-grid" style={{ marginTop: 20 }}>
            {content.articles.slice(0, 3).map((article) => <ArticleCard key={article.id} article={article} />)}
          </div>
        </section>
      )}
    </>
  )
}
