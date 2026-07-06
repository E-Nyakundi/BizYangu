import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'co.bizyangu.app',
  appName: 'BizYangu',
  webDir: 'frontend/out', // static export lands in frontend/out/ relative to project root

  // server.url = LIVE RELOAD (dev only).
  // Comment this block out before building a distribution APK.
  // When commented out the WebView loads from the bundled out/ assets.
  // server: {
  //   url: 'http://localhost:3000',
  //   cleartext: true,
  // },

  android: {
    allowMixedContent: false, // ngrok backend is HTTPS — no mixed content needed
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
}

export default config
