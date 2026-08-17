# Dashboard Widgets (`ui/widgets/dashboard`)

Ce dossier regroupe les composants graphiques et les vues modulaires constituant le **Tableau de Bord Intégral** de StockLam.

## Fichiers et Rôles

- **`__init__.py`** : Fichier d'initialisation du module Python pour le package dashboard.
- **`dashboard_view.py`** : Vue principale du tableau de bord (`DashboardTab`), intégrant la barre d'outils globale, les filtres de dates maîtres, et l'organisation en onglets.
- **`overview_tab.py`** : Onglet de vue d'ensemble (`OverviewTab`) assemblant les cartes d'indicateurs clés (KPIs) et le graphique des flux financiers.
- **`charts_section.py`** : Section graphique professionnelle (`ChartsSection`) affichant l'analyse comparative des flux de stock sous forme de colonnes (Entrées/Achats en Vert 🟩, Sorties/Consommation en Rouge 🟥) avec filtres historiques locaux (7j, 14j, 30j, Ce Mois, 3m, 6m, YTD, 1an, personnalisé), granularités temporelles (Jour, Semaine, Mois), métriques KPI récapitulatives et infobulles riches (`ChartHoverCard`).
- **`kpi_cards.py`** : Cartes synthétiques des indicateurs de performance (`KPICardsSection`, `KPICard`) affichant la valeur totale du stock, la consommation globale, les unités sorties et les pertes/déchets.
- **`alerts_section.py`** : Section de gestion et d'affichage des alertes de stock critique, seuils d'approvisionnement et péremptions.
- **`consumption_reports.py`** : Rapports détaillés de consommation avec tableaux interactifs, filtrage par période et exportation.
- **`family_reception_tab.py`** : Onglet d'analyse des réceptions et entrées de stock ventilées par famille de produits dans le temps.
- **`statistics_tabs.py`** : Onglets d'analyse statistique avancée, incluant la valorisation détaillée du stock (`StockValuationTab`), le rapport de consommation global (`FullConsumptionTab`), l'audit des stocks fantômes (`DeletedProductsAuditTab`), et l'analyse complète des rebuts et pertes par produit unique avec métriques financières précises (`WasteAnalysisTab`).
