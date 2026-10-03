"""Modèles Higgsfield utilisés (identifiants tirés de https://docs.higgsfield.ai/docs/models)."""

MODELES = {
    "image": {
        "id": "higgsfield-ai/soul/standard",
        "nom": "Soul",
        "type": "image",
    },
    "video": {
        "id": "kling-video/v3.0/std/text-to-video",
        "nom": "Kling 3.0 (texte vers vidéo)",
        "type": "video",
    },
    "video_son": {
        "id": "bytedance/seedance-2.5/text-to-video",
        "nom": "Seedance 2.5 (texte vers vidéo, avec son)",
        "type": "video",
    },
    "animer": {
        "id": "kling-video/v3.0/std/image-to-video",
        "nom": "Kling 3.0 (image vers vidéo)",
        "type": "video",
    },
}


def construire_arguments(onglet, f, image_url=None):
    """Transforme le formulaire en arguments conformes au schéma de chaque modèle."""
    prompt = (f.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Écris d'abord une description.")
    format_ = f.get("format") if f.get("format") in ("16:9", "9:16") else "16:9"
    duree = 10 if int(f.get("duree") or 5) == 10 else 5
    resolution = "1080p" if f.get("resolution") == "1080p" else "720p"

    if onglet == "image":
        return {"prompt": prompt, "aspect_ratio": format_, "resolution": "720p", "batch_size": 1}
    if onglet == "video":
        # Kling 3.0 n'a pas de paramètre de résolution ; "sound": "off" = vidéo muette.
        return {"prompt": prompt, "aspect_ratio": format_, "duration": duree, "sound": "off"}
    if onglet == "video_son":
        return {"prompt": prompt, "aspect_ratio": format_, "duration": duree,
                "resolution": resolution, "generate_audio": True}
    if onglet == "animer":
        if not image_url:
            raise ValueError("Choisis d'abord une image à animer.")
        return {"prompt": prompt, "image_url": image_url, "duration": duree, "sound": "off"}
    raise ValueError("Onglet inconnu.")
