# Next features: health notices, missed-quake check, following receptors

Decided with the owner on 7-Oct-2026. Canarito will tell someone when it stops working, report quakes it should have caught and did not, and cover people where they are instead of only at home. Build order: health notices, then the missed-quake check, then following receptors. The same change removes the "An unexplained miss" row from the README and canarito.app (replaced by a rule: never sign in to a Google account in the emulator) and rewrites "The place is fixed".

## Terms

- **receptor**: one Android emulator that `canarito.py` runs at one location and that forwards Google's alerts to one ntfy link. Avoid: sensor, node, device.
- **fixed receptor**: a receptor that stays at a place (home, the parents' house). Desktops, Home Assistant and lights subscribe to it. Avoid: static receptor.
- **following receptor**: a receptor that moves to wherever one person's phone is. Avoid: mobile receptor, travel mode.
- **move**: changing a running receptor's position with one geo fix. The emulator keeps running; nothing is rebuilt. Avoid: rebuild, recreate.
- **asleep**: a following receptor whose emulator is stopped (not deleted) while its person is home. Its Google registration survives the stop. Avoid: destroyed, deleted.
- **alert link**: the ntfy link the family subscribes to: alerts, plus one message if a receptor stays down more than 1 hour. Avoid: user link.
- **admin link**: a second ntfy link only for whoever runs the computer: health notices and missed-quake reports, never alert text. Avoid: debug link, log link.
- **location link**: an ntfy link (or a local URL) where a phone posts its position for a following receptor. Only Canarito reads it. Avoid: tracking link.
- **health notice**: a message `canarito.py` sends when a receptor stops being able to get alerts, and another when it recovers. Avoid: alarm, alert.
- **missed-quake report**: a message sent minutes after a quake that a public catalog lists inside Google's alert radius of a receptor, when that receptor recorded no alert. Avoid: missed alert warning.

## Why

The owner: Canarito should warn on its own if something went wrong, for example a quake that happened and was not detected. A receptor that only covers home is wrong for people who move; Canarito should create coverage where the user goes and support every member of a family. It must be minimally smart and not waste resources. Out of the box it should just work, with the integration points left open for anyone to extend by pull request. It is an open-source project, so nothing may be specific to Colombia.

## Locked decisions

### Following receptors get their position through one contract (Q3: D)

`canarito.py` reads a JSON message with `lat` and `lon` (optional `name`) from a location link. Any app can feed it. This is also the shape OwnTracks already sends (`_type: location`, `lat`, `lon`), so OwnTracks works without a bridge.

- Out of the box: `canarito.py setup --name ana --follow` creates the location link and prints an OwnTracks setup link and a QR code. Ana installs OwnTracks, scans or taps it, and her phone starts feeding the receptor with no typing.
- The README documents the contract and gives recipes for OwnTracks, Home Assistant (an automation that posts the person's position) and an iPhone Shortcut automation. New recipes come by pull request.
- Messages that do not match the contract are rejected and reported on the admin link, never ignored silently.
- `canarito.py` rounds the position to about 1 km before using it. Google needs no more than that.

Rejected:
- A: OwnTracks to a private ntfy link, as the only path. It is now the out-of-the-box recipe inside D, not separate code.
- B: OwnTracks straight to the computer. It keeps the position at home, but it needs a port opened or Tailscale for every user, which is where self-hosted projects lose people. Anyone who wants it runs their own ntfy, which D supports with no extra code.
- C: Home Assistant as its own integration. It becomes a recipe inside D.

### Where a traveller's position passes by default (Q9: C)

The default location link is a random ntfy.sh topic with `?cache=no`, so ntfy.sh passes each message on and stores nothing. `setup --follow` says plainly that ntfy.sh still sees the position in transit, and prints the one option that switches to your own ntfy server.

Rejected:
- A: the same default without saying anything. It hides a real trade-off about a person's location.
- B: refuse ntfy.sh for positions and require your own server. It is the most private, but it puts a server in front of first-time users, which is exactly what this project removed.

### What a following receptor does at home and on the road (Q8: D)

- On the road: the emulator keeps running. `canarito.py` sends a new position only when the person moved more than 1 km, at most every 5 minutes. That matches Google's own limits (it takes a new location at most every 5 minutes and only after more than 1 km), so the receptor trails a car by a few minutes and costs nothing extra.
- At home: after 30 minutes within 5 km of a fixed receptor, the following receptor falls asleep (its emulator stops, its files stay). While it sleeps, the fixed receptor also sends its alerts to that person's link.
- Leaving: when the person is more than 5 km from every fixed receptor, the following receptor wakes. It needs about 3 minutes to boot and up to 5 more for Google to take the position. Meanwhile the person is still near home, inside the fixed receptor's alert radius (31 km even for an M4.5).

Rejected:
- A: always running, the traveller follows only their own link. Simple and correct, but it holds about 4 GB per person all day at home for coverage the fixed receptor already gives.
- B: quiet near a fixed receptor but running. It saves no resources and adds a rule that can fail when it matters.
- C: accept the double alert. It teaches people to ignore alerts.

## Routine choices

- Q1: health notices go to the admin link. If a receptor stays down more than 1 hour, the alert link also gets one plain message, and another when it is back. Full logs stay in the terminal and in `canarito.py evidence`; they never go to the phone.
- Q4: problems that send a health notice, each once when it starts and once when it ends, never repeated:
  - the emulator is not running or not answering for more than 5 minutes;
  - Google's earthquake service is not registered 90 minutes after a boot;
  - setup inside the emulator failed (app missing, config not written, listener not allowed);
  - a following receptor got no position for more than 1 hour;
  - after the computer wakes from sleep: "was asleep from 02:10 to 06:45, no coverage then".
  A dead internet connection cannot be reported this way; `--heartbeat-url` with an outside service such as healthchecks.io covers that, and the README says so.
- Q2: a quake inside the radius computed from the catalog magnitude is reported as missed. One inside the radius only for magnitude + 0.5 is reported as possibly missed, marked as uncertain.
- Q5: missed-quake reports go to the admin link only.
- Q7: catalogs are USGS and EMSC, both worldwide, by default. National catalogs are small optional adapters that turn their feed into one shared event format. Colombia's SGC is the first adapter; others come by pull request. Events from different sources are matched by time and place, so one quake is reported once.
- Q6: when the receptors on a computer would need more than 75% of its RAM (about 4 GB each), `setup` warns and continues.
- Usage recommendations go in the README and on canarito.app: one computer for the whole family, one fixed receptor for home, one following receptor per person who travels, about 4 GB of RAM each. A 16 GB computer fits home plus two travellers with room left for normal use.

## Verified facts

- A move needs no reboot: with the GPS keeper running, a far move reached Google in a median 244 s and at most 306 s over 7 moves (lab run, 27-Sep-2026).
- Google's earthquake code asks for location at most every 5 minutes and only after a move of more than 1 km (`minUpdateInterval=5m`, `minUpdateDistance=1000.0` in the Play Services dump).
- Google registration survives a stopped emulator: after 10 minutes, 5 hours and 30 hours stopped, every registered emulator was registered again after boot (28 and 29-Sep-2026).
- A new emulator took 13 to 60 minutes to register with Google's earthquake service; 1 in 8 never did. The local test on 7-Oct registered in about 20 minutes.
- Google's alert radius follows a table by magnitude (M4.5 31 km, M5 78 km, M5.5 197 km, M6 346 km, M6.5 443 km, M7 about 560 km, M7.8 669 km), built from 1,279 alerts worldwide (Allen et al. 2025). Its match with the real radius was only checked on 69 Colombian alerts (median error 0.4 km).
- Google's magnitude differs from catalogs: one quake was M3.6 for the SGC and M4.46 for Google. USGS never listed the M4.5 of 23-Sep-2026 near Chaparral.
- OwnTracks posts JSON with `lat` and `lon` to any HTTP URL. ntfy accepts `?cache=no` on a publish to skip storing the message.
- An emulator with a personal Google account missed an early alert that one without an account got (24-Sep-2026). `setup` never signs in to an account.

## Risks

- The missed-quake check is only as good as the catalogs and the radius table. Expect some false "possibly missed" reports and some real misses it does not catch.
- A traveller who leaves home fast relies on the fixed receptor for the first minutes, until their own receptor wakes and Google takes the position.
- Positions pass through ntfy.sh by default. It does not store them, but it sees them.
- More logic in `canarito.py` (sleep, wake, catalogs) means more ways to fail. Each piece needs its own test, and every failure must reach the admin link.
- A warning about RAM can scroll past; a receptor killed for lack of memory then shows up only as a health notice.

## Deferred

None.

## Open threads

None.
