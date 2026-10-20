import { ArrowRight, Compass, MapPin, ShieldCheck, Sparkles, Cpu, Clock3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { useTranslation } from '../i18n'

export function AboutPage() {
  const { t, locale } = useTranslation()

  const concepts = [
    {
      num: '01',
      kicker: locale === 'en' ? 'PHYSICAL VENUES' : 'NƠI CHỐN VẬT LÝ',
      title: 'POI (Point of Interest)',
      desc: locale === 'en'
        ? 'Geographic map coordinates (Latitude, Longitude). The spatial foundation anchoring all real-world experiences.'
        : 'Điểm tọa độ địa lý trên bản đồ (Latitude, Longitude). Đây là nền tảng không gian để neo giữ các hoạt động thực tế.',
      icon: MapPin,
      color: 'text-emerald-500',
      tags: locale === 'en' ? ['Coordinates', 'Address', 'District'] : ['Tọa độ', 'Địa chỉ', 'Khu vực'],
    },
    {
      num: '02',
      kicker: locale === 'en' ? 'SPECIFIC ACTIVITY' : 'HOẠT ĐỘNG CỤ THỂ',
      title: locale === 'en' ? 'Experience' : 'Trải nghiệm',
      desc: locale === 'en'
        ? 'The concrete activity you participate in: pottery wheel, heritage sock coffee tasting, handmade paper craft. Bound to duration and cost.'
        : 'Hành động cụ thể bạn tham gia tại địa điểm: vẽ gốm, nếm cà phê bít tất, làm giấy dó. Gắn liền với thời lượng và chi phí.',
      icon: Sparkles,
      color: 'text-amber-500',
      tags: locale === 'en' ? ['Duration', 'Budget', 'Purpose'] : ['Thời lượng', 'Ngân sách', 'Mục đích'],
    },
    {
      num: '03',
      kicker: locale === 'en' ? 'FEASIBLE TIMING' : 'THỜI ĐIỂM KHẢ THI',
      title: locale === 'en' ? 'Timeslot (Slot)' : 'Slot (Khung giờ)',
      desc: locale === 'en'
        ? 'Discrete time windows with specific capacity and live vacancy. Decides whether you can actually participate upon arrival.'
        : 'Khung giờ độc lập có sức chứa riêng và trạng thái chỗ trống. Quyết định trực tiếp bạn có thể tham gia vào lúc bạn đến hay không.',
      icon: Clock3,
      color: 'text-cyan-500',
      tags: locale === 'en' ? ['Start Time', 'Capacity', 'Verification'] : ['Giờ bắt đầu', 'Sức chứa', 'Xác nhận'],
    },
    {
      num: '04',
      kicker: locale === 'en' ? 'HOLISTIC OPTIMIZATION' : 'TỐI ƯU HÓA TỔNG THỂ',
      title: locale === 'en' ? '3D Itinerary' : 'Lịch trình 3D',
      desc: locale === 'en'
        ? 'A sequence of experiences organized by deterministic Heuristic algorithms, balancing inter-district travel times and group energy.'
        : 'Chuỗi trải nghiệm được thuật toán Heuristic sắp xếp khoa học, cân đối thời gian di chuyển giữa các quận và sức bền của nhóm.',
      icon: Compass,
      color: 'text-rose-500',
      tags: locale === 'en' ? ['Heuristic', 'Transit Route', 'Distance Matrix'] : ['Heuristic', 'Lộ trình', 'Ma trận cự ly'],
    },
  ]

  return (
    <div className="about-page-3d page-wrap">
      {/* Hero Section */}
      <div className="about-hero-3d">
        <span className="eyebrow-3d">
          <span className="eyebrow-dot" /> {t('about.eyebrow')}
        </span>
        <h1 className="about-hero-title">
          {t('about.heroTitle1')} <br />
          <em>{t('about.heroTitle2')}</em>
        </h1>
        <p className="about-hero-lead">
          {t('about.heroLead')}
        </p>
      </div>

      {/* Core Architectural Model Grid */}
      <div className="about-concept-section">
        <div className="section-header-center">
          <span className="section-eyebrow">{t('about.dataModelEyebrow')}</span>
          <h2 className="section-title-3d">{t('about.dataModelTitle')}</h2>
        </div>

        <div className="concept-grid-3d">
          {concepts.map((item) => {
            const Icon = item.icon
            return (
              <TiltCard3D key={item.num} maxTilt={8} className="concept-card-3d">
                <div className="concept-card-top">
                  <div className={`concept-icon-box ${item.color}`}>
                    <Icon size={24} />
                  </div>
                  <span className="concept-step-badge">{item.num}</span>
                </div>

                <small className="concept-kicker">{item.kicker}</small>
                <h3 className="concept-title">{item.title}</h3>
                <p className="concept-desc">{item.desc}</p>

                <div className="concept-tags-row">
                  {item.tags.map((t) => (
                    <span key={t} className="concept-mini-tag">
                      {t}
                    </span>
                  ))}
                </div>
              </TiltCard3D>
            )
          })}
        </div>
      </div>

      {/* Engineering Principles */}
      <div className="engineering-section-3d">
        <div className="engineering-card-3d">
          <div className="eng-icon-box">
            <Cpu size={32} className="text-emerald" />
          </div>
          <div className="eng-content">
            <span className="results-sub">{t('about.techPhilosophy')}</span>
            <h3>{t('about.heuristicTitle')}</h3>
            <p>{t('about.heuristicDesc')}</p>
          </div>
        </div>

        <div className="engineering-card-3d">
          <div className="eng-icon-box">
            <ShieldCheck size={32} className="text-amber" />
          </div>
          <div className="eng-content">
            <span className="results-sub">{t('about.transparencyEyebrow')}</span>
            <h3>{t('about.certaintyTitle')}</h3>
            <p>{t('about.certaintyDesc')}</p>
          </div>
        </div>
      </div>

      <section className="mx-auto my-8 max-w-4xl rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 text-sm text-[var(--text-muted)]">
        <h2 className="mb-2 font-semibold text-[var(--text-main)]">
          {locale === 'en' ? 'Data acknowledgements' : 'Ghi nhận nguồn dữ liệu'}
        </h2>
        <p>
          {locale === 'en'
            ? 'Weather data provided by Open-Meteo (CC BY 4.0). Air-quality data from CAMS ENSEMBLE, distributed through Open-Meteo.'
            : 'Dữ liệu thời tiết do Open-Meteo cung cấp (CC BY 4.0). Dữ liệu chất lượng không khí từ CAMS ENSEMBLE, phân phối qua Open-Meteo.'}
        </p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <a className="underline" href="https://open-meteo.com/en/docs" target="_blank" rel="noreferrer">
            {locale === 'en' ? 'Weather data details' : 'Thông tin dữ liệu thời tiết'}
          </a>
          <a className="underline" href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noreferrer">
            {locale === 'en' ? 'Air-quality data details' : 'Thông tin dữ liệu chất lượng không khí'}
          </a>
        </div>
      </section>

      {/* CTA Box */}
      <div className="about-cta-card-3d">
        <div className="about-cta-glow" />
        <div className="about-cta-inner">
          <div className="cta-icon-wrap">
            <Compass size={28} className="text-emerald-300" />
          </div>
          <div>
            <h2>{t('about.ctaTitle')}</h2>
            <p>{t('about.ctaSub')}</p>
          </div>
          <Link to="/planner" className="btn-primary-3d">
            <span>{t('about.ctaBtn')}</span>
            <ArrowRight size={17} />
          </Link>
        </div>
      </div>
    </div>
  )
}
