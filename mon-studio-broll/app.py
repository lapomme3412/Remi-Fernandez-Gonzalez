"""Mon Studio B-roll : petite application locale pour l'API Higgsfield.

Tous les appels à l'API se font ici, côté serveur. La clé (HF_KEY) est lue
dans .env.local et n'est jamais affichée, journalisée ni renvoyée au navigateur.
"""
import json
import mimetypes
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_from_directory

DOSSIER = Path(__file__).parent
load_dotenv(DOSSIER / ".env.local")
load_dotenv(DOSSIER.parent / ".env.local")  # accepte aussi un .env.local à la racine du dépôt

import higgsfield_client  # noqa: E402  (après le chargement de la clé)
from higgsfield_client import Cancelled, Completed, Failed, InProgress, NSFW, Queued  # noqa: E402

from modeles import MODELES, construire_arguments  # noqa: E402

API = "https://api.higgsfield.ai"
GENERATIONS = DOSSIER / "generations"
HISTORIQUE = GENERATIONS / "historique.json"
GENERATIONS.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(DOSSIER / "static"), static_url_path="/static")
verrou = threading.Lock()
taches = {}          # id -> état de la génération en cours
urls_envoyees = {}   # nom de fichier -> URL publique (images déjà envoyées)


# ---------- clé : jamais exposée ----------
def cle():
    return (os.getenv("HF_KEY") or "").strip()


def cle_presente():
    return ":" in cle()


def masquer(obj):
    """Renvoie obj (JSON) avec toute trace de la clé remplacée par ***."""
    texte = json.dumps(obj, ensure_ascii=False)
    for morceau in {cle(), *cle().split(":")}:
        if morceau and len(morceau) >= 4:
            texte = texte.replace(morceau, "***")
    return json.loads(texte)


# ---------- historique ----------
def lire_historique():
    try:
        return json.loads(HISTORIQUE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def ajouter_historique(entree):
    with verrou:
        h = lire_historique()
        h.append(entree)
        HISTORIQUE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- appels Higgsfield ----------
def estimer(application, arguments):
    """POST /estimate/{modèle} -> {'credits': '...', 'usd': '...'}"""
    r = httpx.post(
        f"{API}/estimate/{application}",
        headers={"Authorization": f"Key {cle()}", "Content-Type": "application/json"},
        json=arguments,
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(message_http(r))
    return r.json()


def calculer_prix(reponse, arguments):
    """Renvoie (usd, approximatif). Certains modèles (ex. Seedance) ne donnent qu'une
    description des tarifs « $X par seconde à 480p, $Y à 720p, $Z à 1080p » :
    dans ce cas on calcule tarif × durée, et le résultat est approximatif."""
    try:
        return float(reponse["usd"]), False
    except (KeyError, TypeError, ValueError):
        pass
    texte = (reponse or {}).get("pricing_description") or ""
    m = re.search(r"\$([\d.]+) per second[^$]*?at 480p, \$([\d.]+) at 720p, and \$([\d.]+) at 1080p", texte)
    if m and arguments.get("duration"):
        tarifs = {"480p": float(m.group(1)), "720p": float(m.group(2)), "1080p": float(m.group(3))}
        tarif = tarifs.get(arguments.get("resolution", "720p"))
        if tarif:
            return round(tarif * int(arguments["duration"]), 4), True
    return None, False


def message_http(r):
    try:
        d = r.json().get("detail")
    except ValueError:
        d = None
    d = d if isinstance(d, str) else (json.dumps(d, ensure_ascii=False) if d else r.text[:300])
    explications = {
        401: "Clé invalide ou absente. Vérifie le fichier .env.local.",
        403: "Crédits insuffisants sur ton compte Higgsfield.",
        404: "Modèle introuvable pour ce compte.",
        422: "Paramètres refusés par l'API.",
        423: "Ce modèle est temporairement bloqué. Réessaie plus tard.",
        503: "Ce modèle est désactivé ou pas prêt. Réessaie plus tard.",
    }
    return f"{explications.get(r.status_code, 'Erreur de l’API')} (code {r.status_code}) — {d}"


def url_publique_image(nom_fichier):
    """Envoie une image déjà générée vers Higgsfield pour obtenir une URL publique."""
    chemin = (GENERATIONS / Path(nom_fichier).name)
    if not chemin.is_file():
        raise ValueError("Image introuvable dans generations/.")
    if chemin.name not in urls_envoyees:
        urls_envoyees[chemin.name] = higgsfield_client.upload_file(chemin)
    return urls_envoyees[chemin.name]


def sortie(resultat, type_):
    if type_ == "image":
        imgs = resultat.get("images") or []
        return imgs[0].get("url") if imgs else None
    v = resultat.get("video")
    return v.get("url") if isinstance(v, dict) else None


def telecharger(url, prefixe, type_):
    ext = os.path.splitext(urlparse(url).path)[1].lower() or (".jpg" if type_ == "image" else ".mp4")
    nom = f"{datetime.now():%Y%m%d-%H%M%S}-{prefixe}{ext}"
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with open(GENERATIONS / nom, "wb") as f:
            for bloc in r.iter_bytes():
                f.write(bloc)
    return nom


def executer(tid, onglet, formulaire):
    t = taches[tid]
    modele = MODELES[onglet]
    t["debut"] = time.time()
    try:
        image_url = None
        if onglet == "animer":
            t["etape"] = "Envoi de l'image…"
            image_url = url_publique_image(formulaire.get("image", ""))
        arguments = construire_arguments(onglet, formulaire, image_url)
        t["requete"] = {"application": modele["id"], "arguments": arguments}

        cout = None
        try:
            cout = calculer_prix(estimer(modele["id"], arguments), arguments)[0]
        except Exception:
            pass  # l'estimation est facultative pour générer

        def apres_envoi(request_id):
            t["request_id"] = request_id

        def maj(statut):
            t["etape"] = {Queued: "En file d'attente…", InProgress: "Génération en cours…"}.get(
                type(statut), t.get("etape"))

        t["etat"] = "en_cours"
        t["etape"] = "Envoi de la demande…"
        resultat = higgsfield_client.subscribe(
            modele["id"], arguments=arguments, on_enqueue=apres_envoi, on_queue_update=maj)
        t["reponse"] = resultat
        statut = resultat.get("status")

        if statut != "completed":
            raise ErreurGeneration({
                "failed": "La génération a échoué" + (f" : {resultat.get('error')}" if resultat.get("error") else "."),
                "nsfw": "Contenu refusé par la modération. Rien n'a été facturé.",
                "canceled": "La génération a été annulée. Rien n'a été facturé.",
            }.get(statut, f"Statut inattendu : {statut!r}. Aucun résultat n'a été produit."))
        url = sortie(resultat, modele["type"])
        if not url:
            raise ErreurGeneration("L'API dit « terminé » mais n'a renvoyé aucune URL. Aucun fichier enregistré.")

        t["etape"] = "Enregistrement du fichier…"
        fichier = telecharger(url, onglet, modele["type"])
        ajouter_historique({
            "fichier": fichier, "type": modele["type"], "modele": modele["nom"],
            "onglet": onglet, "prompt": formulaire.get("prompt", "").strip(),
            "cout_usd": cout, "url": url, "date": datetime.now().isoformat(timespec="seconds"),
        })
        t.update(etat="termine", fichier=fichier, type=modele["type"], url=url, cout_usd=cout)
    except ErreurGeneration as e:
        t.update(etat="echec", erreur=str(e))
    except higgsfield_client.HiggsfieldClientError as e:
        t.update(etat="echec", erreur=f"Erreur de l'API Higgsfield : {e}")
    except Exception as e:  # noqa: BLE001
        t.update(etat="echec", erreur=f"Erreur : {e}")
    finally:
        t["fin"] = time.time()


class ErreurGeneration(Exception):
    pass


# ---------- routes ----------
@app.get("/")
def accueil():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/etat")
def etat():
    return jsonify(cle_presente=cle_presente())


def lire_demande():
    d = request.get_json(silent=True) or {}
    onglet = d.get("onglet")
    if onglet not in MODELES:
        abort(400, "Onglet inconnu.")
    if not cle_presente():
        return None, None, ("Clé manquante : ouvre le fichier .env.local et remplis la ligne "
                            "HF_KEY= (format cle-id:cle-secret), puis relance l'application.")
    return onglet, d, None


@app.post("/api/estimer")
def api_estimer():
    onglet, d, erreur = lire_demande()
    if erreur:
        return jsonify(erreur=erreur), 400
    try:
        image_url = url_publique_image(d.get("image", "")) if onglet == "animer" else None
        args = construire_arguments(onglet, d, image_url)
        rep = estimer(MODELES[onglet]["id"], args)
        usd, approx = calculer_prix(rep, args)
        return jsonify(masquer({"usd": usd, "approx": approx, "credits": rep.get("credits"),
                                "description": rep.get("pricing_description"),
                                "requete": {"application": MODELES[onglet]["id"], "arguments": args},
                                "reponse": rep}))
    except ValueError as e:
        return jsonify(erreur=str(e)), 400
    except Exception as e:  # noqa: BLE001
        return jsonify(erreur=f"Estimation impossible : {e}"), 502


@app.post("/api/generer")
def api_generer():
    onglet, d, erreur = lire_demande()
    if erreur:
        return jsonify(erreur=erreur), 400
    try:  # valide tout de suite ce qui peut l'être sans réseau
        if onglet != "animer":
            construire_arguments(onglet, d)
        elif not d.get("image"):
            raise ValueError("Choisis d'abord une image à animer.")
        elif not d.get("prompt", "").strip():
            raise ValueError("Écris d'abord une description.")
    except ValueError as e:
        return jsonify(erreur=str(e)), 400
    tid = uuid.uuid4().hex
    taches[tid] = {"etat": "file", "etape": "Démarrage…"}
    threading.Thread(target=executer, args=(tid, onglet, d), daemon=True).start()
    return jsonify(id=tid)


@app.get("/api/taches/<tid>")
def api_tache(tid):
    t = taches.get(tid)
    if not t:
        abort(404)
    vue = dict(t)
    vue["ecoule"] = round((t.get("fin") or time.time()) - t["debut"], 1) if t.get("debut") else 0
    return jsonify(masquer(vue))


@app.get("/api/historique")
def api_historique():
    h = [e for e in lire_historique() if (GENERATIONS / e["fichier"]).is_file()]
    total = sum(e["cout_usd"] for e in lire_historique() if e.get("cout_usd"))
    return jsonify(historique=list(reversed(h)), total_usd=round(total, 4))


@app.get("/fichiers/<path:nom>")
def fichier(nom):
    return send_from_directory(GENERATIONS, nom, as_attachment=request.args.get("telecharger") == "1",
                               mimetype=mimetypes.guess_type(nom)[0])


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"\n  Mon Studio B-roll  →  http://127.0.0.1:{port}\n")
    if not cle_presente():
        print("  ⚠ Clé absente : remplis HF_KEY= dans .env.local puis relance.\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
