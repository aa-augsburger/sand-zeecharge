# Point d’entrée de compatibilité

Le projet maintenu se trouve désormais à la racine du dépôt.
Ce dossier conserve uniquement un lanceur compatible avec l’ancien chemin.

```powershell
cd ..
uv sync
uv run python main.py
```

L’ancienne copie complète est conservée localement dans `.archive/legacy-project/`
(ignorée par Git). Les changements doivent être faits à la racine.
