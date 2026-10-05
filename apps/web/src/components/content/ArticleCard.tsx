import { Link } from 'react-router-dom'
import type { ArticleSummary } from '../../types'

export function ArticleCard({ article }: { article: ArticleSummary }) {
  return (
    <Link to={`/guides/${article.slug}`} className="article-card">
      {article.cover_url ? <img src={article.cover_url} alt="" loading="lazy" /> : <img alt="" src="/logo.png" style={{ objectFit: 'contain', padding: 24 }} />}
      <div className="article-card-body">
        <span className="article-card-category">{article.category}</span>
        <h3>{article.title}</h3>
        {article.excerpt && <p>{article.excerpt}</p>}
      </div>
    </Link>
  )
}
