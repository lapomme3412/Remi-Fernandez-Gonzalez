# Nouvel'air Coiffure — site vitrine

Site statique (HTML/CSS/JS, sans dépendance). Ouvrir `index.html` ou publier sur GitHub Pages / Netlify.

## À personnaliser
- **Photos** : déposer dans `images/` → `hero.jpg` (bannière), `salon.jpg` (section salon), `galerie-1.jpg` … `galerie-9.jpg`. Sans fichier, des tuiles de couleur s'affichent. Utilisez uniquement des photos dont le salon détient les droits.
- **Coordonnées** : adresse, téléphone (`index.html`, `tel:+33000000000`), e-mail (`SALON_EMAIL` dans `script.js`).
- **Horaires** : tableau dans `index.html` + objet `HOURS` dans `script.js` (statut « Ouvert maintenant »).
- **Tarifs & avis** : textes d'exemple à remplacer.
- **Carte** : dans `.map` de `index.html`, remplacer le texte par l'iframe Google Maps du salon.
- **Rendez-vous** : le formulaire ouvre le mail du client. Pour un envoi direct, brancher Formspree/Netlify Forms ou un lien Planity/Calendly.
