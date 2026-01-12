from mesa import Agent
import random

class ParkingSpotAgent(Agent):
    def __init__(self, unique_id, model, spot_type="Standard", pos=(0,0)):
        super().__init__(unique_id, model)
        self.spot_type = spot_type
        self.is_occupied = False
        self.reserved_by = None 
        self.pos = pos
        # Distance au centre pour l'estimation de valeur
        center_x, center_y = model.width//2, model.height//2
        self.dist_to_center = abs(pos[0] - center_x) + abs(pos[1] - center_y)
        
        if spot_type == "VIP": self.base_price = 20
        elif spot_type == "Handicap": self.base_price = 10
        else: self.base_price = 5

class ParkingManagerAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.bids = {}
        self.requests = {}

    def step(self):
        if self.model.mode == "AUCTION":
            self.resolve_auction()
        elif self.model.mode == "PRIORITY":
            self.resolve_priority()

    def resolve_auction(self):
        for spot_id, bid_list in self.bids.items():
            spot = self.model.grid_agents.get(spot_id)
            if not spot or spot.is_occupied: continue
            
            if bid_list:
                bid_list.sort(key=lambda x: x[1], reverse=True)
                winner, _ = bid_list[0]
                price = bid_list[1][1] if len(bid_list) > 1 else spot.base_price
                winner.allocate_spot(spot, price)
        self.bids = {}

    def resolve_priority(self):
        for spot_id, req_list in self.requests.items():
            spot = self.model.grid_agents.get(spot_id)
            if not spot or spot.is_occupied: continue
            
            if req_list:
                req_list.sort(key=lambda x: (-x[0].priority_score, x[0].arrival_time))
                winner = req_list[0][0]
                winner.allocate_spot(spot, price=spot.base_price)
        self.requests = {}

    def receive_bid(self, vehicle, spot, amount):
        if spot.unique_id not in self.bids: self.bids[spot.unique_id] = []
        self.bids[spot.unique_id].append((vehicle, amount))

    def receive_request(self, vehicle, spot):
        if spot.unique_id not in self.requests: self.requests[spot.unique_id] = []
        self.requests[spot.unique_id].append((vehicle, 0))

class VehicleAgent(Agent):
    def __init__(self, unique_id, model, budget, preferred_type):
        super().__init__(unique_id, model)
        self.budget = budget 
        self.preferred_type = preferred_type
        self.state = "SEARCHING" 
        self.target_spot = None
        self.arrival_time = 0 
        self.waiting_time = 0 
        self.parking_duration = random.randint(50, 200)

        rand = random.random()
        if rand < 0.1: self.priority_score = 3
        elif rand < 0.3: self.priority_score = 2
        else: self.priority_score = 1

    def step(self):
        self.arrival_time += 1
        
        if self.state == "SEARCHING":
            self.waiting_time += 1
            if self.model.mode == "FCFS": self.behavior_fcfs()
            elif self.model.mode == "AUCTION": self.behavior_auction()
            elif self.model.mode == "PRIORITY": self.behavior_priority()
        
        elif self.state == "MOVING":
            self.move_towards_target()
        
        elif self.state == "PARKED":
            self.parking_duration -= 1
            if self.parking_duration <= 0:
                self.state = "LEAVING"
                if self.target_spot:
                    self.target_spot.is_occupied = False
                    self.target_spot.reserved_by = None
                    self.target_spot = None

        elif self.state == "LEAVING":
            self.move_towards_target()

    def behavior_fcfs(self):
        avail_spots = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied]
        if avail_spots:
            # Tri par distance
            avail_spots.sort(key=lambda s: abs(self.pos[0]-s.pos[0]) + abs(self.pos[1]-s.pos[1]))
            top_n = min(len(avail_spots), 3)
            candidates = avail_spots[:top_n]
            chosen = random.choice(candidates)
            self.allocate_spot(chosen, price=chosen.base_price)

    def behavior_auction(self):
        avail_spots = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied]
        candidates = sorted(avail_spots, key=lambda s: abs(self.pos[0]-s.pos[0]) + abs(self.pos[1]-s.pos[1]))[:3]
        for spot in candidates:
            utility = self.budget - spot.base_price
            if utility > 0:
                self.model.manager.receive_bid(self, spot, self.budget)

    def behavior_priority(self):
        avail_spots = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied]
        if avail_spots:
            avail_spots.sort(key=lambda s: abs(self.pos[0]-s.pos[0]) + abs(self.pos[1]-s.pos[1]))
            self.model.manager.receive_request(self, avail_spots[0])

    def allocate_spot(self, spot, price):
        self.target_spot = spot
        spot.is_occupied = True 
        spot.reserved_by = self.unique_id
        self.state = "MOVING"
        self.model.total_revenue += price 

    # --- NOUVEAU SYSTÈME DE TRAFIC ---
    def get_road_direction(self, x):
        """
        Retourne la direction autorisée pour une colonne donnée.
        1 = Down (Y augmente), -1 = Up (Y diminue)
        """
        w = self.model.width
        # Bords et colonnes
        if x == 0: return 1 # Entrée principale -> Bas
        if x == w - 1: return -1 # Sortie remontante -> Haut
        
        idx = round(x / 3)
        if idx % 2 != 0: return -1 # Impair = Monte
        return 1 # Pair = Descend

    def move_towards_target(self):
        x, y = self.pos
        w, h = self.model.width, self.model.height
        
        # 1. Définition de la cible (Place ou Sortie)
        tx, ty = (0, 0)
        
        if self.state == "LEAVING":
            # Sorties aux coins opposés
            exit1 = (w - 1, 0)      # Haut-Droite
            exit2 = (0, h - 1)      # Bas-Gauche
            dist1 = abs(x - exit1[0]) + abs(y - exit1[1])
            dist2 = abs(x - exit2[0]) + abs(y - exit2[1])
            tx, ty = exit1 if dist1 <= dist2 else exit2
            
            if (x, y) == (tx, ty):
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
                return
        
        elif self.state == "MOVING" and self.target_spot:
            tx, ty = self.target_spot.pos
        else:
            return 

        next_x, next_y = x, y
        
        # 2. Identification de la route verticale cible
        def get_nearest_vertical_road(col):
            base = round(col / 3) * 3
            edge = w - 1
            if abs(col - base) <= abs(col - edge): return base
            return edge

        target_road_x = get_nearest_vertical_road(tx)
        
        # 3. Logique de Mouvement avec Respect du Code de la Route
        
        # Est-ce qu'on est sur une zone d'intersection (Haut ou Bas) ?
        at_intersection = (y == 0 or y == h - 1)
        
        # Direction autorisée sur la route actuelle
        current_road_dir = self.get_road_direction(x)

        # CAS A : On doit changer de colonne (Navigation Latérale)
        # On ne peut changer de colonne QUE si on est en haut ou en bas
        if x != target_road_x:
            if at_intersection:
                # On se déplace vers la colonne cible
                if x < target_road_x: next_x += 1
                else: next_x -= 1
            else:
                # On n'est pas à une intersection, on doit continuer sur la route
                # jusqu'au bout pour faire demi-tour
                next_y = y + current_road_dir
        
        # CAS B : On est sur la bonne colonne (Approche ou Parking)
        elif x == target_road_x:
            # Si on est exactement à la hauteur cible (et potentiellement à coté pour se garer)
            if y == ty:
                if x != tx: # Dernier petit pas latéral pour entrer dans la place
                    next_x = tx
            else:
                # On veut aller vers ty.
                # Sens désiré vs Sens autorisé
                desired_dir = 1 if ty > y else -1
                
                if desired_dir == current_road_dir:
                    # Le sens est bon, on avance
                    next_y = y + current_road_dir
                else:
                    # SENS INTERDIT ! La cible est derrière nous.
                    # On doit continuer tout droit jusqu'à une intersection pour faire le tour.
                    next_y = y + current_road_dir

        # 4. Gestion des limites de grille (Sécurité)
        # Si on sort de la grille (ex: on arrive au bout d'une route), on force le virage
        if next_y < 0: 
            next_y = 0
            # Virage forcé à droite ou gauche pour chercher une autre route
            next_x = x + 1 if x < w - 1 else x - 1
            
        if next_y >= h: 
            next_y = h - 1
            next_x = x + 1 if x < w - 1 else x - 1

        # 5. Déplacement Effectif (Anti-collision)
        cell_contents = self.model.grid.get_cell_list_contents([(next_x, next_y)])
        blocking_car = next((obj for obj in cell_contents if isinstance(obj, VehicleAgent) and obj is not self), None)
        spot_on_cell = next((obj for obj in cell_contents if isinstance(obj, ParkingSpotAgent)), None)
        
        can_move = True
        if blocking_car: can_move = False 
        
        # Règle stricte : On ne roule pas SUR une place de parking sauf si c'est la nôtre
        if spot_on_cell:
            if self.target_spot and spot_on_cell == self.target_spot:
                can_move = True # On entre dans notre place
            else:
                can_move = False # C'est une place privée, on ne traverse pas
                # Si on est bloqué par une place, c'est qu'on a essayé de tourner trop tôt ou erreur de calcul
                # On annule le mouvement latéral
                if next_x != x: 
                    next_x = x # On reste sur la route
                    next_y = y + current_road_dir # On continue d'avancer

        if can_move:
            self.model.grid.move_agent(self, (next_x, next_y))
            if self.state == "MOVING" and (next_x, next_y) == (tx, ty):
                self.state = "PARKED"
                self.model.parked_count += 1
        else:
            self.waiting_time += 1