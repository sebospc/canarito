# App Review notes (paste into App Store Connect, App Review Information)

Canarito shows earthquake alerts from a Canarito server that the user (or someone they know)
runs. There is no account and no sign-in. The app has nothing to do until it is linked to a
server by scanning a QR code, so we provide a demo server.

## How to review
1. Open the app and tap Continue. Allow notifications and location.
2. Linking screen: scan the demo QR (attached image), or paste the demo link into the field and
   tap "Usar enlace" (es) / "Use link" (en). The QR and link come from the demo server, see
   "Demo server" below. They are private: never in the repo, never on a bead.
3. Confirm the server name and tap Link. The home screen then says the alerts are on.
4. Settings (gear icon) > "Enviar aviso de prueba" / "Send a test alert". The phone gets a test
   push in a few seconds and the test alert screen shows.

## Notes
- Location: "Always" is used so the user's server can keep the receptor near them when the
  app is closed (significant-change monitoring only). Only a position rounded to 1 km is sent,
  only to the linked server. The app works without "Always"; the home screen then warns that
  the server follows the last place the app was opened.
- Notifications: time-sensitive. Critical Alerts are not requested in this version.
- Camera: only to read the linking QR. The link can be pasted instead.
- No purchases, ads, tracking or third-party SDKs. No data goes to the developer. Alerts pass
  through an open source push relay (`relay/` in the repository) that stores nothing.
- Not an official alert system, and the app says so on the first screen and in Settings.
- Source code: https://github.com/sebospc/canarito

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
