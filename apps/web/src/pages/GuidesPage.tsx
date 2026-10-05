import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarDays, Search } from 'lucide-react'
import { useEntityView } from '../analytics'
import { contentApi } from '../api/content'
import { ArticleCard } from '../components/content/ArticleCard'
import { SimpleMarkdown } from '../components/content/SimpleMarkdown'
import '../components/content/content.css'
import { useTranslation } from '../i18n'
import type { Article, ArticleSummary } from '../types'

export function GuidesPage() {
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const [articles, setArticles] = useState<ArticleSummary[] | null>(null)
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => { contentApi.articles().then(setArticles).catch(() => setArticles([])) }, [])

  const categories = useMemo(() => [...new Set((articles ?? []).map((a) => a.category))], [articles])
  const visible = (articles ?? []).filter((a) => (!category || a.category === category) && (a.title + a.excerpt).toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="content-page-wide">
      <span className="section-eyebrow">{vi ? 'CẨM NANG' : 'TRAVEL GUIDES'}</span>
      <h1 className="content-title">{vi ? 'Cẩm nang khám phá Sài Gòn' : 'Saigon travel guides'}</h1>
      <div className="info-chips">
        <label className="info-chip" style={{ flex: '1 1 260px', maxWidth: 360 }}>
          <Search size={15} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={vi ? 'Tìm bài viết…' : 'Search guides…'}
            style={{ background: 'transparent', border: 0, outline: 'none', color: 'inherit', width: '100%' }} />
        </label>
        {['', ...categories].map((item) => (
          <button key={item || 'all'} type="button" className="info-chip" onClick={() => setCategory(item)}
            style={category === item ? { borderColor: 'var(--border-focus)', color: 'var(--text-main)' } : undefined}>
            {item || (vi ? 'Tất cả' : 'All')}
          </button>
        ))}
      </div>
      {articles === null ? (
        <div className="loading-state-3d"><span className="loader-orbit" /></div>
      ) : visible.length === 0 ? (
        <p className="review-text" style={{ marginTop: 32 }}>{vi ? 'Chưa có bài viết nào.' : 'No guides yet.'}</p>
      ) : (
        <div className="content-grid" style={{ marginTop: 28 }}>{visible.map((article) => <ArticleCard key={article.id} article={article} />)}</div>
      )}
    </div>
  )
}

export function GuidePage() {
  const { slug = '' } = useParams()
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const [article, setArticle] = useState<Article | null>(null)
  const [missing, setMissing] = useState(false)
  useEffect(() => { setArticle(null); setMissing(false); contentApi.article(slug).then(setArticle).catch(() => setMissing(true)) }, [slug])
  useEntityView(article ? { entity_type: 'article', entity_id: article.id } : null)

  return (
    <article className="content-page">
      <Link to="/guides" className="content-back"><ArrowLeft size={15} /> {vi ? 'Cẩm nang' : 'Guides'}</Link>
      {missing && <p className="review-text" style={{ marginTop: 24 }}>{vi ? 'Không tìm thấy bài viết.' : 'Guide not found.'}</p>}
      {!article && !missing && <div className="loading-state-3d"><span className="loader-orbit" /></div>}
      {article && (
        <>
          <h1 className="content-title">{article.title}</h1>
          <div className="content-meta">
            <span className="article-card-category">{article.category}</span>
            {article.published_at && <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><CalendarDays size={14} />{new Date(article.published_at).toLocaleDateString(vi ? 'vi-VN' : 'en-GB')}</span>}
          </div>
          {article.cover_url && <img className="content-cover" src={article.cover_url} alt="" />}
          {article.excerpt && <p className="prose-content" style={{ fontWeight: 500, color: 'var(--text-main)' }}>{article.excerpt}</p>}
          <SimpleMarkdown source={article.body} />
        </>
      )}
    </article>
  )
}
