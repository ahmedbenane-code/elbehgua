# Suivi laitier El Behgua

Application de suivi de la production laitière de la ferme d’El Behgua (MPE · La Mauritanienne des Produits de l’Élevage).

- `index.html` : l’application (tableau de bord, bulletins, fiches vaches, registre).
- `data.json` : les données, mises à jour automatiquement depuis KoboToolbox toutes les heures (`.github/workflows/synchro-kobo.yml`, clé API dans le secret `KOBO_TOKEN`).
- `kobo_sync.py` : script de synchronisation.

© 2026 MPE · La Mauritanienne des Produits de l’Élevage · Tous droits réservés.
