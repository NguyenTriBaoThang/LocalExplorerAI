import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import { router } from './router'
import { AuthProvider, useAuth } from './auth'
import { JourneyProvider } from './journey'

function JourneyApp() {
  const { user, loading } = useAuth()
  if (loading) return null
  const owner = user?.id ?? 'guest'
  return <JourneyProvider key={owner} owner={owner}><RouterProvider router={router} future={{ v7_startTransition: true }} /></JourneyProvider>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AuthProvider><JourneyApp /></AuthProvider></React.StrictMode>,
)
