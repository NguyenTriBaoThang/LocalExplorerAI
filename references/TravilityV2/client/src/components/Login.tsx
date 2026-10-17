import { useState, type FormEvent } from 'react'
import { authRequest } from '../api'

const INPUT = 'mt-1 w-full rounded-lg border border-stone-300 px-3 py-2'

export default function Login({ onToken }: { onToken: (token: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onToken(await authRequest(mode === 'login' ? '/auth/login' : '/auth/register', email, password))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex h-screen items-center justify-center bg-stone-100 px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-3 rounded-2xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold">Travility</h1>
        <label className="block text-sm">
          Email
          <input type="email" required autoComplete="email" className={INPUT}
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm">
          Mật khẩu
          <input type="password" required minLength={8} className={INPUT}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button disabled={busy} className="w-full rounded-lg bg-emerald-700 py-2 text-white disabled:opacity-50">
          {mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}
        </button>
        <button type="button" className="w-full text-sm text-emerald-800"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}
        </button>
      </form>
    </main>
  )
}
