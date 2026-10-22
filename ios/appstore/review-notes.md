# App Review notes (paste into App Store Connect, App Review Information)

Canarito shows earthquake alerts from a Canarito server that the user (or someone they know)
runs. There is no account and no sign-in. The app has nothing to do until it is linked to a
server by scanning a QR code, so we provide a demo server.

## How to review
1. Open the app and tap Continue. Notifications and location are optional: you can choose Don't Allow
   for both and the app still works.
2. Linking screen: scan the attached demo QR, or paste the demo link into the field and tap "Use link"
   ("Usar enlace" in Spanish). The QR and link come from the demo server, see "Demo server" below.
3. Confirm the server name and tap Link. Home shows the server's state.
4. Open Settings (gear icon) and tap "Send a test alert". In a few seconds the test alert screen opens in
   the app and sounds.

## With notifications off
- The app links, shows the server's state and shows alerts while it is open, as in step 4.
- Home reads "Alerts while the app is open" and has a small card with a button to turn notifications on
  in Settings. Nothing is blocked and the app does not ask again.
- With notifications on, alerts also arrive when the app is closed.

## With location off
- The app works the same. If the user's receptor follows their phone, home shows a small card saying the
  server does not know where they are, with a button to allow location. The demo receptor does not follow
  the phone, so the demo shows no card.

## Notes
- Location: "Always" lets the user's server keep the receptor near them when the app is closed
  (significant-change monitoring only). Only a position rounded to 1 km is sent, only to the linked server.
- Notifications: time-sensitive. Critical Alerts are not requested in this version.
- Camera: only to read the linking QR. The link can be pasted instead.
- No purchases, ads, tracking or third-party SDKs. No data goes to the developer. Alerts pass
  through an open source push relay that stores nothing.
- Not an official alert system, and the app says so on the first screen and in Settings.

## Demo server (owner, before submitting)
The pairing code of a real server works once for 10 minutes. For review use demo mode, which
makes a reusable code (docs/app-contract.md, 2d):

1. On a server with no real people, run `canarito.py pair --name review --demo`. It prints the
   QR and the `canarito://pair?...` link, and writes `pair-review-demo.png`. That file is the key:
   keep it private.
2. Put the QR image as an attachment and the link text in the App Review notes field in App
   Store Connect (not in this repo).
3. Phones paired this way only get test alerts (one per 10 seconds), never real ones, and their
   positions are ignored. The home screen reads "Avisos activos" / "Alerts on".
4. After the review is approved, run `canarito.py pair --name review --demo-off`. It stops the
   code and removes the demo phones.

The server must be reachable over HTTPS for the whole review, and its push relay must be up
(the test alert goes through it to Apple). Check with one pairing and one test alert from a
real iPhone before submitting.
