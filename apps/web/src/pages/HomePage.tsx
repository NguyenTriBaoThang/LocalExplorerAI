import {
  ArrowRight,
  ArrowUpRight,
  Sparkles,
  Compass,
  CalendarCheck,
  Navigation,
  ShieldCheck,
  Clock,
  Coins,
  MapPin,
  Bot,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { CityHero3D } from '../components/3d/CityHero3D'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { useTranslation } from '../i18n'
import { HomeContentSections } from '../components/content/HomeContentSections'

export function HomePage() {
  const { t, locale } = useTranslation()

  const categories = [
    {
      id: 'food',
      name: t('home.catFood'),
      icon: '🍜',
      desc: t('home.catFoodDesc'),
    },
    {
      id: 'handicraft',
      name: t('home.catCraft'),
      icon: '🎨',
      desc: t('home.catCraftDesc'),
    },
    {
      id: 'culture',
      name: t('home.catCulture'),
      icon: '🏛️',
      desc: t('home.catCultureDesc'),
    },
    {
      id: 'nature',
      name: t('home.catNature'),
      icon: '🌿',
      desc: t('home.catNatureDesc'),
    },
  ]

  const highlights = [
    {
      number: '01',
      title: t('home.hl1Title'),
      copy: t('home.hl1Copy'),
      icon: CalendarCheck,
    },
    {
      number: '02',
      title: t('home.hl2Title'),
      copy: t('home.hl2Copy'),
      icon: Navigation,
    },
    {
      number: '03',
      title: t('home.hl3Title'),
      copy: t('home.hl3Copy'),
      icon: ShieldCheck,
    },
  ]

  const curatedExperiences = [
    {
      title: locale === 'vi' ? 'Dinh Độc Lập & Dấu ấn Lịch sử' : 'Independence Palace & Heritage Tour',
      district: locale === 'vi' ? 'Quận 1' : 'District 1',
      category: t('explore.intentCulture'),
      duration: `90 ${t('explore.minutes')}`,
      price: locale === 'vi' ? '40.000₫' : '40,000 VND',
      time: '08:00 - 16:30',
      icon: '🏛️',
      imageUrl: 'https://images.unsplash.com/photo-1583417319070-4a69db38a482?auto=format&fit=crop&w=800&q=80',
    },
    {
      title: locale === 'vi' ? 'Bảo tàng Chứng tích Chiến tranh' : 'War Remnants Museum',
      district: locale === 'vi' ? 'Quận 3' : 'District 3',
      category: t('explore.intentCulture'),
      duration: `90 ${t('explore.minutes')}`,
      price: locale === 'vi' ? '40.000₫' : '40,000 VND',
      time: '07:30 - 17:30',
      icon: '🏛️',
      imageUrl: 'https://images.unsplash.com/photo-1596401057633-54a8fe8ef647?auto=format&fit=crop&w=800&q=80',
    },
    {
      title: locale === 'vi' ? 'Thuyền hoàng hôn Bến Bạch Đằng' : 'Saigon River Sunset Breeze',
      district: locale === 'vi' ? 'Bến Bạch Đằng' : 'Bach Dang Pier',
      category: t('explore.intentNature'),
      duration: `75 ${t('explore.minutes')}`,
      price: locale === 'vi' ? '150.000₫' : '150,000 VND',
      time: '16:30 - 18:00',
      icon: '⛵',
      imageUrl: 'https://images.unsplash.com/photo-1559592413-7cec4d0cae2b?auto=format&fit=crop&w=800&q=80',
    },
    {
      title: locale === 'vi' ? 'Bàn Xoay Gốm Mộc Sài Gòn' : 'Saigon Artisan Ceramic Wheel',
      district: locale === 'vi' ? 'Quận 3' : 'District 3',
      category: t('explore.intentCraft'),
      duration: `90 ${t('explore.minutes')}`,
      price: locale === 'vi' ? '180.000₫' : '180,000 VND',
      time: '10:00 - 11:30',
      icon: '🏺',
      imageUrl: 'https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?auto=format&fit=crop&w=800&q=80',
    },
  ]

  return (
    <div className="home-container-3d">
      {/* Hero Section */}
      <section className="home-hero-3d">
        <div className="hero-content-col">
          <div className="hero-badge-wrap">
            <span className="hero-badge-glow" />
            <span className="hero-badge-text">
              <Compass size={14} className="text-emerald animate-spin-slow" />
              {t('home.badge')}
            </span>
          </div>

          <h1 className="hero-heading-3d">
            {t('home.heading1')} <br />
            <span className="gradient-text-emerald">{t('home.headingHighlight')}</span> <span className="nowrap">{t('home.heading2')}</span>
          </h1>

          <p className="hero-description-3d">
            {t('home.desc')}
          </p>

          <div className="hero-cta-group">
            <Link className="btn-primary-3d" to="/chat">
              <Bot size={18} />
              <span>{t('home.ctaChat')}</span>
            </Link>
            <Link className="btn-secondary-3d" to="/explore">
              <span>{t('home.ctaExplore')}</span>
              <ArrowUpRight size={17} />
            </Link>
          </div>

          <div className="hero-features-strip">
            <div className="feature-pill">
              <Sparkles size={14} className="text-amber" />
              <span>{locale === 'vi' ? 'Planner Heuristic 0ms' : '0ms Heuristic Solver'}</span>
            </div>
            <div className="feature-pill">
              <Clock size={14} className="text-emerald" />
              <span>{locale === 'vi' ? 'Khung giờ Slot thực' : 'Slot-Aware Realtime'}</span>
            </div>
            <div className="feature-pill">
              <Coins size={14} className="text-cyan" />
              <span>{locale === 'vi' ? 'Tối ưu hóa ngân sách' : 'Budget-Optimized'}</span>
            </div>
          </div>
        </div>

        {/* 3D WebGL Saigon Cityscape Canvas */}
        <div className="hero-visual-col">
          <CityHero3D />
        </div>
      </section>

      {/* Banners, collections and guides published from the admin portal */}
      <HomeContentSections />

      {/* Quick Vibe Categories */}
      <section className="vibe-section-3d">
        <div className="section-header-center">
          <span className="section-eyebrow">
            {locale === 'vi' ? 'CHỌN THEO NHỊP ĐI' : 'CURATED VIBES'}
          </span>
          <h2 className="section-title-3d">{t('home.categoriesTitle')}</h2>
          <p className="section-subtitle-3d">
            {locale === 'vi'
              ? 'Khám phá các hoạt động đặc trưng theo phong cách và sở thích riêng của bạn tại Sài Gòn.'
              : 'Discover signature local activities curated by style and tempo across Ho Chi Minh City.'}
          </p>
        </div>

        <div className="vibe-grid-3d">
          {categories.map((cat) => (
            <Link to={`/explore?intent=${cat.id}`} key={cat.id} className="vibe-card-link">
              <TiltCard3D maxTilt={10} className="vibe-card-3d">
                <div className="vibe-icon-wrap">
                  <span className="vibe-emoji">{cat.icon}</span>
                </div>
                <h3 className="vibe-title">{cat.name}</h3>
                <p className="vibe-desc">{cat.desc}</p>
                <div className="vibe-action">
                  <span>{locale === 'vi' ? 'Khám phá ngay' : 'Explore now'}</span>
                  <ArrowRight size={15} />
                </div>
              </TiltCard3D>
            </Link>
          ))}
        </div>
      </section>

      {/* Curated Experiences Showcase */}
      <section className="showcase-section-3d">
        <div className="section-header-split">
          <div>
            <span className="section-eyebrow">
              {locale === 'vi' ? 'GỢI Ý ĐẶC SẮC' : 'FEATURED PICKS'}
            </span>
            <h2 className="section-title-3d">{t('home.curatedTitle')}</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '13.5px', marginTop: '4px' }}>
              {t('home.curatedSubtitle')}
            </p>
          </div>
          <Link to="/explore" className="view-all-link">
            <span>{t('home.viewAll')}</span>
            <ArrowRight size={16} />
          </Link>
        </div>

        <div className="showcase-grid-3d">
          {curatedExperiences.map((item, idx) => (
            <Link to="/explore" key={idx} className="showcase-card-link">
              <TiltCard3D maxTilt={6} className="showcase-card-3d">
                <div className="showcase-photo-box">
                  <img src={item.imageUrl} alt={item.title} className="showcase-photo-img" loading="lazy" />
                  <div className="showcase-photo-gradient" />
                  <div className="showcase-top-badges">
                    <span className="showcase-tag">
                      <span>{item.icon}</span> {item.category}
                    </span>
                    <span className="showcase-action-circle">
                      <ArrowUpRight size={14} />
                    </span>
                  </div>
                  <div className="showcase-bottom-badges">
                    <span className="showcase-district-badge">
                      <MapPin size={11} /> {item.district}
                    </span>
                    <span className="showcase-price-badge">{item.price}</span>
                  </div>
                </div>
                <div className="showcase-body">
                  <h3 className="showcase-title">{item.title}</h3>
                  <div className="showcase-footer">
                    <div className="showcase-meta">
                      <Clock size={12} className="text-amber" />
                      <span>{item.duration}</span>
                    </div>
                    <div className="slot-badge">
                      <span className="slot-dot" />
                      <span>{item.time}</span>
                    </div>
                  </div>
                </div>
              </TiltCard3D>
            </Link>
          ))}
        </div>
      </section>

      {/* Core Philosophy & Comparison */}
      <section className="philosophy-section-3d">
        <div className="philosophy-card-main">
          <div className="section-header-center">
            <span className="section-eyebrow">
              {locale === 'vi' ? 'VÌ SAO CHỌN LOCAL EXPLORER AI?' : 'SMART CITY ADVANTAGE'}
            </span>
            <h2 className="section-title-3d">{t('home.whyTitle')}</h2>
            <p className="section-subtitle-3d">
              {locale === 'vi'
                ? 'Không còn cảnh đến nơi phát hiện workshop đã kín chỗ hay quán nghỉ sớm.'
                : 'Say goodbye to arriving at closed workshops, sold-out slots, or rushing through rush-hour traffic.'}
            </p>
          </div>

          <div className="highlights-grid-3d">
            {highlights.map((item) => {
              const Icon = item.icon
              return (
                <TiltCard3D key={item.number} maxTilt={6} className="highlight-box-3d">
                  <div className="highlight-icon-pill">
                    <Icon size={24} className="text-emerald" />
                  </div>
                  <span className="highlight-num">{item.number}</span>
                  <h3 className="highlight-title">{item.title}</h3>
                  <p className="highlight-copy">{item.copy}</p>
                </TiltCard3D>
              )
            })}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="cta-banner-3d">
        <div className="cta-banner-glow" />
        <div className="cta-banner-inner">
          <div className="cta-text-side">
            <span className="section-eyebrow text-emerald-300">
              {locale === 'vi' ? 'SÀI GÒN ĐANG CHỜ BẠN' : 'SAIGON IS CALLING'}
            </span>
            <h2 className="cta-heading-3d">
              {t('home.ctaBannerTitle')}
            </h2>
            <p className="cta-sub-3d">
              {t('home.ctaBannerDesc')}
            </p>
          </div>
          <div className="cta-action-side">
            <Link to="/planner" className="btn-cta-hero">
              <span>{t('home.ctaBannerBtn')}</span>
              <ArrowRight size={20} />
            </Link>
            <span className="cta-guarantee">
              {locale === 'vi'
                ? 'Hoàn toàn miễn phí · Dữ liệu mô phỏng minh bạch'
                : '100% Free · Transparent Feasible Data'}
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}
