# Lancez ce fichier : uvicorn backend:app --reload

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from model import SmartParkingModel
from agents import VehicleAgent, ParkingSpotAgent

app = FastAPI()

# Configuration CORS : Permet au Frontend (React) de discuter avec le Backend
origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",  # Vite utilise parfois localhost
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage global du modèle
current_model = None

@app.post("/init")
def init_model(spawn_rate: float = 0.2, mode: str = "FCFS"):
    """
    Initialise la simulation et renvoie la configuration de la grille.
    """
    global current_model
    # On force 20x20 pour avoir une belle grille, modifiable ici
    width, height = 20, 20
    current_model = SmartParkingModel(width=width, height=height, spawn_rate=spawn_rate, mode=mode)
    
    return {
        "message": "Simulation initialized",
        "config": {
            "width": width,
            "height": height,
            "spawn_rate": spawn_rate,
            "mode": mode
        }
    }

@app.get("/step")
def step_model():
    """
    Avance d'un pas (step) et renvoie l'état complet (Agents + KPIs).
    """
    global current_model
    
    if current_model is None:
        return {"error": "Model not initialized. Call /init first."}
    
    # 1. Avancer la simulation Python
    current_model.step()
    
    # 2. Sérialisation des données (Python -> JSON)
    spots_data = []
    cars_data = []
    
    for agent in current_model.schedule.agents:
        if isinstance(agent, ParkingSpotAgent):
            spots_data.append({
                "id": str(agent.unique_id),
                "x": agent.pos[0],
                "y": agent.pos[1],
                "type": agent.spot_type,
                "occupied": agent.is_occupied
            })
        elif isinstance(agent, VehicleAgent):
            if agent.pos: # Sécurité si l'agent n'est pas sur la grille
                cars_data.append({
                    "id": str(agent.unique_id),
                    "x": agent.pos[0],
                    "y": agent.pos[1],
                    "state": agent.state,
                    "budget": getattr(agent, 'budget', 0) # Gestion cas où budget n'existe pas
                })

    # 3. Récupération des KPIs
    metrics = {
        "occupancy": current_model.get_occupancy_rate(),
        "revenue": current_model.total_revenue,
        "step": current_model.schedule.steps
    }

    return {
        "spots": spots_data,
        "cars": cars_data,
        "metrics": metrics
    }