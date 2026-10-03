(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Photos de la galerie : déposer les fichiers dans /images (galerie-1.jpg …) puis ajuster ce nombre.
  const PHOTOS = Array.from({ length: 9 }, (_, i) => `images/galerie-${i + 1}.jpg`);
  const COLORS = [['#7a3b1e','#d98e5a'],['#3a2a22','#8a6a52'],['#9b4a2c','#e0a37a'],['#2b3444','#6c7a92'],['#b8693a','#e8c9a8']];

  // Nav
  const nav = $('#nav'), fab = $('.fab'), burger = $('#burger'), menu = $('#menu');
  const onScroll = () => {
    nav.classList.toggle('solid', scrollY > 40);
    fab.classList.toggle('show', scrollY > innerHeight * .7);
  };
  addEventListener('scroll', onScroll, { passive: true }); onScroll();
  burger.addEventListener('click', () => {
    const o = menu.classList.toggle('open');
    burger.setAttribute('aria-expanded', o);
    nav.classList.add('solid');
  });
  $$('#menu a').forEach(a => a.addEventListener('click', () => { menu.classList.remove('open'); burger.setAttribute('aria-expanded', false); }));

  // Tabs
  $$('.tabs button').forEach(b => b.addEventListener('click', () => {
    $$('.tabs button').forEach(x => x.setAttribute('aria-selected', x === b));
    $$('.prices').forEach(p => p.hidden = p.dataset.panel !== b.dataset.tab);
  }));

  // Horaires : [ouverture, fermeture] en heures décimales, par jour (0 = dimanche)
  const HOURS = { 0: null, 1: null, 2: [9, 18.5], 3: [9, 18.5], 4: [9, 18.5], 5: [9, 18.5], 6: [8.5, 17] };
  const now = new Date(), d = now.getDay(), h = now.getHours() + now.getMinutes() / 60;
  $(`#hours tr[data-d="${d}"]`)?.classList.add('today');
  const t = HOURS[d], open = t && h >= t[0] && h < t[1];
  const fmt = x => `${Math.floor(x)}h${String(Math.round((x % 1) * 60)).padStart(2, '0')}`;
  let msg;
  if (open) msg = `Ouvert maintenant · jusqu'à ${fmt(t[1])}`;
  else {
    let n = d, add = 0; if (!(t && h < t[0])) { do { n = (n + 1) % 7; add++; } while (!HOURS[n]); }
    const days = ['dimanche','lundi','mardi','mercredi','jeudi','vendredi','samedi'];
    msg = `Fermé · ouvre ${add === 0 ? "aujourd'hui" : add === 1 ? 'demain' : days[n]} à ${fmt(HOURS[n][0])}`;
  }
  $('#openStatus').innerHTML = `<span class="dot ${open ? 'on' : ''}"></span>${msg}`;

  // Galerie (tuile colorée si l'image est absente)
  const gal = $('#gallery');
  PHOTOS.forEach((src, i) => {
    const b = document.createElement('button');
    const [c1, c2] = COLORS[i % COLORS.length];
    b.style.setProperty('--c1', c1); b.style.setProperty('--c2', c2);
    b.style.setProperty('--h', [300, 220, 360, 260][i % 4] + 'px');
    b.setAttribute('aria-label', `Agrandir la réalisation ${i + 1}`);
    const img = new Image(); img.loading = 'lazy'; img.alt = `Réalisation ${i + 1}`; img.src = src;
    img.onerror = () => { img.remove(); b.classList.add('empty'); b.dataset.missing = '1'; };
    b.append(img); b.addEventListener('click', () => b.dataset.missing || openLb(i));
    gal.append(b);
  });

  // Lightbox
  const lb = $('#lightbox'), lbImg = $('#lbImg'); let cur = 0;
  const avail = () => $$('button:not([data-missing])', gal);
  function openLb(i) { cur = i; show(); lb.hidden = false; document.body.style.overflow = 'hidden'; }
  function show() { lbImg.src = PHOTOS[cur]; }
  function step(n) { do { cur = (cur + n + PHOTOS.length) % PHOTOS.length; } while (gal.children[cur].dataset.missing && avail().length); show(); }
  function close() { lb.hidden = true; document.body.style.overflow = ''; }
  $('.lb-close').onclick = close; $('.prev').onclick = () => step(-1); $('.next').onclick = () => step(1);
  lb.addEventListener('click', e => e.target === lb && close());
  addEventListener('keydown', e => { if (lb.hidden) return; if (e.key === 'Escape') close(); if (e.key === 'ArrowLeft') step(-1); if (e.key === 'ArrowRight') step(1); });

  // Formulaire : ouvre le mail/SMS du client (aucun serveur requis). Adapter SALON_EMAIL.
  const SALON_EMAIL = 'contact@exemple.fr';
  const form = $('#rdvForm'), fm = $('#formMsg');
  form.date.min = new Date().toISOString().split('T')[0];
  form.addEventListener('submit', e => {
    e.preventDefault();
    let ok = true;
    ['nom', 'tel', 'presta', 'date'].forEach(n => { const bad = !form[n].value.trim(); form[n].classList.toggle('invalid', bad); ok = ok && !bad; });
    if (!ok) { fm.textContent = 'Merci de remplir les champs obligatoires.'; fm.style.color = '#d64545'; return; }
    const body = `Nom : ${form.nom.value}\nTéléphone : ${form.tel.value}\nPrestation : ${form.presta.value}\nDate : ${form.date.value} (${form.creneau.value})\n\n${form.msg.value}`;
    location.href = `mailto:${SALON_EMAIL}?subject=${encodeURIComponent('Demande de RDV — ' + form.nom.value)}&body=${encodeURIComponent(body)}`;
    fm.textContent = 'Votre application mail s\'ouvre pour envoyer la demande. Merci !'; fm.style.color = '#2f8f57';
  });

  // Reveal on scroll
  const io = new IntersectionObserver(es => es.forEach(x => x.isIntersecting && (x.target.classList.add('in'), io.unobserve(x.target))), { threshold: .12 });
  $$('.section .wrap > *, .reviews figure').forEach(el => { el.classList.add('reveal'); io.observe(el); });

  $('#year').textContent = new Date().getFullYear();
})();
