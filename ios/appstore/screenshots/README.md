# Screenshots

Taken on the team simulator (iPhone 18 Pro Max, 1320x2868, status bar 9:41) from `-state` samples with
the fake data of `Canarito/Samples.swift` (server canarito.example.org, receptor casa). Debug build.
Order: intro, covered, alert, unreachable, settings. `es-MX/` and `en-US/`.

- 1320x2868 (6.9"), the size App Store Connect requires. Team simulator `canarito-team-promax` (iPhone 18 Pro Max).
- The alert screen quotes the UNGRD guide in Spanish in both languages: it is Colombian safety
  text, shown verbatim on purpose.
- Retake: `xcrun simctl status_bar <udid> override --time 9:41 ...`, launch with `-state <name>
  -AppleLanguages (es)`; settings is `-state covered -sheet settings`, taken right after a fresh
  install. Write to an absolute path and delete the old file first.
