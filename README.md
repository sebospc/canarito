# Canarito

Canarito runs an Android emulator on your own computer, tells it that it is at a place you
choose (your home, your parents' town), and forwards Google's earthquake early warnings
from that emulator to your phone. It works on iPhone too, through the free
[ntfy](https://ntfy.sh) app.

It is a hack around a system we do not own. Read [What can go wrong](#what-can-go-wrong)
before you trust it with anything.

## Why it exists

Android phones get earthquake early warnings from Google (Android Earthquake Alerts, AEA).
iPhones do not. In Colombia, where this started, most people do not get any early warning
on an iPhone.

AEA decides who gets an alert by the location the phone reports. An Android emulator with a
fake location is enough. On 23 and 24 September 2026 real quakes near Chaparral, Colombia,
reached our emulators, and only the ones placed inside the alert radius got them. The
others, 478 km away or more, got nothing.

So the idea: one emulator per place you care about, an app inside it that catches the
alert, and a push to your phone.

## How it works

```
quake
  │  Google detects it with Android phones near the epicenter (we do not take part)
  ▼
Google Play Services inside the emulator, location = your place
  │  posts a notification on channel eew_alert*
  ▼
Canarito app in the emulator (a notification listener)
  │  checks the sender is really Play Services (signing certificate), then
  │  HTTP POST to your ntfy topic, own words, no Google text
  ▼
ntfy (ntfy.sh or your own server)
  ▼
ntfy app on every phone subscribed to that topic
```

On the computer, `canarito.py run` keeps the emulator alive: it starts it, feeds it the GPS
position while it boots, installs and configures the app after every boot, and reboots it
every 18 hours so its location never gets old.

What you get on the phone, in Spanish by default:

> **Alerta de sismo**
> Sismo M4.5 cerca de su zona. Protéjase ahora.

`--language en` gives "Earthquake M4.5 near you. Take cover now."

The text has no distance on purpose. The distance Google gives is from the emulator to the
quake, not from you, and a phone showing "16 km" makes people believe it is theirs.

## What you need

- A computer that stays on: macOS (Apple Silicon or Intel) or Linux with KVM. Windows was
  never tried.
- About 4 GB of free RAM per emulator, and 10 GB of disk for the first one. Each emulator
  grows to about 3.5 GB of RAM after some hours.
- Python 3.9 or newer.
- The Android SDK command line tools. JDK 17 if you build the app yourself.
- A phone with the ntfy app: [iOS](https://apps.apple.com/app/ntfy/id1625396347),
  [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).

No Google account is needed in the emulator. That was measured: an emulator with no account,
on an x86_64 server with a Brazilian IP, got the alert for a quake in Colombia.

## Install

1. Android SDK. On macOS: `brew install --cask android-commandlinetools`. On Linux, the
   "Command line tools only" zip from https://developer.android.com/studio. Then:

   ```bash
   export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools   # where yours is
   ```

2. Build the app (or download `android-debug.apk` from the releases page and pass it with
   `--apk`). It must be the debug build: the CLI writes its config with `run-as`, which only
   works on debuggable apps.

   ```bash
   echo "sdk.dir=$ANDROID_HOME" > local.properties
   ./gradlew :android:assembleDebug
   ```

3. Create a receptor at your place. Latitude and longitude in decimal degrees, from any map.

   ```bash
   python3 canarito.py setup --name home --lat 4.711 --lon -74.072
   ```

   The first time it downloads the emulator and an Android 15 image, a few GB. It prints the
   ntfy topic it made for you, something like `https://ntfy.sh/canarito-3f9a...`.

4. On each phone: install ntfy, add a subscription with that topic URL. On Android, set the
   subscription to "urgent" so it can ring. On iPhone, allow notifications.

5. Start it and leave it running:

   ```bash
   python3 canarito.py run --name home
   ```

   The first boot takes a few minutes, and the log says `receptor provisioned`. That is not
   enough. Google's earthquake code inside the emulator has to start too, and on a new
   emulator that took 13 to 60 minutes in our runs. Wait for `AEA registered`. Until that
   line, this receptor cannot get an alert.

6. Check the phone side and the receptor:

   ```bash
   python3 canarito.py test --name home
   ```

More places: run `setup` and `run` again with another `--name`. Each one is a full emulator,
so the RAM adds up.

To keep it running after a reboot of the computer, start `canarito.py run` from a systemd
unit (Linux) or a launchd agent (macOS), with the same `ANDROID_HOME`. It runs in the
foreground and keeps the emulator alive on its own.

### Options

| option | what it does |
|---|---|
| `--notify-url` | your own ntfy topic URL, for example on your own ntfy server |
| `--notify-token` | ntfy access token, for a topic with access control |
| `--heartbeat-url` | pinged every 5 minutes by the app, for example a [healthchecks.io](https://healthchecks.io) check. If the pings stop, that service tells you. Without it, nobody notices a dead receptor. |
| `--language` | `es` (default) or `en` |

`canarito.py evidence --name home` prints everything the app saw from Play Services and each
send attempt, as JSON lines.

On a self-hosted ntfy server, iPhones only get instant notifications if the server has
`upstream-base-url: "https://ntfy.sh"` set. That is how ntfy delivers to iOS without an Apple
developer account of your own.

## What can go wrong

This is the part to read.

**It is not an official alert system.** If it fails, nobody is accountable, and it can fail
silently. Do not make it your only source of warning, and do not build something for other
people on top of it without understanding everything below.

**It breaks Google's terms.** The Android SDK license allows the emulator "solely to develop
applications" (sections 3.1 and 3.4), and forbids distributing data obtained from Google
APIs without permission (8.1). Google's Terms of Service forbid using its content without
permission. Running this is your decision. We think personal, non-commercial use is low
risk, but it is still against the terms. This project uses no Google text or brand in the
alert it sends.

**Google can stop it any day.** Google's anti-abuse system (DroidGuard) reads the motion
sensors to tell real devices from fake ones. Today that does not stop alert delivery to
emulators. Nothing says it will stay that way, and you will not get a warning when it
changes.

**The warning is often too late close to the epicenter.** Google's alert reached our
emulator 18.1 s after the quake started (24-sep-2026, M4.5), and Canarito added about 0.8 s.
The shaking (S wave) travels about 3.5 km/s:

| your distance to the epicenter | shaking arrives | time left with the warning |
|---|---|---|
| 20 km | 6 s | none, 12 s late |
| 50 km | 14 s | none, 3 s late |
| 100 km | 29 s | about 11 s |
| 200 km | 57 s | about 40 s |
| 300 km | 86 s | about 68 s |

It is useful from about 80 km. For the quake right under you, no system can help. Google
says itself that only 36% of its users get the alert before the shaking.

**The alert is for the emulator's place, not for you.** If you travel, you still get alerts
for home. Google alerts within a radius that depends on its magnitude estimate (about 31 km
for M4.5, 78 km for M5, 346 km for M6), so an emulator far from where you live may stay
silent for a quake you feel.

**Old location, lost alert.** On 24-sep-2026 an emulator with a location about 25 hours old
did not get an alert it should have got. Play Services takes a GPS fix only some minutes into
each boot and then keeps it, so the app holds GPS open and the CLI reboots the emulator
every 18 hours. Each reboot is about 10 minutes without coverage.

**Some emulators never start AEA.** One in eight of our new emulators never registered,
for reasons we did not find. `run` says so after 90 minutes: delete that AVD and run
`setup` again.

**One alert we never explained.** In the same quake, an emulator on a Mac with a personal
Google account did not get the early warning, only the "you may have felt shaking" notice
40 s later. An identical setup without an account on a server did. We never found out why.

**Only the early warning is sent.** The later notice (`eew_update`, which came 5 min 21 s
after the quake on 24-sep) is not forwarded, because "take cover" would be wrong advice by
then. If Google renames its alert channel, Canarito stops forwarding, on purpose: guessing
risks a false alarm. The evidence file still records what arrived.

**Google's magnitude is its own.** A quake the Colombian Geological Service measured as M3.6
came from Google as M4.46. Compare by time and place, never by magnitude.

**ntfy.sh topics are public.** Anyone who knows the topic name can read it and post to it.
`setup` makes a random name; keep it private, or use a protected topic or your own server.

**Duplicates are possible.** A retry after a lost answer, or a restart of the app while an
alert is on screen, can send the same alert twice. Twice was chosen over never. Two
emulators near the same place also send one alert each.

**A computer that sleeps is a receptor that sleeps.** Turn off sleep on the machine that runs
it. We once missed hours of outage because the Mac that watched the fleet was asleep.

## What was measured

All numbers in this README come from a lab run between 22-Sep and 7-Oct-2026:

- 23-sep, M4.5 near Chaparral: the emulator 19.5 km away got the alert, three others
  478 km or more away did not. Google's radius for M4.5 is 31 km.
- 24-sep, M4.48 near Chaparral: an emulator on AWS (no Google account, x86_64, Brazilian
  IP) got the early warning at +18.1 s. Origin to push on a test phone: about 18.8 s.
- The emulator does not take part in detection. In 18 hours of sensor logs, nothing in
  Play Services' earthquake code read the accelerometer. Injecting accelerometer data is
  possible but goes nowhere, and could harm a system that warns millions if it did.
- Play Services updates the location for AEA at most every 5 minutes and only after a move
  of more than 1 km.
- Google's alert radius follows a table by magnitude, not a model. Interpolating it matched
  the real radius with a median error of 0.4 km on 69 Colombian alerts from Allen et al.
  2025 ([Zenodo 15498729](https://doi.org/10.5281/zenodo.15498729)). It barely accounts for
  depth: Bucaramanga, with its deep nest of quakes, gets the most alerts in Colombia.
- In Colombia, none of 65 alerts in three years was the full-screen "TakeAction" type, only
  normal notifications.

## History

This started in September 2026 as a plan for a paid iPhone app in Colombia and Chile. The
system then had more parts: a fleet of emulators on AWS spot servers, a gateway that pushed
through Apple's push service (APNs) and Web Push, a native iOS app with a subscription, and
a team of AI coding agents doing most of the work under one person.

That plan was dropped on 7-Oct-2026, before launch. The terms problem above had no good
answer for a paid product. The servers cost money every month whether anyone used them or
not. The author also could not keep working on it next to another project.

What is left is the part that works for one person or one family on their own computer,
with no server and no account of ours in the middle. The AWS fleet, the gateway and the iOS
app are not in this repository.

## Ideas not done

- Read AEA's own location age from `dumpsys` and reboot only when needed, instead of every
  18 hours.
- A shared receptor for a neighborhood or a town, with one ntfy topic many people follow.
- A proper permission from Google, or access to the official alert feed from a national
  seismological service, would make all of this unnecessary. That is the real fix.

## License

MIT. See [LICENSE](LICENSE). Not affiliated with Google. Android Earthquake Alerts is a
Google service.
