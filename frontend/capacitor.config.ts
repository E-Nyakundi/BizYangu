import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'co.bizyangu.app',
  appName: 'BizYangu',
  webDir: 'out',

  // No server.url — Capacitor serves the built Next.js files
  // from the APK itself (the 'out' folder baked in at build time).
  // API calls go to Django via NEXT_PUBLIC_API_URL in .env.local.

  android: {
    allowMixedContent: false,
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
}

export default config