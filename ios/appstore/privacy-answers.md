# App Privacy answers (App Store Connect)

Matches `Canarito/PrivacyInfo.xcprivacy`.

Apple counts data sent off the phone to a server we do not run as collected. Canarito has no
server of its own and nothing reaches the developer, but the app does send these two things to
the server the user pairs with, so the honest answer is to declare them, not "no data".
Owner decided 10-Oct: keep this declaration.

| Data type | Collected | Linked to user | Tracking | Purpose |
|---|---|---|---|---|
| Coarse Location (rounded to 1 km) | Yes | No (owner decision 10-Oct) | No | App Functionality |
| Device ID (push handle, device key) | Yes | No | No | App Functionality |
| Everything else | No | | | |

- Tracking: No. No ads, no data brokers, no third-party SDKs.
- Privacy policy URL: https://canarito.app/privacy (source: `site/build.py`, served by devops, cn-6g7).
- Encryption export: uses only HTTPS from the system (standard exempt). `ITSAppUsesNonExemptEncryption` is set to NO in project.yml.
- Age rating: 4+. Content rights: no third-party content, except the UNGRD safety text and
  pictograms quoted with source on the alert screen (owner to confirm the right to show them).
