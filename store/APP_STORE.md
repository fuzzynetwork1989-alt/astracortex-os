# Apple App Store listing — AstraCortex OS

## App identity
- **Name:** AstraCortex OS
- **Bundle ID:** `com.astracortex.os`
- **Category:** Productivity

## Subtitle
Cognitive OS for work — local or cloud AI

## Description
Same product as Play listing. iOS build requires macOS + Xcode:

```bash
cd mobile
npx expo prebuild --platform ios
npx expo run:ios
# or EAS: eas build -p ios
```

## Privacy nutrition labels
- Contact info (email)
- User content (messages, docs)
- Diagnostics (optional usage metrics)

## Privacy policy URL
`https://YOUR_VERCEL_URL/privacy`

## Note
Physical iOS device install needs Apple Developer account ($99/yr). Expo EAS can produce TestFlight builds from this repo’s `mobile/` app.
