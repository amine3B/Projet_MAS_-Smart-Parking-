from mesa import Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
from agents import VehicleAgent, ParkingSpotAgent, ParkingManagerAgent
import random
import statistics

class SmartParkingModel(Model):
    """Modèle de simulation de parking intelligent"""
    
    def __init__(self, width=20, height=20, spawn_rate=0.2, mode="FCFS"):
        super().__init__()
        self.width = width
        self.height = height
        self.spawn_rate = spawn_rate 
        self.mode = mode 
        self.running = True 
        
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, torus=False)
        
        self.total_revenue = 0
        self.total_walking_distance = 0
        self.vehicle_count = 0
        self.parked_count = 0 
        self.grid_agents = {} 
        self.next_vehicle_id = 0

        # --- GÉNÉRATION DU PARKING ---
        exit1 = (width - 1, 0)
        exit2 = (0, height - 1)

        spot_id = 0
        for x in range(width):
            # Définition des routes verticales (Correspond à agents.py)
            is_vertical_road = (x % 3 == 0) or (x == width - 1)

            for y in range(height):
                # Définition des routes horizontales
                is_horizontal_road = (y == 0) or (y == 1) or (y == height - 2) or (y == height - 1)

                # Si c'est une route, on laisse vide
                if is_vertical_road or is_horizontal_road:
                    continue 

                # Calcul du type de place
                dist_exit1 = abs(x - exit1[0]) + abs(y - exit1[1])
                dist_exit2 = abs(x - exit2[0]) + abs(y - exit2[1])
                min_dist_to_exit = min(dist_exit1, dist_exit2)
                
                if min_dist_to_exit < 5: p_type = "VIP"
                elif min_dist_to_exit < 10: p_type = "Handicap" 
                else: p_type = "Standard"

                unique_id = f"spot_{spot_id}"
                spot = ParkingSpotAgent(unique_id, self, p_type, (x, y))
                self.grid.place_agent(spot, (x, y))
                self.schedule.add(spot)
                self.grid_agents[unique_id] = spot
                spot_id += 1

        self.manager = ParkingManagerAgent("manager", self)
        if mode in ["AUCTION", "PRIORITY"]:
            self.schedule.add(self.manager)

        self.datacollector = DataCollector(
            model_reporters={
                "Occupancy": self.get_occupancy_rate,
                "Revenue": lambda m: m.total_revenue,
                "Avg_Walking_Distance": lambda m: (m.total_walking_distance / m.parked_count) if m.parked_count > 0 else 0,
                "Waiting_Variance": self.calculate_waiting_variance
            }
        )

    def calculate_waiting_variance(self):
        wait_times = [a.waiting_time for a in self.schedule.agents if isinstance(a, VehicleAgent)]
        if len(wait_times) > 1: return statistics.variance(wait_times)
        return 0

    def step(self):
        # Spawn de véhicules
        if random.random() < self.spawn_rate:
            valid_entrances = [(0, 0), (self.width - 1, self.height - 1)]
            random.shuffle(valid_entrances)
            
            for spawn_pos in valid_entrances:
                cell_contents = self.grid.get_cell_list_contents([spawn_pos])
                is_clear = not any(isinstance(a, VehicleAgent) for a in cell_contents)
                
                if is_clear:
                    self.next_vehicle_id += 1
                    vid = f"car_{self.schedule.steps}_{self.next_vehicle_id}"
                    v = VehicleAgent(vid, self, random.randint(15, 60), "Standard")
                    self.grid.place_agent(v, spawn_pos) 
                    self.schedule.add(v)
                    self.vehicle_count += 1
                    break 

        self.schedule.step()
        self.datacollector.collect(self)

    def get_occupancy_rate(self):
        spots = [a for a in self.schedule.agents if isinstance(a, ParkingSpotAgent)]
        if not spots: return 0
        occupied = sum([1 for s in spots if s.is_occupied])
        return (occupied / len(spots)) * 100