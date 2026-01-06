# 🚗 Smart Parking Simulation

Simulation de parking intelligent **Digital Twin (Jumeau Numérique)** basée sur une **architecture multi-agents**.

Ce projet compare les performances et revenus entre :

- gestion classique **FCFS – First Come First Served**
- gestion par **enchères dynamiques (Vickrey Auction)**

## ✨ Fonctionnalités

- **Simulation Multi-Agents (Mesa)**  
  Chaque voiture et chaque place de parking est un agent autonome.

- **Enchères de Vickrey**  
  Les voitures enchérissent pour les meilleures places selon leur budget.  
  Le gagnant paie **le prix de la deuxième meilleure offre**.

- **Visualisation en temps réel (React)**  
  Affichage de la grille, des mouvements et des indicateurs.

- **Tableau de bord KPI**  
  - taux d’occupation  
  - revenus générés  
  - distance totale parcourue

- **Architecture Client–Serveur**  
  - Backend : Python + FastAPI  
  - Frontend : React + Vite

## 🛠 Tech Stack

### Backend (simulation)
- Python
- Mesa
- FastAPI
- Uvicorn

### Frontend (interface)
- React
- Vite
- Tailwind CSS
- Recharts
- lucide-react

## 📂 Structure du projet

```bash
smart-parking/
├── parking-backend/               # Logique Python
│   ├── agents.py                  # Définition des agents (Voitures, Places)
│   ├── model.py                   # Logique du modèle (grille, zones)
│   └── backend.py                 # API FastAPI
│
└── parking-frontend/              # Interface React
    ├── src/
    │   └── SmartParkingClient.jsx # composant principal
    ├── package.json
    └── ...

## 🚀 Installation et exécution

### ✔ Prérequis

- Python **3.8+**
- Node.js **16+**

### 1️⃣ Installation du Backend (Python)

cd parking-backend
pip install fastapi uvicorn mesa
uvicorn backend:app --reload

### 2️⃣ Installation du Frontend (React)

cd parking-frontend
npm install
npm install lucide-react recharts
npm run dev

## 🎮 Utilisation

- ouvrir l’interface frontend
- vérifier l’état Backend Python Actif
- choisir mode FCFS ou Enchères
- régler le trafic
- démarrer / pause simulation

Légende :
- 🟨 VIP
- 🟦 Handicap
- 🟩 Standard

## 🤝 Contribution

fork du projet
git checkout -b feature/NouvelleFeature
git commit -m "Add nouvelle feature"
git push origin feature/NouvelleFeature

ouvrir une Pull Request

## 📜 Licence

Projet académique — utilisation libre à des fins pédagogiques.


