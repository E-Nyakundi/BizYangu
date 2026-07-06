'use client'

import { useEffect } from 'react'
import { initializeTheme } from '@/lib/theme'

export default function RootLayoutClient({
  children,
}: {
  children: React.ReactNode
}) {
  useEffect(() => {
    initializeTheme()
  }, [])

  return <>{children}</>
}
