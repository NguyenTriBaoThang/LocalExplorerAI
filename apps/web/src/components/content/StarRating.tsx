import { Star } from 'lucide-react'

export function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <span className="stars" role="img" aria-label={`${value}/5`}>
      {[1, 2, 3, 4, 5].map((i) => <Star key={i} size={size} fill={i <= Math.round(value) ? 'currentColor' : 'none'} />)}
    </span>
  )
}

export function StarInput({ value, onChange, label }: { value: number; onChange: (value: number) => void; label: string }) {
  return (
    <span role="radiogroup" aria-label={label}>
      {[1, 2, 3, 4, 5].map((i) => (
        <button key={i} type="button" role="radio" aria-checked={value === i} aria-label={`${i}/5`}
          className={`star-button${i <= value ? ' on' : ''}`} onClick={() => onChange(i)}>
          <Star size={22} fill={i <= value ? 'currentColor' : 'none'} />
        </button>
      ))}
    </span>
  )
}
