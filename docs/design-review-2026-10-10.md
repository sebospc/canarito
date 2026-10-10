# Design review, 2026-10-10

Method: ⚠️ DEGRADED: single-context. One session read the source, no sub-agents. Impeccable's launcher is not installed, so context loading was skipped ("Launcher unavailable" path) and `impeccable detect` did not run. There is no PRODUCT.md or DESIGN.md in either project.

Not verified: nothing was rendered. No browser, no Simulator, no Dynamic Type or Dark Mode capture, no VoiceOver pass, no performance profile. Everything below comes from reading code. Contrast ratios for the web palette were computed from the hex values (see Positives).

Skills run: `/impeccable critique` (assessment A only), `/impeccable audit` with `audit.native.md` and `ios.md`, `/better-ui`, `/no-ai-slop` in detect mode on user-facing strings.

Targets:
- Web: `site/public/styles.css`, `site/build.py` (source of `index.html` and `en/index.html`), SVGs in `docs/` (built by `docs/images.py`).
- iOS, read only: `~/Documents/earthquakes-project/ios-client/EarthquakeRelay/{Main,Alert,Consent,Coverage,Paywall,PositionLesson,Root}View.swift`.

## Answer

Partly. The skills were not the main cause.

- The iOS views are in good shape. Their comments cite a 4.5:1 audit, simulator screenshots and numbered review rounds, so someone ran a loop like Impeccable's audit by hand. Dynamic Type, Reduce Motion on the pulse, 44 pt targets, pinned buttons, a layout switch at accessibility sizes and VoiceOver announcements are all there. The gaps are the usual ones a native audit finds (below), not a collapse.
- The web look (7 October, before the skills) has the typical gaps the skills target: a halo shadow, one identical entrance on every hero child, hover without a hover query, diagram text that shrinks to about 10 px on phones, bold lead-ins on every note. Small, fixable in an hour.
- The worst findings are not visual. They are copy that is true for the old app and false for Canarito (position leaves the phone, "we are fixing it", a privacy controller), and an alert text in a different register from everything else. `/no-ai-slop` and a truth check on strings would have caught these. A visual skill would not.
- Root cause, if one: no PRODUCT.md or DESIGN.md. Decisions like "always dark" and "bird never on an alert" live only in code comments, so nothing could check them and a rewrite can silently drop them. Run `/impeccable init` and `document` before the app work starts (writes files, so I did not do it).

## Findings, worst first

"Carries" = still applies to the new Canarito app if the file or pattern is reused.

| # | Sev | Where | Pattern | Fix | Carries |
|---|-----|-------|---------|-----|---------|
| 1 | P0 | `CoverageView.swift:48`, `MainView.swift:176` | "Tu posición exacta no sale del teléfono." The new app sends its position to the server (STATUS.md). The line becomes false on the screen that explains privacy. | Rewrite from the real flow: what is sent (rounded position, to the paired server only), to whom (the person who runs it). Same for `ConsentView.swift:139` ("zona de unos 11 km", "al servidor solo llegan las zonas"). | Yes, if strings are copied |
| 2 | P0 | `ConsentView.swift:143-145`, `:15-16`, `LegalTexts.controllerName`, `CoverageView.swift:94-95` | Legal text names a controller, hello@canarito.app and `canarito.app/es/terminos` and `/privacidad`. Canarito is self-hosted and free; the site has no such pages. Dead links in a consent screen. | Decide who is the controller for a self-hosted server and for the relay, write short text for that, publish the pages or drop the links before App Review. | Yes |
| 3 | P1 | `MainView.swift:190` | "Lo estamos arreglando." There is no team behind a self-hosted server. A promise nobody keeps, on the screen where a person learns they are uncovered. | "Ahora mismo no podemos avisarte." plus what the person can do (check the server). The code already does this for `serviceUnreachable` (`:181-183`). | Yes |
| 4 | P1 | `android/.../RelayPolicy.java:43`, `RelayPolicyTest.java:29-30`, mock in `build.py` / `images.py:200` | Alert text uses usted ("su zona", "Protéjase ahora"). The site, the iOS app and the brand rule ("Tú, per the brand", `MainView.swift:138`) use tú. The most important sentence in the product has the odd voice. | Pick one register. Tú for all, then update the test and the mockups. | Yes (push text) |
| 5 | P1 | `build.py:30`, `:80`, rendered in `index.html` | "Sin servidor." / "No server." Now there is a server, and an APNs relay is being added. A false claim in the first explanation block. | Replace with what is true: one server, run by whoever wants it; nothing paid. | Yes |
| 6 | P1 | `RootView.swift:52-53`, `MainView.swift:65` | `.animation(.smooth(0.5))` on state and legal screen, and a `.move(edge: .bottom)` for the action button, with no `accessibilityReduceMotion` check. `ios.md` and better-ui both treat this as HIGH: motion that ignores the setting. The pulse at `MainView.swift:34` is gated, so the rule is known and missed twice. | Under Reduce Motion use `.opacity` only. One helper, used in both places. | Yes |
| 7 | P1 | `build.py:15`, `:65` | Hero "Unos segundos pueden cambiarlo todo." / "A few seconds can change everything." Fails the portability test: fits any alert, news or insurance product. The line under it (`claim`, `:16`) says what the product is, so the h1 earns nothing. | Lead with the claim ("Los avisos de sismo de Android, en tu iPhone"), drop the h1 line. | Yes (site, App Store subtitle) |
| 8 | P2 | `ConsentView.swift:94,107-113,119,121,125` | Card with a 4 pt coloured bar on the leading edge, five uses. Refused pattern (coloured side border above 1 px). | Plain surface card; put the weight in the bold first sentence, which is already there. | Only if consent is reused |
| 9 | P2 | `ConsentView.swift:81` | Small bold uppercase label "QUÉ CAMBIÓ" above text. Kicker/eyebrow, banned with no exception. | Drop the label; the sentence "Actualizamos los límites" in the title already says it. | Only if re-accept is reused |
| 10 | P2 | `styles.css:84` with `docs/images.py` sizes | On phones `.figure` is 780 px wide for a 1200 px drawing. Text drawn at 16 and 17 px comes out at 10.4 and 11.1 px; 19 px at 12.4. Below the 11 pt floor and hard to read; the reader must also scroll sideways. | Draw a narrow variant (about 390 px) for phones, or raise the SVG text to 20+ px and drop detail. | Yes (site) |
| 11 | P2 | `AlertView.swift:111,161,188,246,256` | Fixed `frame(width: 24/84/20)` for icons and pictograms. Text scales, these do not (`@ScaledMetric` is used in `MainView:16-17`, not here). The guide row (`:160`, `:255`) is an `HStack` with no switch to a vertical layout at accessibility sizes, unlike `CoverageView.swift:37`. At AX sizes the text column gets squeezed beside an 84 pt picture. | `@ScaledMetric` for the sizes; reuse the `AnyLayout` switch from CoverageView. | Yes |
| 12 | P2 | `MainView.swift:70`, `ConsentView.swift:62`, `CoverageView.swift:117`, `AlertView.swift:74` | `.preferredColorScheme(.dark)` everywhere, and `Brand.*` custom colours instead of semantic system colours. Defensible (night use, brand), but it ignores the phone's setting and increased-contrast, and it is written nowhere except one comment. | Keep it if the choice is deliberate, record it in DESIGN.md with the reason, and check Increase Contrast in the Simulator. | Decision needed |
| 13 | P2 | `AlertView.swift:111,188,246` | `GlyphClock`, `GlyphPhone` custom images next to SF Symbols in `MainView`. `ios.md`: one icon set; SF Symbols. | `clock`, `phone.fill` as SF Symbols, `.symbolRenderingMode`, scale with text. | Yes |
| 14 | P2 | `AlertView.swift:185-206`, `:240-251` | Three button implementations built by hand (background on the label, no `ButtonStyle`), copied between `closeButton`, `emergencyButton` and `AfterView`; `MainView.actionButton` uses `.borderedProminent`. No pressed state of its own. Cards use radius 14 in some files and 16 in `AlertView:166`, `:262`. | One `ButtonStyle` (filled, outlined) with a pressed state, one radius token. | Yes |
| 15 | P2 | `MainView.swift:27-35` | State shown as an SF Symbol in a 13%-tinted circle, 2.6x the symbol size. This is the stock "icon in a circle" hero; it says nothing about Canarito. The bird, the product's one distinctive shape, is 26 pt in a header (`:128`). | Make the state mark from the bird (or a bird plus a state badge). Keep the pulse. | Yes, design decision |
| 16 | P2 | `styles.css:51` | `.glow` ring: `box-shadow:0 0 0 14px rgba(...)` twice. Zero-offset coloured halo (decoration), and in forced-colors mode the rings vanish. | Drop the rings or draw them as real elements with a transparent border. | Site only |
| 17 | P2 | `styles.css:89-91` | `.hero>*` all get the same `rise` entrance, then `.notif,.toast,.glow` a second drop at 0.9 s. Scattered identical entrances, not one authored moment. Gated by reduced motion, so only a polish issue. | Animate the trio only, or the phone notification alone. | Site only |
| 18 | P3 | `styles.css:20,29` | `:hover` outside `@media (hover:hover)`. On touch the hover stays after a tap. | Wrap both. | Site only |
| 19 | P3 | `styles.css:19` vs `:28` | `.lang` radius 10, `.button` radius 12, same size of control. Same detail two ways. | One radius. | Site only |
| 20 | P3 | `styles.css:35,44,46,49`, `AlertView.swift:129` | Raw hex outside the token set: `#16262A`, `#F3F6F6`, `#fff`, `#2A3538` (web mockups) and `Color(hex: 0xF4F4F2)` (iOS test band, bypasses `Brand`). | Tokens in both. | Yes |
| 21 | P3 | `build.py:29,30,37,38,79,80,87,88` | Bold lead-in on every note ("**Probado con sismos reales.**"). Formatting slop; the `strong` is the paragraph's topic, a heading in disguise. | Plain sentences, or real h3s if the topics matter. Keep `.risk b`, those are labels in a list. | Site, README |
| 22 | P3 | `build.py:36`, mock in `index.html` | The hero mock shows the ntfy app, not Canarito. Obsolete the day the iOS app ships. | Redraw with the Canarito notification and the canary alert screen. | Yes |

## Audit health score (iOS, from source)

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 3 | Strong. Motion not gated in Root/Main (#6); fixed icon sizes (#11) |
| 2 | Performance | 3 | Not profiled. One-second `TimelineView` limited to a line, fine |
| 3 | Appearance & theming | 2 | Brand colours only, dark forced, stray hex (#12, #20) |
| 4 | Platform conformance | 3 | System nav, sheets, List, confirmation dialog. Custom glyphs and buttons (#13, #14) |
| 5 | Adaptivity | 2 | AX sizes handled in Main/Coverage, not in Alert guide rows. Landscape and iPad unchecked (Not verified) |
| | Total | 13/20 | Acceptable, with real strengths |

Platform conformance verdict: native. Navigation stack, sheet, List sections, confirmation dialog and system buttons. Not a ported website.

## Web critique (Persuade mode, source only)

Design specificity: good. Night teal with canary only on the bird and the alert, Bricolage Grotesque for display, system sans for text. A different product could not use this unchanged. The hero trio (phone, laptop, lamp) shows the idea at a glance.

Weaker spots: the h1 (#7), a long text-only wall in "Qué puede fallar" (eight rows, honest and correct to keep), and the hero stack of h1 + claim + lead saying the same thing three times at 64, 28 and 21 px.

Heuristics (8 of 10 scored, 7 and 10 n/a for a landing page): visibility of status 3, match with the real world 2 (the "Sin servidor" claim), user control 3, consistency 3, error prevention 3, recognition 3, minimalist design 3, error recovery 2 (a reader who hits a failure only gets "see GitHub"). Total 22/32, judged from source.

## Positives, keep

- Contrast on the web palette (computed): sub on page 6.55, accent on page 5.61, late on surface 5.03, dark sub on page 8.16, dark accent on surface 7.57, text on canary 11.23. All above 4.5.
- Risks section is visible, plain and specific. Best copy in the repo.
- Type scale, 480 px measure on notes, focus-visible on links, reduced-motion media query on the web.
- iOS: `isAccessibilitySize` branches (`MainView.swift:50,64`, `CoverageView.swift:37`), `AccessibilityNotification.Announcement` on state change (`MainView.swift:72-74`), pinned buttons, `.symbolEffect` gated on Reduce Motion, 44 pt minimum heights, comments that record why (contrast, clipping, VoiceOver order).
- Brand rules are written down in comments and followed (no bird on an alert, tú, no numbers on the main screen).

## Does not carry to Canarito

`PaywallView.swift` and the subscription card in `MainView.swift:92-104` (free app, no purchases). The App Review code field (`CoverageView.swift:77-92`): STATUS.md says App Review gets a demo QR instead. `PositionLessonView` can stay if the guide stays.

## Order of work

1. Strings first (#1 to #5): a truth pass on every string against the real flow, then `/no-ai-slop` on the result.
2. `/impeccable init` and `document` so the dark choice, tone and brand rules have a home; then `/impeccable shape` for the new main screen (#15).
3. Build with #6, #11, #13, #14 fixed from the start in the shared pieces, not patched later.
4. Web: #10, #16 to #19, #21, #22 in one `/impeccable polish` pass after the app ships, so the mock is the real app.
