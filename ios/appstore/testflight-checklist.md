# TestFlight checklist (owner does Apple; nothing here is automated)

Before the first upload
- [ ] APNs key (.p8) created, key id and team id given to devops for the relay secret.
- [ ] Relay deployed with topic `app.canarito`, sandbox and production both answer.
- [ ] https://canarito.app/privacy live (cn-6g7), URL entered in App Store Connect. The app already links it.
- [ ] Demo server up with `pair --name review --demo`, QR and link in the App Review notes field (review-notes.md), tested from a real iPhone.
- [ ] Critical Alerts: request submitted by the owner. Build flag `CRITICAL_ALERTS` stays off until granted.

Build
- [ ] `xcodegen generate`, signing automatic with team BGKJDXR2L4, Archive, upload from Xcode.
- [ ] Raise `CURRENT_PROJECT_VERSION` on every upload.

On a real iPhone before inviting anyone (the Simulator cannot do these)
- [ ] Pair by scanning the real QR from the live host.
- [ ] Test alert arrives with the app killed, with the phone locked, and in a Focus mode.
- [ ] Location "Always" prompt appears once; after granting, moving about 1.5 km sends one position (check server log).
- [ ] Turn off the server: home screen goes to "No llegamos a tu servidor" within 2 minutes of opening.
- [ ] Unlink in Settings: the server drops the device.
- [ ] Dynamic Type at the largest size on intro, home and alert.
- [ ] VoiceOver reads home state and the alert screen.

Then
- [ ] Add testers (owner and partner first), watch one real day.
- [ ] Submit for review only with a settled demo.
