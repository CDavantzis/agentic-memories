import React from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import { AppLayout } from './pages/AppLayout'
import { Health } from './pages/Health'
import { Retrieve } from './pages/Retrieve'
import { Store } from './pages/Store'
import { Structured } from './pages/Structured'
import { Browser } from './pages/Browser'

const qc = new QueryClient()

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Health /> },
      { path: 'health', element: <Health /> },
      { path: 'retrieve', element: <Retrieve /> },
      { path: 'store', element: <Store /> },
      { path: 'structured', element: <Structured /> },
      { path: 'browser', element: <Browser /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
)


