import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { GuestOnly, RequireAuth, RequireRole } from './auth/guards'
import { ToastProvider } from './components/ui'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage'
import { AdminPartnersPage } from './pages/admin/AdminPartnersPage'
import { AdminUsersPage } from './pages/admin/AdminUsersPage'
import { AdminContentPage } from './pages/admin/AdminContentPage'
import { AdminPlaceEditorPage } from './pages/admin/AdminPlaceEditorPage'
import { AdminPlacesPage } from './pages/admin/AdminPlacesPage'
import { AdminRbacPage } from './pages/admin/AdminRbacPage'
import { AccountPage } from './pages/AccountPage'
import { AuditLogPage } from './pages/AuditLogPage'
import { adminApi, partnerApi } from './lib/api'
import { PartnerAnalyticsPage } from './pages/partner/PartnerAnalyticsPage'
import { PartnerCalendarPage } from './pages/partner/PartnerCalendarPage'
import { PartnerPlacesPage } from './pages/partner/PartnerPlacesPage'
import { PartnerReviewsPage } from './pages/partner/PartnerReviewsPage'
import { ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from './pages/auth/AccountPages'
import { LoginPage } from './pages/auth/LoginPage'
import { RegisterPage } from './pages/auth/RegisterPage'
import { HomePage } from './pages/HomePage'
import { PartnerBookingsPage } from './pages/partner/PartnerBookingsPage'
import { PartnerExperiencesPage } from './pages/partner/PartnerExperiencesPage'
import { PartnerLayout } from './pages/partner/PartnerLayout'
import { PartnerOverviewPage } from './pages/partner/PartnerOverviewPage'
import { PartnerProfilePage } from './pages/partner/PartnerProfilePage'

// Stable references so the audit page does not refetch on every render.
const loadPartnerAudit = () => partnerApi.audit()
const loadAdminAudit = () => adminApi.audit(300)

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route element={<GuestOnly />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            </Route>
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />

            <Route element={<RequireAuth />}>
              <Route path="/" element={<HomePage />} />
              <Route element={<RequireRole role="provider" />}>
                <Route path="/partner" element={<PartnerLayout />}>
                  <Route index element={<PartnerOverviewPage />} />
                  <Route path="experiences" element={<PartnerExperiencesPage />} />
                  <Route path="bookings" element={<PartnerBookingsPage />} />
                  <Route path="profile" element={<PartnerProfilePage />} />
                  <Route path="analytics" element={<PartnerAnalyticsPage />} />
                  <Route path="calendar" element={<PartnerCalendarPage />} />
                  <Route path="places" element={<PartnerPlacesPage />} />
                  <Route path="reviews" element={<PartnerReviewsPage />} />
                  <Route path="activity" element={<AuditLogPage title="Nhật ký hoạt động" description="Các thay đổi trên trải nghiệm, slot và địa điểm của bạn." load={loadPartnerAudit} />} />
                  <Route path="account" element={<AccountPage />} />
                </Route>
              </Route>
              <Route element={<RequireRole role="admin" />}>
                <Route path="/admin" element={<AdminLayout />}>
                  <Route index element={<AdminOverviewPage />} />
                  <Route path="partners" element={<AdminPartnersPage />} />
                  <Route path="users" element={<AdminUsersPage />} />
                  <Route path="rbac" element={<AdminRbacPage />} />
                  <Route path="places" element={<AdminPlacesPage />} />
                  <Route path="places/:placeId" element={<AdminPlaceEditorPage />} />
                  <Route path="content" element={<AdminContentPage />} />
                  <Route path="audit" element={<AuditLogPage title="Nhật ký hệ thống" description="Mọi thay đổi quan trọng do người dùng và quản trị viên thực hiện." load={loadAdminAudit} />} />
                  <Route path="account" element={<AccountPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
