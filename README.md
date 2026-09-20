# Battery company simulation

Simulation simple d’une entreprise qui achète des batteries usagées et pratique l’arbitrage sur le marché de l’électricité : acheter quand le prix est bas, revendre quand il est haut.

Aucun matériel, aucune API réelle, aucun trading réel — uniquement un modèle pour explorer la rentabilité.

## Architecture

```
├── main.py                 # Scénario par défaut (30 jours)
├── data/prices.csv         # Prix horaires (généré au premier lancement)
├── models/                 # Batterie, entreprise, transactions
├── simulation/             # Marché (CSV) et moteur horaire
├── strategies/             # Décisions charge / décharge (seuils)
├── reports/                # Résumé texte et graphiques
└── tests/                  # Tests pytest
```

## Installation avec uv

Prérequis : installer [uv](https://docs.astral.sh/uv/getting-started/installation/) (il gère Python 3.13 via le fichier `.python-version`).

```bash
cd sand-zeecharge   # racine du repo (pyproject.toml)
uv sync             # crée .venv/, installe pandas, matplotlib, pytest
```

Toutes les commandes ci-dessous utilisent l’environnement virtuel géré par uv — pas besoin d’activer `.venv` manuellement.

## Lancer la simulation

```bash
uv run python main.py
```

Le rapport s’affiche dans le terminal. Les graphiques sont enregistrés dans `reports/output/` (`price.png`, `soc.png`, `cumulative_profit.png`).

## Tests

```bash
uv run pytest
```

## Hypothèses simplificatrices (MVP)

- **Prix** : profil journalier fictif + bruit (seed 42), pas de données réelles.
- **Pas de contraintes réseau** : puissance max respectée, pas de files d’attente.
- **Rendement** : énergie achetée `grid_kwh` → stockée `grid_kwh × charge_efficiency` ; décharge `battery_kwh` → vendue `battery_kwh × discharge_efficiency`.
- **Dégradation** : perte de SoH proportionnelle à l’énergie cyclée (`apply_degradation` dans `models/battery.py`), remplaçable plus tard.
- **ROI** : `bénéfice net / capital initial` ; la valeur résiduelle des batteries n’est pas comptée au bilan.
- **Une stratégie** : seuils configurables (`ThresholdStrategy`). Pas de maintenance ni OPEX dans le scénario par défaut.

## Scénario par défaut

| Paramètre | Valeur |
|-----------|--------|
| Capital initial | 100 000 CHF |
| Batterie | 100 kWh nominal, SoH 85 %, 5 000 CHF |
| Puissance | 40 kW charge / décharge |
| Rendement | 95 % / 95 % |
| Stratégie | acheter &lt; 0.08 CHF/kWh, vendre &gt; 0.20 CHF/kWh |
| Durée | 30 jours |

## Étendre le projet

- Nouvelle stratégie : implémenter `decide()` comme `ThresholdStrategy` dans `strategies/`.
- Nouveau modèle de dégradation : modifier `apply_degradation` sans toucher au moteur.
- Prix réels : remplacer ou alimenter `data/prices.csv` avec `timestamp,price_chf_kwh`.
