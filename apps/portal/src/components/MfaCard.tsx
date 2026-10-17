import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Copy, Download, KeyRound, ShieldCheck, ShieldOff } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { authApi, errorMessage } from '../lib/api'
import type { MfaSetup, MfaStatus } from '../lib/types'
import { Alert, Badge, Button, Card, CardHeader, Field, Input, Spinner, useToast } from './ui'

type Mode = 'idle' | 'setup' | 'codes' | 'regenerate' | 'disable'

/** Two-factor authentication (TOTP) enrolment and management. */
export function MfaCard({ onEnabled }: { onEnabled?: () => void }) {
  const { refresh } = useAuth()
  const toast = useToast()
  const [status, setStatus] = useState<MfaStatus | null>(null)
  const [mode, setMode] = useState<Mode>('idle')
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [codes, setCodes] = useState<string[]>([])
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => { authApi.mfaStatus().then(setStatus).catch((err) => setError(errorMessage(err))) }, [])
  useEffect(load, [load])
  const reset = () => { setMode('idle'); setSetup(null); setCode(''); setPassword(''); setError('') }

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError('')
    try { await action() } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  const submit = (action: () => Promise<void>) => (event: FormEvent) => { event.preventDefault(); void run(action) }

  const download = () => {
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([codes.join('\n') + '\n'], { type: 'text/plain' }))
    link.download = 'local-explorer-recovery-codes.txt'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const codeInput = (
    <Field label="Mã 6 số từ ứng dụng xác thực (hoặc mã khôi phục)">
      <Input required inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" className="max-w-[220px] font-mono tracking-widest" autoFocus />
    </Field>
  )

  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2">Xác thực hai lớp {status && (status.enabled ? <Badge tone="green" dot>Đang bật</Badge> : <Badge tone="amber" dot>Chưa bật</Badge>)}</span>}
        description="Mỗi lần đăng nhập cần thêm mã từ ứng dụng như Google Authenticator, Microsoft Authenticator hoặc 1Password." />
      <div className="space-y-4 p-5">
        {!status && !error && <Spinner />}
        {status?.required && !status.enabled && <Alert tone="amber" title="Bắt buộc với quản trị viên">Bật xác thực hai lớp để tiếp tục sử dụng khu vực quản trị.</Alert>}
        {error && <Alert tone="red">{error}</Alert>}

        {status && mode === 'idle' && (
          <div className="flex flex-wrap items-center gap-3">
            {!status.enabled && <Button icon={ShieldCheck} loading={busy} onClick={() => void run(async () => { setSetup(await authApi.mfaSetup()); setMode('setup') })}>Bật xác thực hai lớp</Button>}
            {status.enabled && (
              <>
                <p className="text-sm text-slate-600">Còn <strong>{status.recovery_codes_remaining}</strong> mã khôi phục chưa dùng.</p>
                <Button variant="secondary" size="sm" icon={KeyRound} onClick={() => setMode('regenerate')}>Tạo mã khôi phục mới</Button>
                {!status.required && <Button variant="ghost" size="sm" icon={ShieldOff} className="text-rose-600" onClick={() => setMode('disable')}>Tắt</Button>}
              </>
            )}
          </div>
        )}

        {mode === 'setup' && setup && (
          <form onSubmit={submit(async () => {
            setCodes(await authApi.mfaEnable(code.trim()))
            setCode('')
            setMode('codes')
            await refresh()
            load()
            toast.success('Đã bật xác thực hai lớp.')
          })} className="grid gap-5 sm:grid-cols-[200px_minmax(0,1fr)]">
            <img src={setup.qr} alt="Mã QR để thêm vào ứng dụng xác thực" className="h-[200px] w-[200px] rounded-lg border border-slate-200 bg-white p-2" />
            <div className="space-y-4">
              <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
                <li>Mở ứng dụng xác thực và quét mã QR.</li>
                <li>Không quét được? Nhập khóa: <code className="break-all rounded bg-slate-100 px-1.5 py-0.5 text-xs">{setup.secret}</code></li>
                <li>Nhập mã 6 số mà ứng dụng hiển thị.</li>
              </ol>
              {codeInput}
              <div className="flex gap-2"><Button type="submit" loading={busy}>Xác nhận</Button><Button type="button" variant="secondary" onClick={reset}>Hủy</Button></div>
            </div>
          </form>
        )}

        {mode === 'codes' && (
          <div className="space-y-3">
            <Alert tone="amber" title="Lưu mã khôi phục ngay">Mỗi mã dùng được một lần khi bạn mất điện thoại. Các mã này chỉ hiển thị lần này.</Alert>
            <pre className="grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-4 font-mono text-sm text-slate-800 sm:grid-cols-4">{codes.map((item) => <span key={item}>{item}</span>)}</pre>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" icon={Copy} onClick={() => { void navigator.clipboard?.writeText(codes.join('\n')); toast.success('Đã sao chép.') }}>Sao chép</Button>
              <Button variant="secondary" size="sm" icon={Download} onClick={download}>Tải xuống</Button>
              <Button size="sm" onClick={() => { setCodes([]); reset(); onEnabled?.() }}>Tôi đã lưu</Button>
            </div>
          </div>
        )}

        {(mode === 'regenerate' || mode === 'disable') && (
          <form onSubmit={submit(async () => {
            if (mode === 'regenerate') {
              setCodes(await authApi.mfaRegenerate(code.trim()))
              setCode('')
              setMode('codes')
            } else {
              await authApi.mfaDisable(code.trim(), password || null)
              reset()
              await refresh()
              toast.success('Đã tắt xác thực hai lớp.')
            }
            load()
          })} className="space-y-4">
            {codeInput}
            {mode === 'disable' && <Field label="Mật khẩu hiện tại"><Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="max-w-xs" /></Field>}
            <div className="flex gap-2">
              <Button type="submit" variant={mode === 'disable' ? 'danger' : 'primary'} loading={busy}>{mode === 'regenerate' ? 'Tạo mã mới' : 'Tắt xác thực hai lớp'}</Button>
              <Button type="button" variant="secondary" onClick={reset}>Hủy</Button>
            </div>
          </form>
        )}
      </div>
    </Card>
  )
}
