"""Minimal in-app internationalization (French / English). `t(key)` returns the string
for the current language; `set_language` switches it. The app rebuilds its widgets on
language change so every label is refreshed."""
from __future__ import annotations

_LANG = "fr"
LANGUAGES = {"fr": "Francais", "en": "English"}

STRINGS = {
    "fr": {
        "app_title": "norma studio  —  normalisation relationnelle non supervisée",
        "menu_file": "&Fichier", "menu_view": "&Affichage", "menu_analysis": "&Analyse",
        "menu_lang": "&Langue", "open_csv": "Ouvrir CSV...", "connect_db": "Connecter une base...",
        "analyze": "Analyser", "export_sql": "Exporter SQL...", "quit": "Quitter",
        "preferences": "Préférences...",
        "open_data": "Ouvrir des données...",
        "export_constraints": "Exporter les contraintes...",
        "freeze_contract": "Geler le contrat (norma.yml)...",
        "check_contract": "Vérifier un contrat...",
        "export_format": "Format d'export :", "choose_out_dir": "Choisir le dossier de sortie",
        "open_contract": "Ouvrir un contrat norma.yml", "check_title": "Vérification du contrat",
        "exported_n": "{n} fichier(s) exporté(s) vers {d}",
        "contract_saved": "Contrat enregistré : {path}",
        "check_summary": "{ok}/{total} contraintes satisfaites",
        "tab_data": "Données", "tab_fdgraph": "Graphe des DF", "tab_schema": "Schéma",
        "tab_sql": "SQL", "tab_anomalies": "Anomalies", "tab_deploy": "Base propre",
        "dock_constraints": "Contraintes",
        "ready": "Prêt. Ouvrez un CSV ou connectez une base, puis lancez l'analyse.",
        "no_table": "Aucune table chargée", "preview": "Aperçu",
        "rules_title": "Contraintes découvertes", "col_type": "Type", "col_rule": "Règle",
        "col_conf": "Conf.", "add_expert": "+ Contrainte experte", "remove": "Supprimer",
        "active": "actives", "normal_form": "forme normale",
        "schema_title": "Schéma relationnel", "form": "Forme", "relayout": "Re-disposer",
        "current_nf": "Forme normale courante", "candidate_keys": "clés candidates",
        "sql_title": "SQL (DDL)", "generate_from_schema": "Générer depuis le schéma",
        "apply_sql": "Appliquer SQL au schéma",
        "anomaly_title": "Zones d'anomalie", "threshold": "Seuil",
        "anomaly_legend": "Plus la cellule est rouge, plus son score de violation est élevé.",
        "deploy_title": "Construire une base de données propre",
        "deploy_desc": "Crée une base SQLite avec le schéma obtenu, peuplée des données "
                       "sans anomalies, avec triggers et vues sur les contraintes CPAD.",
        "target_file": "Fichier SQLite cible", "browse": "Parcourir...",
        "clean_threshold": "Seuil d'anomalie (lignes au-dessus exclues)",
        "incl_triggers": "Inclure les triggers (contraintes applicables)",
        "incl_views": "Inclure les vues sur les contraintes (non-clés)",
        "gen_script": "Générer le script SQL", "create_db": "Créer la base SQLite",
        "pref_theme": "Thème", "pref_light": "Clair", "pref_dark": "Sombre",
        "pref_accent": "Couleur d'accent", "pref_language": "Langue", "pick_color": "Choisir...",
        "tab_repair": "Réparation", "tab_report": "Rapport qualité",
        "repair_title": "Réparation guidée par les contraintes",
        "repair_desc": "Pour chaque cellule en violation, proposer la valeur cohérente "
                       "(mode du groupe pour les FD, projection monotone/linéaire), dans la "
                       "zone sûre (confiance, support, rareté). Aperçu avant d'appliquer.",
        "confidence": "Confiance min", "min_group": "Groupe min", "order": "ordre", "linear": "linéaire",
        "col_row": "Ligne", "col_column": "Colonne", "col_before": "Avant", "col_after": "Après", "col_rule": "Règle",
        "undo": "Annuler", "apply_clean": "Nettoyer", "edits_count": "corrections proposées",
        "report_title": "Rapport de qualité des données", "refresh": "Rafraîchir",
        "export_html": "Exporter HTML", "export_pdf": "Exporter PDF", "export_svg": "Exporter SVG",
        "fd_hint": "Déplacez les nœuds pour arranger le graphe, puis exportez en PDF/SVG vectoriel.",
        "fd_legend_simple": "— DF simple", "fd_legend_composite": "∧ DF composite (clé conjointe)",
        "db_connect_btn": "Se connecter et lister les tables", "db_tables": "Tables :",
        "db_driver": "Pilote :", "db_database": "Base / fichier :", "db_host": "Hôte :",
        "db_port": "Port :", "db_user": "Utilisateur :", "db_password": "Mot de passe :",
        "expert_title": "Ajouter une contrainte experte (FD)",
        "expert_sources": "Sources (membre gauche, multi-sélection) :",
        "expert_target": "Cible (membre droit) :",
        "saved": "Enregistré", "save_failed": "Échec de l'enregistrement",
        "tip_open": "Ouvrir un fichier CSV", "tip_db": "Se connecter à une base",
        "tip_run": "Découvrir les contraintes", "tip_sql": "Exporter le schéma en SQL",
        "status_loaded": "Table '{name}' chargée : {n} lignes, {c} colonnes.",
        "status_truncated": "Fichier volumineux : analyse limitée à un échantillon de {n} lignes "
                            "(variable NORMA_MAX_ROWS pour changer).",
        "status_analyzing": "Analyse en cours (découverte des contraintes)...",
        "status_analyzed": "Analyse terminée : {k} contraintes découvertes.",
        "status_expert_added": "Contrainte experte ajoutée : {fd}.",
        "sql_none": "Aucun CREATE TABLE reconnu.",
        "sql_parsed": "{n} tables analysées depuis le SQL et affichées dans l'onglet Schéma.",
        "sql_placeholder": "-- Chargez une table et lancez l'analyse pour générer le DDL.",
        "sql_generated": "DDL généré depuis le schéma découvert.",
        "status_repair_preview": "{n} corrections proposées.",
        "status_repair_applied": "{n} cellules corrigées.",
        "status_repair_undone": "Réparation annulée.",
        "ok": "OK", "cancel": "Annuler",
    },
    "en": {
        "app_title": "norma studio  —  unsupervised relational normalization",
        "menu_file": "&File", "menu_view": "&View", "menu_analysis": "&Analysis",
        "menu_lang": "&Language", "open_csv": "Open CSV...", "connect_db": "Connect database...",
        "analyze": "Analyze", "export_sql": "Export SQL...", "quit": "Quit",
        "preferences": "Preferences...",
        "open_data": "Open data...",
        "export_constraints": "Export constraints...",
        "freeze_contract": "Freeze contract (norma.yml)...",
        "check_contract": "Check a contract...",
        "export_format": "Export format:", "choose_out_dir": "Choose output directory",
        "open_contract": "Open a norma.yml contract", "check_title": "Contract check",
        "exported_n": "{n} file(s) exported to {d}",
        "contract_saved": "Contract saved: {path}",
        "check_summary": "{ok}/{total} constraints satisfied",
        "tab_data": "Data", "tab_fdgraph": "FD graph", "tab_schema": "Schema",
        "tab_sql": "SQL", "tab_anomalies": "Anomalies", "tab_deploy": "Clean database",
        "dock_constraints": "Constraints",
        "ready": "Ready. Open a CSV or connect a database, then run the analysis.",
        "no_table": "No table loaded", "preview": "preview",
        "rules_title": "Discovered constraints", "col_type": "Type", "col_rule": "Rule",
        "col_conf": "Conf.", "add_expert": "+ Expert constraint", "remove": "Remove",
        "active": "active", "normal_form": "normal form",
        "schema_title": "Relational schema", "form": "Form", "relayout": "Re-layout",
        "current_nf": "Current normal form", "candidate_keys": "candidate keys",
        "sql_title": "SQL (DDL)", "generate_from_schema": "Generate from schema",
        "apply_sql": "Apply SQL to schema",
        "anomaly_title": "Anomaly zones", "threshold": "Threshold",
        "anomaly_legend": "The redder the cell, the higher its violation score.",
        "deploy_title": "Build a clean database",
        "deploy_desc": "Creates a SQLite database with the discovered schema, populated with "
                       "anomaly-free data, plus triggers and views over the CPAD constraints.",
        "target_file": "Target SQLite file", "browse": "Browse...",
        "clean_threshold": "Anomaly threshold (rows above are excluded)",
        "incl_triggers": "Include triggers (enforceable constraints)",
        "incl_views": "Include constraint views (non-key)",
        "gen_script": "Generate SQL script", "create_db": "Create SQLite database",
        "pref_theme": "Theme", "pref_light": "Light", "pref_dark": "Dark",
        "pref_accent": "Accent color", "pref_language": "Language", "pick_color": "Pick...",
        "tab_repair": "Repair", "tab_report": "Quality report",
        "repair_title": "Constraint-guided repair",
        "repair_desc": "For each violating cell, propose the consistent value (group mode "
                       "for FDs, monotone/linear projection), inside the safe zone "
                       "(confidence, support, rarity). Preview before applying.",
        "confidence": "Min confidence", "min_group": "Min group", "order": "order", "linear": "linear",
        "col_row": "Row", "col_column": "Column", "col_before": "Before", "col_after": "After", "col_rule": "Rule",
        "preview": "Preview", "undo": "Undo", "apply_clean": "Clean", "edits_count": "proposed fixes",
        "report_title": "Data quality report", "refresh": "Refresh",
        "export_html": "Export HTML", "export_pdf": "Export PDF", "export_svg": "Export SVG",
        "fd_hint": "Drag the nodes to arrange the graph, then export to vector PDF/SVG.",
        "fd_legend_simple": "— single-source FD", "fd_legend_composite": "∧ composite FD (joint key)",
        "db_connect_btn": "Connect and list tables", "db_tables": "Tables:",
        "db_driver": "Driver:", "db_database": "Database / file:", "db_host": "Host:",
        "db_port": "Port:", "db_user": "User:", "db_password": "Password:",
        "expert_title": "Add an expert constraint (FD)",
        "expert_sources": "Sources (left-hand side, multi-select):",
        "expert_target": "Target (right-hand side):",
        "saved": "Saved", "save_failed": "Save failed",
        "tip_open": "Open a CSV file", "tip_db": "Connect to a database",
        "tip_run": "Discover the constraints", "tip_sql": "Export the schema as SQL",
        "status_loaded": "Table '{name}' loaded: {n} rows, {c} columns.",
        "status_truncated": "Large file: analysis limited to a {n}-row sample "
                            "(set NORMA_MAX_ROWS to change).",
        "status_analyzing": "Analysis running (constraint discovery)...",
        "status_analyzed": "Analysis complete: {k} constraints discovered.",
        "status_expert_added": "Expert constraint added: {fd}.",
        "sql_none": "No CREATE TABLE recognized.",
        "sql_parsed": "{n} tables parsed from SQL and shown in the Schema tab.",
        "sql_placeholder": "-- Load a table and run the analysis to generate the DDL.",
        "sql_generated": "DDL generated from the discovered schema.",
        "status_repair_preview": "{n} fixes proposed.",
        "status_repair_applied": "{n} cells repaired.",
        "status_repair_undone": "Repair undone.",
        "ok": "OK", "cancel": "Cancel",
    },
}


def set_language(lang: str):
    global _LANG
    if lang in STRINGS:
        _LANG = lang


def language() -> str:
    return _LANG


def t(key: str) -> str:
    # current language, then English as the universal fallback, then the raw key
    return STRINGS.get(_LANG, {}).get(key) or STRINGS["en"].get(key) or key
