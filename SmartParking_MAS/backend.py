# Lancez ce fichier avec : python backend.py
# Ou : uvicorn backend:app --reload

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn 
from model import SmartParkingModel
from agents import VehicleAgent, ParkingSpotAgent

app = FastAPI()

origins = ["http://localhost:5173", "http://127.0.0.1:5173", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_model = None

@app.post("/init")
def init_model(spawn_rate: float = 0.3, mode: str = "FCFS"):
    global current_model
    current_model = SmartParkingModel(width=20, height=20, spawn_rate=spawn_rate, mode=mode)
    return {
        "message": f"Simulation initialized in {mode} mode",
        "config": {"width": 20, "height": 20}
    }

@app.get("/step")
def step_model():
    global current_model
    if current_model is None:
        return {"error": "Model not initialized"}
    
    current_model.step()
    
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
            if agent.pos: 
                cars_data.append({
                    "id": str(agent.unique_id),
                    "x": agent.pos[0],
                    "y": agent.pos[1],
                    "state": agent.state,
                    "budget": agent.budget,
                    "priority": getattr(agent, 'priority_score', 1) 
                })

    df = current_model.datacollector.get_model_vars_dataframe()
    last_metrics = df.iloc[-1].to_dict() if not df.empty else {}

    return {
        "spots": spots_data,
        "cars": cars_data,
        "metrics": {
            "occupancy": last_metrics.get("Occupancy", 0),
            "revenue": last_metrics.get("Revenue", 0),
            "avg_walking": last_metrics.get("Avg_Walking_Distance", 0),
            "fairness_variance": last_metrics.get("Waiting_Variance", 0),
            "step": current_model.schedule.steps
        }
    }

if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)