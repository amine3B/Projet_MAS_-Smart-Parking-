from mesa import Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
from agents import VehicleAgent, ParkingSpotAgent, ParkingManagerAgent
import random

class SmartParkingModel(Model):
    def __init__(self, width=10, height=10, spawn_rate=0.2, mode="FCFS"):
        self.width = width
        self.height = height
        self.spawn_rate = spawn_rate 
        self.mode = mode 
        
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, torus=False)
        
        # KPIs globaux
        self.total_revenue = 0
        self.total_walking_distance = 0
        self.vehicle_count = 0
        self.grid_agents = {} 

        # 1. Création des Places de Parking (Ressources)
        # On remplit les rangées du milieu pour laisser des "routes" sur les bords
        spot_id = 0
        for x in range(1, width-1):
            for y in range(1, height-1):
                # --- NOUVELLE LOGIQUE DE ZONES ---
                # Groupement basé sur la distance à l'entrée (x=0)
                
                # Zone 1 : VIP (Les 3 premières colonnes) -> Très proche de l'entrée
                if x <= 3: 
                    p_type = "VIP"
                # Zone 2 : Handicap (Les 2 colonnes suivantes) -> Proche
                elif x <= 5:
                    p_type = "Handicap"
                # Zone 3 : Standard (Le reste du parking)
                else:
                    p_type = "Standard"

                spot = ParkingSpotAgent(f"spot_{spot_id}", self, p_type, (x,y))
                self.grid.place_agent(spot, (x,y))
                self.schedule.add(spot)
                self.grid_agents[f"spot_{spot_id}"] = spot
                spot_id += 1

        # 2. Création du Manager (pour le mode Enchères)
        self.manager = ParkingManagerAgent("manager", self)
        if mode == "AUCTION":
            self.schedule.add(self.manager)

        # 3. Data Collector
        self.datacollector = DataCollector(
            model_reporters={
                "Occupancy": self.get_occupancy_rate,
                "Revenue": lambda m: m.total_revenue,
                "Avg_Walking_Distance": lambda m: m.total_walking_distance / m.vehicle_count if m.vehicle_count > 0 else 0
            }
        )

    def step(self):
        # Génération dynamique de véhicules
        if random.random() < self.spawn_rate:
            vid = f"car_{self.schedule.steps}_{random.randint(0,1000)}"
            # Budget aléatoire entre 10 et 50
            v = VehicleAgent(vid, self, budget=random.randint(10, 50), preferred_type="Standard")
            # Entrée sur une case aléatoire au bord (0,0)
            start_pos = (0, 0) 
            self.grid.place_agent(v, start_pos)
            self.schedule.add(v)
            self.vehicle_count += 1

        self.datacollector.collect(self)
        self.schedule.step()

    def get_occupancy_rate(self):
        spots = [a for a in self.schedule.agents if isinstance(a, ParkingSpotAgent)]
        occupied = sum([1 for s in spots if s.is_occupied])
        return (occupied / len(spots)) * 100 if spots else 0