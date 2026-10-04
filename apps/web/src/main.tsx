import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import { router } from './router'
import { AuthProvider } from './auth'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AuthProvider><RouterProvider router={router} future={{ v7_startTransition: true }} /></AuthProvider></React.StrictMode>,
)
