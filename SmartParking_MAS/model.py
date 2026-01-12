from mesa import Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
from agents import VehicleAgent, ParkingSpotAgent, ParkingManagerAgent
import random
import statistics

class SmartParkingModel(Model):
    def __init__(self, width=20, height=20, spawn_rate=0.2, mode="FCFS"):
        self.width = width
        self.height = height
        self.spawn_rate = spawn_rate 
        self.mode = mode 
        
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, torus=False)
        
        self.total_revenue = 0
        self.total_walking_distance = 0
        self.vehicle_count = 0
        self.parked_count = 0 
        self.grid_agents = {} 

        # --- GÉNÉRATION D'UN PARKING CROISÉ ---
        # Sorties situées en : Haut-Droite (width-1, 0) et Bas-Gauche (0, height-1)
        exit1 = (width - 1, 0)
        exit2 = (0, height - 1)

        spot_id = 0
        for x in range(width):
            # Routes verticales : modulo 3 OU bord droit absolu
            is_vertical_road = (x % 3 == 0) or (x == width - 1)

            for y in range(height):
                # Routes horizontales : Haut et Bas
                is_horizontal_road = (y == 0) or (y == height - 1)

                if is_vertical_road or is_horizontal_road:
                    continue 

                # --- NOUVELLE LOGIQUE DE ZONES ---
                # Calcul de la distance vers la sortie la plus proche
                dist_exit1 = abs(x - exit1[0]) + abs(y - exit1[1])
                dist_exit2 = abs(x - exit2[0]) + abs(y - exit2[1])
                min_dist_to_exit = min(dist_exit1, dist_exit2)
                
                # Plus on est proche d'une sortie, plus le statut est élevé
                if min_dist_to_exit < 5: p_type = "VIP"      # Très proche
                elif min_dist_to_exit < 10: p_type = "Handicap" # Proche
                else: p_type = "Standard"                     # Loin

                spot = ParkingSpotAgent(f"spot_{spot_id}", self, p_type, (x,y))
                self.grid.place_agent(spot, (x,y))
                self.schedule.add(spot)
                self.grid_agents[f"spot_{spot_id}"] = spot
                spot_id += 1

        self.manager = ParkingManagerAgent("manager", self)
        if mode in ["AUCTION", "PRIORITY"]:
            self.schedule.add(self.manager)

        self.datacollector = DataCollector(
            model_reporters={
                "Occupancy": self.get_occupancy_rate,
                "Revenue": lambda m: m.total_revenue,
                "Avg_Walking_Distance": lambda m: m.total_walking_distance / m.parked_count if m.parked_count > 0 else 0,
                "Waiting_Variance": self.calculate_waiting_variance
            }
        )

    def calculate_waiting_variance(self):
        wait_times = [
            a.waiting_time for a in self.schedule.agents 
            if isinstance(a, VehicleAgent) and a.state != "SEARCHING"
        ]
        if len(wait_times) > 1: return statistics.variance(wait_times)
        return 0

    def step(self):
        # Spawn sur 2 ENTRÉES CROISÉES : (0,0) et (Width-1, Height-1)
        if random.random() < self.spawn_rate:
            entrances = [(0, 0), (self.width - 1, self.height - 1)]
            spawn_pos = random.choice(entrances)
            
            # Vérifier si l'entrée choisie est libre
            cell_contents = self.grid.get_cell_list_contents([spawn_pos])
            if not any(isinstance(a, VehicleAgent) for a in cell_contents):
                vid = f"car_{self.schedule.steps}_{random.randint(0,1000)}"
                v = VehicleAgent(vid, self, budget=random.randint(15, 60), preferred_type="Standard")
                self.grid.place_agent(v, spawn_pos) 
                self.schedule.add(v)
                self.vehicle_count += 1

        self.datacollector.collect(self)
        self.schedule.step()

    def get_occupancy_rate(self):
        spots = [a for a in self.schedule.agents if isinstance(a, ParkingSpotAgent)]
        if not spots: return 0
        occupied = sum([1 for s in spots if s.is_occupied])
        return (occupied / len(spots)) * 100