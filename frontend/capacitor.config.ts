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
    GoogleAuth: {
      // Web/server client ID — needed so the plugin can request an
      // idToken audienced for our backend to verify, not just an
      // Android-only access token. The Android-specific client ID
      // (tied to this keystore's SHA-1) is passed at GoogleAuth.initialize()
      // call time instead — see lib/google-auth.ts.
      scopes: ['profile', 'email'],
      serverClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID_WEB,
      forceCodeForRefreshToken: false,
    },
  },
}

export default config