from mesa import Agent
import numpy as np

class ParkingSpotAgent(Agent):
    """Agent représentant une place de parking (Ressource)."""
    def __init__(self, unique_id, model, spot_type="Standard", pos=(0,0)):
        super().__init__(unique_id, model)
        self.spot_type = spot_type
        self.is_occupied = False
        self.pos = pos
        # Distance de Manhattan vers la sortie (supposée être à (0,0))
        self.distance_to_exit = abs(pos[0]) + abs(pos[1]) 
        self.base_price = 5 if spot_type == "Standard" else 10 # [cite: 39]

class ParkingManagerAgent(Agent):
    """Agent Coordinateur pour le mode Enchères (Vickrey)."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.bids = {} # {spot_id: [(vehicle, bid_amount), ...]}

    def step(self):
        # Résolution des enchères à chaque pas de temps [cite: 67]
        for spot_id, bid_list in self.bids.items():
            spot = self.model.grid_agents[spot_id]
            if spot.is_occupied:
                continue
            
            # Tri des offres (Vickrey: Second-Price Sealed-Bid)
            if bid_list:
                # Trier par montant décroissant
                bid_list.sort(key=lambda x: x[1], reverse=True)
                winner, highest_bid = bid_list[0]
                
                # Prix = 2ème offre la plus haute, ou prix de base si une seule offre [cite: 71]
                price_to_pay = bid_list[1][1] if len(bid_list) > 1 else spot.base_price
                
                # Allocation
                winner.allocate_spot(spot, price_to_pay)
                
        self.bids = {} # Reset pour le prochain tour

    def receive_bid(self, vehicle, spot, amount):
        if spot.unique_id not in self.bids:
            self.bids[spot.unique_id] = []
        self.bids[spot.unique_id].append((vehicle, amount))

class VehicleAgent(Agent):
    """Agent Véhicule (Cognitif)."""
    def __init__(self, unique_id, model, budget, preferred_type):
        super().__init__(unique_id, model)
        self.budget = budget # [cite: 44]
        self.preferred_type = preferred_type
        self.state = "SEARCHING" # SEARCHING, MOVING, PARKED [cite: 48]
        self.target_spot = None
        self.parked_spot = None
        self.arrival_time = 0 # Pour calculer le temps d'attente

    def step(self):
        self.arrival_time += 1
        if self.state == "PARKED":
            return
        
        if self.state == "MOVING":
            self.move_towards_target()
        
        if self.state == "SEARCHING":
            if self.model.mode == "FCFS":
                self.behavior_fcfs()
            elif self.model.mode == "AUCTION":
                self.behavior_auction()

    def behavior_fcfs(self):
        """Mode 1: Prend la place libre la plus proche."""
        avail_spots = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied]
        
        # Filtrer par type (simple implémentation: accepte tout si Standard, sinon cherche spécifique)
        valid_spots = [s for s in avail_spots if s.spot_type == self.preferred_type or self.preferred_type == "Standard"]
        
        if valid_spots:
            # Trier par distance
            valid_spots.sort(key=lambda s: abs(self.pos[0]-s.pos[0]) + abs(self.pos[1]-s.pos[1]))
            best_spot = valid_spots[0]
            self.allocate_spot(best_spot, price=0) # Gratuit en FCFS

    def behavior_auction(self):
        """Mode 2: Enchères de Vickrey[cite: 62]."""
        avail_spots = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied]
        
        for spot in avail_spots:
            # Calcul Utilité: SU = Valeur - Coût(Est.) - Distance [cite: 50]
            utility = self.budget - spot.base_price - spot.distance_to_exit
            
            if utility > 0:
                # Enchère sincère (Strategy-proofness de Vickrey)
                bid_amount = self.budget 
                self.model.manager.receive_bid(self, spot, bid_amount)

    def allocate_spot(self, spot, price):
        self.target_spot = spot
        spot.is_occupied = True # Réservation immédiate
        self.state = "MOVING"
        self.model.total_revenue += price # KPI Economique 

    def move_towards_target(self):
        # Déplacement simple pas à pas
        x, y = self.pos
        tx, ty = self.target_spot.pos
        
        if x < tx: x += 1
        elif x > tx: x -= 1
        elif y < ty: y += 1
        elif y > ty: y -= 1
        
        self.model.grid.move_agent(self, (x, y))
        
        if (x, y) == (tx, ty):
            self.state = "PARKED"
            # KPI Efficiency: Distance marchée [cite: 76]
            self.model.total_walking_distance += self.target_spot.distance_to_exit