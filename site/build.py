#!/usr/bin/env python3
"""Writes canarito.app in Spanish (/) and English (/en/): python3 site/build.py"""
from html import escape
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent / "public"
REPO = "https://github.com/sebospc/canarito"

PAGES = {
    "es": {
        "path": "index.html", "home": "/", "other": "/en/", "other_label": "English", "other_lang": "en",
        "title": "Canarito: avisos de sismo en cualquier dispositivo",
        "description": "Canarito corre en tu computador y manda los avisos de sismo de Android a tu iPhone, tu computador o lo que quieras. Gratis y de código abierto.",
        "og": "/og.png", "locale": "es_CO",
        "h1": "Unos segundos pueden cambiarlo todo.",
        "claim": "Los avisos de sismo de Android, en cualquier dispositivo.",
        "lead": "Canarito corre en tu computador y manda los avisos de sismo a tu iPhone, a tu computador o a lo que quieras. Gratis y de código abierto.",
        "button": "Ver en GitHub",
        "caveat": 'No es oficial y puede fallar. <a href="#fallas">Lee qué puede fallar</a>.',
        "phone_alt": "Celular bloqueado con la notificación de ntfy: Alerta de sismo",
        "laptop_alt": "Computador con la notificación del navegador",
        "lamp": "La luz de la sala, por Home Assistant",
        "now": "ahora",
        "alts": ("Sismo, Google, receptores en tu computador, ntfy y cualquier aparato suscrito",
                 "Instala ntfy, suscríbete a tu enlace y el próximo aviso llega a ese aparato",
                 "Tiempo de aviso por distancia: nada a 20 y 50 km, unos 10 s a 100 km, 38 s a 200 km, 67 s a 300 km"),
        "how_h": "Cómo funciona",
        "how_p": "Google decide quién recibe un aviso según la ubicación que reporta cada aparato. Un emulador de Android con una ubicación fija basta.",
        "how_1": "<strong>Probado con sismos reales.</strong> En septiembre de 2026, dos sismos en Colombia llegaron a nuestros emuladores. Los que estaban dentro del radio del aviso lo recibieron; los que estaban a 478 km, no.",
        "how_2": "<strong>Sin servidor.</strong> El emulador corre en tu computador y ntfy, un servicio gratis, lleva el aviso a tus aparatos. Si quieres todo bajo tu control, puedes montar tu propio ntfy.",
        "connect_h": "Conecta lo que quieras",
        "connect_p": "Canarito manda cada aviso a un enlace privado de ntfy. Todo lo que se suscriba a ese enlace lo recibe.",
        "connect_1": '<strong>Celular y computador.</strong> La app ntfy en <a href="https://apps.apple.com/app/ntfy/id1625396347">iPhone</a> y <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy">Android</a>, o <a href="https://ntfy.sh/app">ntfy.sh/app</a> en cualquier navegador.',
        "connect_2": "<strong>Algo más fuerte.</strong> Una sirena, un parlante o una luz con Home Assistant, o tu propio script. En iPhone, ntfy no suena en modo silencio: Apple guarda eso para las apps oficiales de alertas.",
        "follow_h": "Te sigue a donde vayas",
        "follow_p": "Un receptor puede seguir el celular de una persona en vez de quedarse en un lugar. La app OwnTracks le dice a tu computador dónde estás, y Canarito mueve el receptor contigo.",
        "follow_1": "<strong>Sin desperdiciar memoria.</strong> Cuando llegas a casa, tu receptor se duerme y el de la casa te avisa a ti también. Cuando sales, se despierta donde estés. La posición se redondea a 1 km.",
        "follow_2": "<strong>Un computador para toda la familia.</strong> Un receptor fijo para la casa y uno que sigue a cada persona que viaja, unos 4 GB de memoria cada uno. Un computador de 16 GB alcanza para la casa y dos personas fuera al tiempo.",
        "warn_h": "Cuánto aviso tienes",
        "warn_p": "Depende de qué tan lejos estés del epicentro. Google dice que solo el 36% de sus propios usuarios recibe el aviso antes del temblor.",
        "risks_h": "Qué puede fallar",
        "risks_p": "Léelo antes de confiar en Canarito para algo importante. Canarito te avisa por un enlace aparte cuando algo falla, y cuando hubo un sismo cerca que no le llegó.",
        "risks": (
            ("Los términos de Google", "La licencia del emulador es solo para desarrollar apps, y los datos de Google no se pueden redistribuir sin permiso. Usarlo es decisión tuya."),
            ("Google lo puede apagar", "Su sistema contra abusos lee los sensores del emulador. En nuestras pruebas no bloqueó los avisos, y si eso cambia nadie te va a avisar."),
            ("Ubicación vieja", "Un emulador con una ubicación de unas 25 horas se perdió un aviso. Canarito lo reinicia cada 18 horas, y cada reinicio deja unos 10 minutos sin cobertura."),
            ("El servicio de Google nunca arranca", "Uno de cada ocho emuladores nuevos nunca se registró. A los 90 minutos Canarito te avisa por el enlace de administración para que lo crees de nuevo."),
            ("Un receptor que sigue llega tarde", "Se mueve como mucho cada 5 minutos y Google tarda unos minutos más, así que los primeros minutos después de un viaje largo pueden quedar sin cobertura. Si OwnTracks deja de enviar, se queda en el último lugar conocido; a las 6 horas sin posición te avisamos."),
            ("Duplicados", "Un reintento puede mandar el mismo aviso dos veces. Preferimos dos veces a ninguna."),
            ("Enlaces públicos", "Quien conozca el nombre de un tema en ntfy.sh lo puede leer. Canarito inventa un nombre al azar: no lo compartas fuera de tu familia."),
            ("El computador dormido", "Si el computador se suspende, el receptor se detiene. Al despertar, Canarito te dice cuánto tiempo estuvo sin cobertura. Desactiva la suspensión en ese equipo."),
        ),
        "start_h": "Empieza",
        "start_p": "Necesitas macOS o Linux, Python 3.9, Java 17 y las herramientas de línea de comandos de Android.",
        "comments": ("# la app que va dentro del emulador", "# tu lugar, desde cualquier mapa", "# déjalo corriendo"),
        "after": "La primera vez, el servicio de sismos de Google tarda de 15 a 60 minutos en arrancar dentro del emulador. Espera la línea <code>AEA registered</code>. Las instrucciones completas están en GitHub.",
        "footer_left": "Canarito · código abierto, licencia MIT",
        "footer_right": "No está afiliado a Google. Android Earthquake Alerts es un servicio de Google.",
    },
    "en": {
        "path": "en/index.html", "home": "/en/", "other": "/", "other_label": "Español", "other_lang": "es",
        "title": "Canarito: earthquake early warnings on any device",
        "description": "Canarito runs on your computer and sends Android's earthquake early warnings to your iPhone, your computer or anything else. Free and open source.",
        "og": "/og-en.png", "locale": "en_US",
        "h1": "A few seconds can change everything.",
        "claim": "Android's earthquake warnings, on any device.",
        "lead": "Canarito runs on your computer and sends earthquake warnings to your iPhone, your computer or anything else you choose. Free and open source.",
        "button": "See it on GitHub",
        "caveat": 'Not official, and it can fail. <a href="#risks">Read what can go wrong</a>.',
        "phone_alt": "Locked phone with an ntfy notification: Earthquake alert",
        "laptop_alt": "Computer with the browser notification",
        "lamp": "The living room light, through Home Assistant",
        "now": "now",
        "alts": ("Quake, Google, receptors on your computer, ntfy, and any device that subscribes",
                 "Install ntfy, subscribe to your link, and the next alert arrives on that device",
                 "Warning time by distance: none at 20 and 50 km, about 10 s at 100 km, 38 s at 200 km, 67 s at 300 km"),
        "how_h": "How it works",
        "how_p": "Google picks who gets an alert by the location each device reports. An Android emulator with a fixed location is enough.",
        "how_1": "<strong>Tested with real quakes.</strong> In September 2026, two quakes in Colombia reached our emulators. The ones inside the alert radius got the warning; the ones 478 km away did not.",
        "how_2": "<strong>No server.</strong> The emulator runs on your computer, and ntfy, a free service, carries the alert to your devices. If you want everything under your control, run your own ntfy.",
        "connect_h": "Connect anything",
        "connect_p": "Canarito sends every alert to a private ntfy link. Anything subscribed to that link gets it.",
        "connect_1": '<strong>Phone and computer.</strong> The ntfy app on <a href="https://apps.apple.com/app/ntfy/id1625396347">iPhone</a> and <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy">Android</a>, or <a href="https://ntfy.sh/app">ntfy.sh/app</a> in any browser.',
        "connect_2": "<strong>Something louder.</strong> A siren, a speaker or a light through Home Assistant, or your own script. On iPhone, ntfy cannot ring through silent mode: Apple keeps that for official alert apps.",
        "follow_h": "It follows you",
        "follow_p": "A receptor can follow one person's phone instead of staying at a place. The OwnTracks app tells your computer where you are, and Canarito moves the receptor with you.",
        "follow_1": "<strong>No wasted memory.</strong> When you get home, your receptor sleeps and the home receptor alerts you too. When you leave, it wakes up wherever you are. Positions are rounded to 1 km.",
        "follow_2": "<strong>One computer for the whole family.</strong> One fixed receptor for home and one following receptor per person who travels, about 4 GB of memory each. A 16 GB computer fits home and two people away at the same time.",
        "warn_h": "How much warning you get",
        "warn_p": "It depends on how far you are from the epicenter. Google says only 36% of its own users get the alert before the shaking.",
        "risks_h": "What can go wrong",
        "risks_p": "Read this before you trust Canarito with anything important. Canarito tells you on a separate link when something breaks, and when a nearby quake reached no alert.",
        "risks": (
            ("Google's terms", "The emulator license covers app development only, and Google's data may not be redistributed without permission. Running this is your decision."),
            ("Google can stop it", "Its anti-abuse system reads the emulator's sensors. It did not block alerts in our tests, and nobody will tell you if that changes."),
            ("Old location", "An emulator with a location about 25 hours old missed an alert. Canarito reboots it every 18 hours, and each reboot leaves about 10 minutes without coverage."),
            ("Google's service never starts", "One in eight new emulators never registered. After 90 minutes Canarito tells you on the admin link so you can create it again."),
            ("A following receptor trails", "It moves at most every 5 minutes and Google takes a few minutes more, so the first minutes after a long trip can be uncovered. If OwnTracks stops sending, it stays at the last known place; after 6 hours without a position we tell you."),
            ("Duplicates", "A retry can send the same alert twice. We chose twice over never."),
            ("Public links", "Anyone who knows an ntfy.sh topic name can read it. Canarito picks a random name: keep it within your family."),
            ("A sleeping computer", "If the computer suspends, the receptor stops. When it wakes, Canarito tells you how long it had no coverage. Turn off sleep on that machine."),
        ),
        "start_h": "Start",
        "start_p": "You need macOS or Linux, Python 3.9, Java 17 and the Android command line tools.",
        "comments": ("# the app that goes inside the emulator", "# your place, from any map", "# leave it running"),
        "after": "The first time, Google's earthquake service takes 15 to 60 minutes to start inside the emulator. Wait for the line <code>AEA registered</code>. Full instructions are on GitHub.",
        "footer_left": "Canarito · open source, MIT license",
        "footer_right": "Not affiliated with Google. Android Earthquake Alerts is a Google service.",
    },
}

BIRD = "M8 64 C27 72 33 40 57 33 C70 29 79 34 84 41 L95 44 L84 49 C80 65 63 75 40 73"
BELL = "M10 27V19a10 10 0 0 1 20 0v8l2.5 3.5h-25zM16.5 34.5a3.5 3.5 0 0 0 7 0"
BULB = "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"


def page(lang, t):
    risks_id = "fallas" if lang == "es" else "risks"
    risks = "".join(f'<div class="risk"><b>{escape(name)}</b><p>{escape(text)}</p></div>' for name, text in t["risks"])
    build, setup, run = t["comments"]
    mesh_alt, connect_alt, warning_alt = (escape(alt) for alt in t["alts"])
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t["title"])}</title>
<meta name="description" content="{escape(t["description"])}">
<meta name="referrer" content="no-referrer">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" hreflang="{t["other_lang"]}" href="https://canarito.app{t["other"]}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://canarito.app{t["home"]}">
<meta property="og:title" content="{escape(t["title"])}">
<meta property="og:description" content="{escape(t["description"])}">
<meta property="og:image" content="https://canarito.app{t["og"]}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{t["locale"]}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<div class="wrap">
<header>
  <a class="brand" href="{t["home"]}" aria-label="Canarito"><svg viewBox="0 0 100 100" aria-hidden="true"><path d="{BIRD}" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="wm">Canarito</span></a>
  <a class="lang" href="{t["other"]}" hreflang="{t["other_lang"]}" lang="{t["other_lang"]}">{t["other_label"]}</a>
</header>
<main>
<div class="hero">
  <h1>{escape(t["h1"])}</h1>
  <p class="claim">{escape(t["claim"])}</p>
  <p class="lead">{escape(t["lead"])}</p>
  <div class="actions"><a class="button" href="{REPO}">{escape(t["button"])}</a><p class="caveat">{t["caveat"]}</p></div>
  <div class="trio">
    <div class="phone" role="img" aria-label="{escape(t["phone_alt"])}"><div class="screen"><div class="island"></div>
      <p class="clock">10:24</p>
      <div class="notif"><span class="ntfy"><svg viewBox="0 0 40 40" aria-hidden="true"><path d="{BELL}" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span><div><b>Alerta de sismo</b>Sismo M4.5 cerca de tu zona. Protégete ahora.</div></div>
    </div></div>
    <div class="laptop" role="img" aria-label="{escape(t["laptop_alt"])}"><div class="lid"><div class="web"><div class="bar"></div>
      <div class="toast"><b>Alerta de sismo</b>Sismo M4.5 cerca de tu zona. Protégete ahora.<br><span>ntfy.sh · {t["now"]}</span></div></div></div><div class="base"></div></div>
    <div class="lamp"><div class="glow"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="{BULB}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>{escape(t["lamp"])}</div>
  </div>
</div>

<section>
  <h2>{escape(t["how_h"])}</h2>
  <p>{escape(t["how_p"])}</p>
  <div class="figwrap"><img class="figure" src="/img/mesh-{lang}.svg" alt="{mesh_alt}" width="1200" height="556"></div>
  <div class="notes"><p>{t["how_1"]}</p><p>{t["how_2"]}</p></div>
</section>

<section>
  <h2>{escape(t["connect_h"])}</h2>
  <p>{escape(t["connect_p"])}</p>
  <div class="figwrap"><img class="figure" src="/img/connect-{lang}.svg" alt="{connect_alt}" width="1200" height="388"></div>
  <div class="notes"><p>{t["connect_1"]}</p><p>{t["connect_2"]}</p></div>
</section>

<section>
  <h2>{escape(t["follow_h"])}</h2>
  <p>{escape(t["follow_p"])}</p>
  <div class="notes"><p>{t["follow_1"]}</p><p>{t["follow_2"]}</p></div>
</section>

<section>
  <h2>{escape(t["warn_h"])}</h2>
  <p>{escape(t["warn_p"])}</p>
  <div class="figwrap"><img class="figure" src="/img/warning-{lang}.svg" alt="{warning_alt}" width="1200" height="570"></div>
</section>

<section id="{risks_id}">
  <h2>{escape(t["risks_h"])}</h2>
  <p>{escape(t["risks_p"])}</p>
  <div class="risks">{risks}</div>
</section>

<section>
  <h2>{escape(t["start_h"])}</h2>
  <p>{escape(t["start_p"])}</p>
<pre><code>git clone {REPO}.git && cd canarito
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew :android:assembleDebug                                  <span class="c">{escape(build)}</span>
python3 canarito.py setup --name home --lat 4.711 --lon -74.072   <span class="c">{escape(setup)}</span>
python3 canarito.py run --name home                               <span class="c">{escape(run)}</span></code></pre>
  <p class="after">{t["after"]}</p>
  <div class="actions"><a class="button" href="{REPO}">{escape(t["button"])}</a></div>
</section>
</main>
<footer><span>{escape(t["footer_left"])}</span><span>{escape(t["footer_right"])}</span></footer>
</div>
</body>
</html>
'''


PRIVACY = {
    "es": {
        "path": "privacy/index.html", "home": "/", "other": "/en/privacy/", "other_label": "English", "other_lang": "en", "locale": "es_CO",
        "title": "Privacidad de Canarito", "description": "Qué envía la app de Canarito, a quién y qué se queda en tu iPhone.",
        "h1": "Privacidad de la app de Canarito", "updated": "Última actualización: 10 de octubre de 2026.",
        "intro": "Canarito es gratis y de código abierto. No hay empresa detrás, ni cuentas, ni correo. Esta página dice qué envía la app de iPhone, a quién y qué guarda.",
        "sections": (
            ("Lo que envía la app", (
                "A tu servidor, el que vinculaste con el QR: tu posición redondeada a dos decimales (unos 1 km), cuando te mueves más de 1 km y una vez al vincular. Un identificador de push de tu iPhone, sellado para que solo el relé de Canarito lo pueda abrir. Un nombre para el dispositivo, el genérico que iOS da a las apps.",
                "Al relé de Canarito, cuando vinculas y cada vez que Apple cambia el token de tu iPhone: ese token, para recibir el identificador sellado.",
            )),
            ("Lo que no envía", (
                "Tu posición exacta no sale del iPhone. La app no tiene cuentas, anuncios, análisis ni rastreo, y no usa SDK de terceros. La cámara solo lee el QR para vincular, y no guarda nada.",
            )),
            ("Quién es responsable", (
                "Quien administra tu servidor es responsable de lo que ese servidor guarda y por cuánto tiempo. Pregúntale. Puede ver tu posición redondeada, el nombre del dispositivo y el identificador de push. Canarito no tiene un servidor propio y no recibe tus datos.",
            )),
            ("El relé de avisos", (
                "El aviso va de tu servidor al relé, del relé a Apple y de Apple a tu iPhone. El relé es de código abierto (carpeta relay del repositorio). No guarda tokens, vinculaciones ni avisos, y sus registros solo tienen códigos de estado e identificadores de servidor. Apple procesa los avisos según sus propias políticas.",
            )),
            ("Lo que se queda en tu iPhone", (
                "El servidor vinculado y el nombre de tu receptor, la clave del dispositivo (en el llavero de iOS), la última posición enviada y los identificadores de los últimos 50 avisos, para que un mismo aviso no suene dos veces.",
            )),
            ("Cómo borrar tus datos", (
                "En Ajustes de la app, «Desvincular este iPhone» pide al servidor que borre el dispositivo y borra los datos de la app. Si el servidor no responde, quien lo administra puede quitarlo. Borrar la app quita lo que está en el iPhone.",
            )),
            ("Contacto y cambios", (
                "Escribe en los issues de github.com/sebospc/canarito. Los cambios a esta página quedan en el historial del repositorio.",
            )),
        ),
        "footer_left": "Canarito · código abierto, licencia MIT", "footer_right": "No es un sistema oficial de alertas.",
    },
    "en": {
        "path": "en/privacy/index.html", "home": "/en/", "other": "/privacy/", "other_label": "Español", "other_lang": "es", "locale": "en_US",
        "title": "Canarito privacy", "description": "What the Canarito app sends, to whom, and what stays on your iPhone.",
        "h1": "Canarito app privacy", "updated": "Last updated: 10 October 2026.",
        "intro": "Canarito is free and open source. There is no company behind it, no accounts and no email. This page says what the iPhone app sends, to whom, and what it keeps.",
        "sections": (
            ("What the app sends", (
                "To your server, the one you linked with the QR: your position rounded to two decimals (about 1 km), when you move more than 1 km and once when you link. A push identifier of your iPhone, sealed so only the Canarito relay can open it. A name for the device, the generic one iOS gives apps.",
                "To the Canarito relay, when you link and each time Apple changes your iPhone's token: that token, to get the sealed identifier back.",
            )),
            ("What it does not send", (
                "Your exact position never leaves the iPhone. The app has no accounts, ads, analytics or tracking, and uses no third-party SDK. The camera only reads the QR to link, and saves nothing.",
            )),
            ("Who is responsible", (
                "Whoever runs your server is responsible for what that server stores and for how long. Ask them. They can see your rounded position, the device name and the push identifier. Canarito has no server of its own and does not receive your data.",
            )),
            ("The alert relay", (
                "The alert goes from your server to the relay, from the relay to Apple, and from Apple to your iPhone. The relay is open source (the relay folder of the repository). It stores no tokens, pairings or alerts, and its logs hold only status codes and server ids. Apple handles alerts under its own policies.",
            )),
            ("What stays on your iPhone", (
                "The linked server and your receptor's name, the device key (in the iOS Keychain), the last position sent, and the ids of the last 50 alerts, so the same alert does not ring twice.",
            )),
            ("How to delete your data", (
                "In the app's Settings, \"Unlink this iPhone\" asks the server to delete the device and clears the app's data. If the server does not answer, whoever runs it can remove it. Deleting the app removes what is on the iPhone.",
            )),
            ("Contact and changes", (
                "Write in the issues of github.com/sebospc/canarito. Changes to this page stay in the repository history.",
            )),
        ),
        "footer_left": "Canarito · open source, MIT license", "footer_right": "Not an official alert system.",
    },
}


SUPPORT = {
    "es": {
        "path": "support/index.html", "home": "/", "other": "/en/support/", "other_label": "English", "other_lang": "en", "locale": "es_CO",
        "title": "Ayuda de Canarito", "description": "Cómo vincular la app de Canarito, probar un aviso y pedir ayuda.",
        "h1": "Ayuda de la app de Canarito", "updated": "Última actualización: 17 de octubre de 2026.",
        "intro": "Canarito hace sonar tu iPhone cuando el receptor de tu servidor recibe una alerta temprana de sismo. Es gratis, sin cuentas y sin compras.",
        "sections": (
            ("Vincular tu iPhone", (
                "Necesitas un servidor de Canarito, tuyo o de alguien de confianza. Quien lo administra te da un QR o un enlace. Abre la app, escanea el QR o pega el enlace y toca Vincular.",
            )),
            ("Probar que funciona", (
                "En Ajustes de la app, toca «Enviar aviso de prueba». En unos segundos llega una notificación de prueba.",
            )),
            ("Si no llegan avisos", (
                "Revisa que las notificaciones de Canarito estén activas en los Ajustes del iPhone. Si la app dice que el servidor o el receptor no responden, avisa a quien administra tu servidor.",
            )),
            ("Contacto", (
                "Escríbenos a bandada.team@gmail.com.",
            )),
        ),
        "footer_left": "Canarito · código abierto, licencia MIT", "footer_right": "No es un sistema oficial de alertas.",
    },
    "en": {
        "path": "en/support/index.html", "home": "/en/", "other": "/support/", "other_label": "Español", "other_lang": "es", "locale": "en_US",
        "title": "Canarito support", "description": "How to link the Canarito app, test an alert and get help.",
        "h1": "Canarito app support", "updated": "Last updated: 17 October 2026.",
        "intro": "Canarito sounds your iPhone when your server's receptor gets an earthquake early warning. It is free, with no accounts and no purchases.",
        "sections": (
            ("Link your iPhone", (
                "You need a Canarito server, your own or one run by someone you trust. Whoever runs it gives you a QR code or a link. Open the app, scan the QR or paste the link, and tap Link.",
            )),
            ("Test that it works", (
                "In the app's Settings, tap \"Send a test alert\". A test notification arrives in a few seconds.",
            )),
            ("If alerts do not arrive", (
                "Check that notifications for Canarito are on in the iPhone Settings. If the app says the server or the receptor is not responding, tell whoever runs your server.",
            )),
            ("Contact", (
                "Write to bandada.team@gmail.com.",
            )),
        ),
        "footer_left": "Canarito · open source, MIT license", "footer_right": "Not an official alert system.",
    },
}


def privacy_page(lang, t):
    body = "".join(f"<h2>{escape(heading)}</h2>" + "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)
                   for heading, paragraphs in t["sections"])
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t["title"])}</title>
<meta name="description" content="{escape(t["description"])}">
<meta name="referrer" content="no-referrer">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" hreflang="{t["other_lang"]}" href="https://canarito.app{t["other"]}">
<meta property="og:title" content="{escape(t["title"])}">
<meta property="og:locale" content="{t["locale"]}">
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<div class="wrap">
<header>
  <a class="brand" href="{t["home"]}" aria-label="Canarito"><svg viewBox="0 0 100 100" aria-hidden="true"><path d="{BIRD}" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="wm">Canarito</span></a>
  <a class="lang" href="{t["other"]}" hreflang="{t["other_lang"]}" lang="{t["other_lang"]}">{t["other_label"]}</a>
</header>
<main class="doc">
  <h1>{escape(t["h1"])}</h1>
  <p class="updated">{escape(t["updated"])}</p>
  <p class="lead">{escape(t["intro"])}</p>
  {body}
</main>
<footer><span>{escape(t["footer_left"])}</span><span>{escape(t["footer_right"])}</span></footer>
</div>
</body>
</html>
'''


if __name__ == "__main__":
    for lang, strings in PAGES.items():
        target = PUBLIC / strings["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(lang, strings))
    for lang, strings in [*PRIVACY.items(), *SUPPORT.items()]:
        target = PUBLIC / strings["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(privacy_page(lang, strings))
