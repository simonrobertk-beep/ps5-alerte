#!/usr/bin/env python3
"""
Alerte PS5 Digital en stock chez Best Buy Canada.
Aucune dépendance : Python 3.8+ seulement.

Utilisation :
    python3 ps5_alerte.py              # boucle infinie (vérifie aux ~90 s)
    python3 ps5_alerte.py --test       # envoie une notification de test
    python3 ps5_alerte.py --une-fois   # une seule vérification, puis quitte

Notifications : push sur le téléphone via ntfy.sh (gratuit, sans compte).
  1. Installe l'app « ntfy » (iOS / Android).
  2. Abonne-toi à un nom de sujet secret et unique (voir NTFY_SUJET plus bas).
"""
import argparse
import os
import json
import random
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ---------------- À PERSONNALISER ----------------
NTFY_SUJET = os.environ.get("NTFY_SUJET", "CHANGE-MOI")   # sur GitHub : lu depuis un secret

PRODUITS = {
    # SKU Best Buy : nom affiché
    "19446112": "PS5 Slim Digital 825 Go",
    # Décommente / ajoute d'autres SKU au besoin (bundles, etc.) :
    # "19471342": "PS5 Digital - bundle Fortnite Flowering Chaos",
    # "19185139": "PS5 Digital - bundle Astro Bot",
}

INTERVALLE_SECONDES = 90      # délai moyen entre deux vérifications
RENOTIFIER_APRES_MIN = 30     # re-notifier si toujours en stock après X minutes
# --------------------------------------------------

API = ("https://www.bestbuy.ca/ecomm-api/availability/products"
       "?accept=application%2Fvnd.bestbuy.standardproduct.v1%2Bjson"
       "&skus={skus}")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def notifier(titre, message, lien=None, prioritaire=True):
    entetes = {"Title": titre.encode("utf-8"),
               "Priority": "urgent" if prioritaire else "default",
               "Tags": "video_game,rotating_light"}
    if lien:
        entetes["Click"] = lien
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_SUJET}",
        data=message.encode("utf-8"), headers=entetes, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
        log(f"Notification envoyée : {titre}")
    except Exception as e:
        log(f"Échec de l'envoi de la notification : {e}")


def verifier():
    """Retourne {sku: bool_en_stock}."""
    url = API.format(skus="|".join(PRODUITS))
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
        "Referer": "https://www.bestbuy.ca/"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8-sig"))
    return interpreter(data)


def interpreter(data):
    resultats = {}
    for a in data.get("availabilities", []):
        sku = str(a.get("sku"))
        livraison = (a.get("shipping") or {})
        retrait = (a.get("pickup") or {})
        en_stock = (
            livraison.get("purchasable") is True
            or retrait.get("purchasable") is True
            or str(a.get("buttonState", "")).lower() == "addtocart"
        )
        resultats[sku] = en_stock
    return resultats


def lien(sku):
    return f"https://www.bestbuy.ca/fr-ca/produit/{sku}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true")
    p.add_argument("--une-fois", action="store_true")
    args = p.parse_args()

    if args.test:
        notifier("Test PS5", "Si tu vois ceci, les alertes fonctionnent.",
                 lien("19446112"))
        return

    log(f"Surveillance de {len(PRODUITS)} produit(s). Ctrl+C pour arrêter.")
    derniere_alerte = {}     # sku -> timestamp
    erreurs = 0

    while True:
        try:
            etat = verifier()
            erreurs = 0
            for sku, nom in PRODUITS.items():
                if etat.get(sku):
                    log(f"EN STOCK : {nom}")
                    maintenant = time.time()
                    if maintenant - derniere_alerte.get(sku, 0) > RENOTIFIER_APRES_MIN * 60:
                        notifier(f"{nom} EN STOCK !",
                                 f"{nom} est disponible chez Best Buy Canada.",
                                 lien(sku))
                        derniere_alerte[sku] = maintenant
                else:
                    log(f"Rupture : {nom}")
                    derniere_alerte.pop(sku, None)
        except urllib.error.HTTPError as e:
            erreurs += 1
            log(f"Erreur HTTP {e.code} (Best Buy bloque peut-être les requêtes)")
        except Exception as e:
            erreurs += 1
            log(f"Erreur : {e}")

        if erreurs == 10:
            notifier("Alerte PS5 : problème",
                     "10 erreurs de suite en interrogeant Best Buy. Vérifie le script.",
                     prioritaire=False)
        if args.une_fois:
            return
        # délai aléatoire + recul si erreurs, pour ne pas surcharger le site
        pause = INTERVALLE_SECONDES * random.uniform(0.7, 1.3) * (1 + min(erreurs, 5))
        time.sleep(pause)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
