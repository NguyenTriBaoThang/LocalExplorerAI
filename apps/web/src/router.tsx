import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { HomePage } from './pages/HomePage'
import { ExplorePage } from './pages/ExplorePage'
import { PlannerPage } from './pages/PlannerPage'
import { ItineraryPage } from './pages/ItineraryPage'
import { ProviderPage } from './pages/ProviderPage'
import { ProviderPortalPage } from './pages/ProviderPortalPage'
import { AboutPage } from './pages/AboutPage'
import { AuthPage } from './pages/AuthPage'
import { ProfilePage } from './pages/ProfilePage'
import { AdminPage } from './pages/AdminPage'
import { SharedItineraryPage } from './pages/SharedItineraryPage'
import { ComparePage } from './pages/ComparePage'
import { ChatPage } from './pages/ChatPage'
import { Map3DPage } from './pages/Map3DPage'
import { ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from './pages/RecoveryPages'
import { GuidePage, GuidesPage } from './pages/GuidesPage'
import { PlacePage } from './pages/PlacePage'
import { CustomerRoute, GuestRoute, RoleHome, RoleRoute } from './auth'

export const router = createBrowserRouter([{
  element: <AppLayout />,
  children: [
    { path: '/', element: <RoleHome><HomePage /></RoleHome> },
    { path: '/map-3d', element: <Map3DPage /> },
    { element: <CustomerRoute />, children: [
      { path: '/explore', element: <ExplorePage /> },
      { path: '/chat', element: <ChatPage /> },
      { path: '/planner', element: <PlannerPage /> },
      { path: '/itinerary/:id', element: <ItineraryPage /> },
      { path: '/provider', element: <ProviderPage /> },
      { path: '/about', element: <AboutPage /> },
      { path: '/guides', element: <GuidesPage /> },
      { path: '/guides/:slug', element: <GuidePage /> },
      { path: '/places/:placeId', element: <PlacePage /> },
    ] },
    { path: '/shared/:token', element: <SharedItineraryPage /> },
    { path: '/forgot-password', element: <ForgotPasswordPage /> },
    { path: '/reset-password', element: <ResetPasswordPage /> },
    { path: '/verify-email', element: <VerifyEmailPage /> },
    { element: <GuestRoute />, children: [
      { path: '/login', element: <AuthPage /> },
      { path: '/register', element: <AuthPage register /> },
    ] },
    { element: <RoleRoute roles={['traveler', 'provider', 'admin']} />, children: [
      { path: '/profile', element: <ProfilePage /> },
    ] },
    { element: <RoleRoute roles={['traveler']} />, children: [
      { path: '/compare', element: <ComparePage /> },
    ] },
    { element: <RoleRoute roles={['provider']} />, children: [
      { path: '/provider-portal', element: <ProviderPortalPage /> },
    ] },
    { element: <RoleRoute roles={['admin']} />, children: [
      { path: '/admin', element: <AdminPage /> },
    ] },
  ],
}], {
  future: {
    v7_relativeSplatPath: true,
  },
})
