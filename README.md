# Sand Zeecharge

Simulateur local d’arbitrage électrique avec batteries usagées, en Python 3.13.
Cockpit **Rich** en français, suivi de plusieurs batteries, rapports HTML/JSON/CSV et graphiques PNG.
Les prix par défaut sont synthétiques : aucune API ni opération de trading réelle.

## Installation et lancement

Depuis la racine du dépôt, celle qui contient `pyproject.toml` :

```powershell
uv sync --locked
uv run python main.py
```

Le cockpit montre le prix courant, les achats et ventes réellement exécutés, la trésorerie,
la marge d’arbitrage, le stock et la santé des batteries, ainsi que les cinq dernières transactions.
Il adapte sa disposition à la largeur du terminal et utilise une vue compacte pendant
l’animation sur les terminaux de faible hauteur. Le bilan final reste intégral.
Les sorties redirigées désactivent automatiquement l’animation.

```powershell
# Trois batteries sur 30 jours
uv run python main.py --batteries 3 --days 30

# Calcul rapide, sans animation
uv run python main.py --days 365 --no-live

# Démonstration plus lente
uv run python main.py --days 2 --delay 0.15

# Import de prix ; cadence déduite du CSV, y compris les pas de 15 minutes
uv run python main.py --prices data/prices.csv

# Affichage détaillé et paramètres personnalisés
uv run python main.py --verbose --days 1 --buy 0.07 --sell 0.23
uv run python main.py --cash 20000 --capacity 80 --power 30 --soh 0.8

uv run python main.py --help
uv run pytest
```

## Rapports

Chaque lancement remplace les fichiers du dossier `reports/output/` :

- `report.html` : cockpit et bilan Rich, consultables dans un navigateur ;
- `summary.json` : indicateurs, états finaux et contrôle du bilan énergétique ;
- `transactions.csv` : achats de batteries et opérations énergétiques ;
- `steps.csv` : prix, durée, stock, trésorerie et marge à chaque pas ;
- `price.png`, `soc.png`, `cumulative_profit.png` : graphiques.

Utiliser `--output chemin/du/scenario` pour conserver plusieurs scénarios,
ou `--no-plots` pour omettre les PNG. Les chemins par défaut sont relatifs au
fichier principal ; le programme peut être lancé depuis un autre répertoire.
Un chemin fourni explicitement est relatif au répertoire d’appel.

## Données et conventions

Le CSV doit contenir `timestamp,price_chf_kwh`, avec des dates valides, uniques,
croissantes et régulièrement espacées. Les valeurs manquantes, les prix non numériques
ou infinis et les trous temporels sont refusés. Les prix négatifs sont acceptés.
Préférer des dates UTC pour les séries traversant un changement d’heure.
Chaque ligne représente le début d’un intervalle ; la dernière conserve la cadence
observée. Un marché d’une seule ligne représente une heure par défaut ; l’API
`EnergyMarket(prices, duration_h=...)` permet de préciser une autre durée.
`--days` ne concerne que la génération synthétique ; un CSV est simulé intégralement.

- La puissance de charge est mesurée côté réseau, celle de décharge côté batterie.
- Une charge de 40 kWh à 95 % stocke 38 kWh avant dégradation.
- Une décharge interne de 38 kWh à 95 % vend 36,1 kWh au réseau.
- Les cycles équivalents sont `(énergie chargée interne + énergie déchargée interne) / (2 × capacité nominale)`.
- Le facteur de dégradation est la perte de SOH par cycle nominal équivalent complet.
- Les pertes provoquées par une baisse de capacité sont comptabilisées séparément.
- Le bilan vérifie `stock initial + achats = stock final + ventes + pertes`.
- Le rendement observé `ventes / achats` n’est affiché que pour une période commençant
  et finissant avec des batteries vides. Sinon il est indiqué comme non disponible.

Les achats sont limités par la trésorerie **avant** la charge. Une vente à prix négatif
est également limitée au montant payable. Quand le budget est insuffisant pour tout le
parc, les batteries sont servies dans leur ordre dans `Company.batteries`.
Les seuils d’achat/vente sont stricts ; un prix égal au seuil ne déclenche pas l’action correspondante.

## Indicateurs et limites du modèle

- **Marge d’arbitrage** : recettes des ventes moins coûts d’achat d’énergie.
- **Solde après investissement** : marge moins achats de batteries et maintenance.
- **Trésorerie** : argent disponible, avec les dépenses effectivement enregistrées.

Le solde après investissement n’est pas un bénéfice comptable : la valeur résiduelle
des batteries et la valeur de l’énergie stockée ne sont pas comptabilisées. Le modèle
n’inclut pas de frais réseau, taxes, vieillissement calendaire, limite commune de raccordement
ou coûts fixes. `Company.record_maintenance()` permet d’enregistrer une dépense explicite,
mais le scénario par défaut n’en ajoute pas. La dégradation est un modèle linéaire simplifié.

## Architecture

```text
main.py                  paramètres CLI et orchestration
models/                  batterie, validation, entreprise et transactions
simulation/market.py     génération et validation des prix
simulation/engine.py     moteur, bilans et snapshots immuables par pas
strategies/              décisions ; stratégie à seuils par défaut
ui/console.py            affichage Rich à partir des snapshots
reports/report.py        exports et graphiques
tests/                  tests physiques, financiers, CSV, CLI et Rich
```

Une stratégie implémente `decide(price_chf_kwh, batteries, duration_h)` et renvoie une liste
`Action(battery_id, action_type)`. Une batterie absente de la liste reste inactive ;
les identifiants inconnus et les actions multiples pour une même batterie sont refusés.
Le moteur reste responsable des contraintes physiques et financières.

La version maintenue est à la racine. L’ancien `sand-zeecharge/main.py` est un lanceur
compatible vers cette version. La copie antérieure est sauvegardée localement dans
`.archive/legacy-project/`, ignoré par Git.
