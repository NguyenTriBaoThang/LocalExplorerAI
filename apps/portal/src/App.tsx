import { AdminMeshyPage } from './pages/admin/AdminMeshyPage'
import { AdminLandmarkStoriesPage } from './pages/admin/AdminLandmarkStoriesPage'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { GuestOnly, RequireAuth, RequirePermission, RequireRole } from './auth/guards'
import { ToastProvider } from './components/ui'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage'
import { AdminPartnersPage } from './pages/admin/AdminPartnersPage'
import { AdminUsersPage } from './pages/admin/AdminUsersPage'
import { AdminContentPage } from './pages/admin/AdminContentPage'
import { AdminPlaceEditorPage } from './pages/admin/AdminPlaceEditorPage'
import { AdminPlacesPage } from './pages/admin/AdminPlacesPage'
import { AdminReviewsPage } from './pages/admin/AdminReviewsPage'
import { AdminSiteSettingsPage } from './pages/admin/AdminSiteSettingsPage'
import { AdminRbacPage } from './pages/admin/AdminRbacPage'
import { AdminImportsPage } from './pages/admin/AdminImportsPage'
import { AdminIntegrationsPage } from './pages/admin/AdminIntegrationsPage'
import { AdminOperationsPage } from './pages/admin/AdminOperationsPage'
import { AdminAiToolsPage } from './pages/admin/AdminAiToolsPage'
import { AdminFloodRiskPage } from './pages/admin/AdminFloodRiskPage'
import { AccountPage } from './pages/AccountPage'
import { AuditLogPage } from './pages/AuditLogPage'
import { adminApi, partnerApi } from './lib/api'
import { PartnerAnalyticsPage } from './pages/partner/PartnerAnalyticsPage'
import { PartnerCalendarPage } from './pages/partner/PartnerCalendarPage'
import { PartnerPlacesPage } from './pages/partner/PartnerPlacesPage'
import { PartnerReviewsPage } from './pages/partner/PartnerReviewsPage'
import { PartnerSlotAssistantPage } from './pages/partner/PartnerSlotAssistantPage'
import { PartnerEvidencePage } from './pages/partner/PartnerEvidencePage'
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
                  <Route element={<RequirePermission permission="provider:experience" />}>
                    <Route path="experiences" element={<PartnerExperiencesPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:booking_read" />}>
                    <Route path="bookings" element={<PartnerBookingsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:profile" />}>
                    <Route path="profile" element={<PartnerProfilePage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:analytics" />}>
                    <Route path="analytics" element={<PartnerAnalyticsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:experience" />}>
                    <Route path="calendar" element={<PartnerCalendarPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:poi" />}>
                    <Route path="places" element={<PartnerPlacesPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:reviews" />}>
                    <Route path="reviews" element={<PartnerReviewsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:slot_assist" />}>
                    <Route path="slot-assistant" element={<PartnerSlotAssistantPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:evidence" />}>
                    <Route path="evidence" element={<PartnerEvidencePage />} />
                  </Route>
                  <Route element={<RequirePermission permission="provider:audit" />}>
                    <Route path="activity" element={<AuditLogPage title="Nhật ký hoạt động" description="Các thay đổi trên trải nghiệm, slot và địa điểm của bạn." load={loadPartnerAudit} />} />
                  </Route>
                  <Route path="account" element={<AccountPage />} />
                </Route>
              </Route>
              <Route element={<RequireRole role="admin" />}>
                <Route path="/admin" element={<AdminLayout />}>
                  <Route element={<RequirePermission permission="admin:models_3d" />}><Route path="meshy" element={<AdminMeshyPage />} /></Route>
                  <Route element={<RequirePermission permission="admin:dashboard" />}>
                    <Route index element={<AdminOverviewPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:providers" />}>
                    <Route path="partners" element={<AdminPartnersPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:users" />}>
                    <Route path="users" element={<AdminUsersPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:rbac" />}>
                    <Route path="rbac" element={<AdminRbacPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:places" />}>
                    <Route path="places" element={<AdminPlacesPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:places" />}>
                    <Route path="places/:placeId" element={<AdminPlaceEditorPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:reviews" />}>
                    <Route path="reviews" element={<AdminReviewsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:content" />}>
                    <Route path="content" element={<AdminContentPage />} />
                    <Route path="landmark-stories" element={<AdminLandmarkStoriesPage />} />
                  </Route>
                  <Route element={<RequirePermission anyOf={['admin:place_import', 'admin:duplicates']} />}>
                    <Route path="imports" element={<AdminImportsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:integrations" />}>
                    <Route path="integrations" element={<AdminIntegrationsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="ops:read" />}>
                    <Route path="operations" element={<AdminOperationsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:system" />}>
                    <Route path="site-settings" element={<AdminSiteSettingsPage />} />
                  </Route>
                  <Route element={<RequirePermission permission="admin:ai_tools" />}>
                    <Route path="ai-tools" element={<AdminAiToolsPage />} />
                  </Route>
                  <Route path="flood-risk" element={<AdminFloodRiskPage />} />
                  <Route element={<RequirePermission permission="admin:audit" />}>
                    <Route path="audit" element={<AuditLogPage title="Nhật ký hệ thống" description="Mọi thay đổi quan trọng do người dùng và quản trị viên thực hiện." load={loadAdminAudit} />} />
                  </Route>
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
