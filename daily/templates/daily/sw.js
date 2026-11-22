/* Chilavu service worker: offline shell + daily reminder */
const CACHE = "chilavu-v4";
const SHELL = ["/", "/signin/", "/static/daily/icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE && k !== "chilavu-settings").map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

/* network first, fall back to cache (pages + static). API is never cached. */
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/") || url.pathname === "/export.csv") return;
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok && (req.mode === "navigate" || url.pathname.startsWith("/static/"))) {
        const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy));
      }
      return res;
    }).catch(() => caches.match(req).then(r => r || caches.match("/")))
  );
});

/* ---------- daily reminder ---------- */
const iso = d => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);

async function getSettings() {
  const r = await (await caches.open("chilavu-settings")).match("/__reminder");
  return r ? r.json() : { on: false, hour: 21, last: "" };
}
async function saveSettings(s) {
  await (await caches.open("chilavu-settings")).put("/__reminder", new Response(JSON.stringify(s), { headers: { "Content-Type": "application/json" } }));
}

async function maybeRemind() {
  const s = await getSettings();
  const now = new Date(), today = iso(now);
  if (!s.on || now.getHours() < s.hour || s.last === today) return;
  let loggedToday = false;
  try {
    const r = await fetch("/api/expenses/?month=" + today.slice(0, 7), { credentials: "include" });
    if (r.ok) loggedToday = (await r.json()).some(t => t.date === today);
  } catch (e) {}
  if (loggedToday) return;
  s.last = today; await saveSettings(s);
  await self.registration.showNotification("Did you add today's spends?", {
    body: "You haven't added today's spends yet. Tap to add them now.",
    icon: "/static/daily/icons/icon-192.png",
    badge: "/static/daily/icons/icon-192.png",
    tag: "daily-reminder",
    data: { url: "/?add=1" }
  });
}

self.addEventListener("periodicsync", e => { if (e.tag === "daily-reminder") e.waitUntil(maybeRemind()); });
self.addEventListener("message", e => { if (e.data === "check-reminder") e.waitUntil(maybeRemind()); });

self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
    for (const c of list) { if ("focus" in c) { c.navigate(url); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
