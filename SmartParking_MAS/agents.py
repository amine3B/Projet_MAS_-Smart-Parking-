from mesa import Agent
import random

class ParkingSpotAgent(Agent):
    """Agent représentant une place de parking"""
    def __init__(self, unique_id, model, spot_type="Standard", pos=(0, 0)):
        super().__init__(unique_id, model)
        self.spot_type = spot_type
        self.is_occupied = False
        self.reserved_by = None 
        self.pos = pos
        
        # Prix selon le type
        if spot_type == "VIP": self.base_price = 20
        elif spot_type == "Handicap": self.base_price = 10
        else: self.base_price = 5

    def step(self):
        pass


class ParkingManagerAgent(Agent):
    """Gère les enchères et priorités"""
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
        for spot_id, bid_list in list(self.bids.items()):
            spot = self.model.grid_agents.get(spot_id)
            if not spot or spot.is_occupied or spot.reserved_by: continue
            
            if bid_list:
                bid_list.sort(key=lambda x: x[1], reverse=True)
                winner, _ = bid_list[0]
                price = bid_list[1][1] if len(bid_list) > 1 else spot.base_price
                winner.allocate_spot(spot, price)
        self.bids = {}

    def resolve_priority(self):
        for spot_id, req_list in list(self.requests.items()):
            spot = self.model.grid_agents.get(spot_id)
            if not spot or spot.is_occupied or spot.reserved_by: continue
            
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
        self.stuck_counter = 0
        self.last_pos = None
        
        rand = random.random()
        if rand < 0.1: self.priority_score = 3
        elif rand < 0.3: self.priority_score = 2
        else: self.priority_score = 1

    def step(self):
        self.arrival_time += 1
        
        # --- GESTION DES BLOCAGES (CRITIQUE POUR LE DOUBLE SENS) ---
        if self.last_pos == self.pos:
            self.stuck_counter += 1
        else:
            self.stuck_counter = 0
        self.last_pos = self.pos
        
        # Si bloqué trop longtemps
        if self.stuck_counter > 20:
            if self.state == "MOVING" and self.target_spot:
                # On abandonne la place et on cherche ailleurs
                self.target_spot.is_occupied = False
                self.target_spot.reserved_by = None
                self.target_spot = None
                self.state = "SEARCHING"
                self.stuck_counter = 0
            elif self.state == "SEARCHING" and self.stuck_counter > 40:
                # On abandonne et on part
                self.state = "LEAVING"
                self.stuck_counter = 0
            elif self.state == "LEAVING" and self.stuck_counter > 20:
                # CAS CRITIQUE : Bloqué en sortant -> On disparaît pour débloquer le trafic
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
                return
        
        # --- MACHINE A ETATS ---
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
        avail = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied and not a.reserved_by]
        if avail:
            avail.sort(key=lambda s: abs(self.pos[0] - s.pos[0]) + abs(self.pos[1] - s.pos[1]))
            candidates = avail[:3]
            if candidates: self.allocate_spot(random.choice(candidates), candidates[0].base_price)

    def behavior_auction(self):
        avail = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied and not a.reserved_by]
        if avail:
            candidates = sorted(avail, key=lambda s: abs(self.pos[0] - s.pos[0]) + abs(self.pos[1] - s.pos[1]))[:3]
            for spot in candidates:
                if self.budget > spot.base_price: self.model.manager.receive_bid(self, spot, self.budget)

    def behavior_priority(self):
        avail = [a for a in self.model.schedule.agents if isinstance(a, ParkingSpotAgent) and not a.is_occupied and not a.reserved_by]
        if avail:
            avail.sort(key=lambda s: abs(self.pos[0] - s.pos[0]) + abs(self.pos[1] - s.pos[1]))
            self.model.manager.receive_request(self, avail[0])

    def allocate_spot(self, spot, price):
        self.target_spot = spot
        spot.is_occupied = True 
        spot.reserved_by = self.unique_id
        self.state = "MOVING"
        self.model.total_revenue += price 
        self.model.total_walking_distance += abs(self.pos[0] - spot.pos[0]) + abs(self.pos[1] - spot.pos[1])

    def move_towards_target(self):
        if not self.pos: return
            
        x, y = self.pos
        w, h = self.model.width, self.model.height
        tx, ty = x, y 

        # --- CIBLE ---
        if self.state == "LEAVING":
            exit1 = (w - 1, 0)
            exit2 = (0, h - 1)
            
            # Sortie atteinte
            if (x, y) == exit1 or (x, y) == exit2:
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
                return

            # CHOIX SORTIE LA PLUS PROCHE
            dist1 = abs(x - exit1[0]) + abs(y - exit1[1])
            dist2 = abs(x - exit2[0]) + abs(y - exit2[1])
            tx, ty = exit1 if dist1 <= dist2 else exit2
            
        elif self.state == "MOVING" and self.target_spot:
            tx, ty = self.target_spot.pos
        else:
            return 

        # --- DÉPLACEMENT (Sans direction imposée) ---
        moves = self.calculate_legal_moves(x, y, tx, ty, w, h)
        
        for next_x, next_y in moves:
            if (next_x, next_y) == (x, y): continue
                
            cell_contents = self.model.grid.get_cell_list_contents([(next_x, next_y)])
            blocking_car = next((obj for obj in cell_contents if isinstance(obj, VehicleAgent) and obj is not self), None)
            spot_on_cell = next((obj for obj in cell_contents if isinstance(obj, ParkingSpotAgent)), None)
            
            can_move = True
            if blocking_car: can_move = False
            
            # Ne pas traverser les places de parking des autres
            if spot_on_cell:
                if self.target_spot and spot_on_cell == self.target_spot: can_move = True
                elif spot_on_cell.pos == self.pos: can_move = True
                else: can_move = False

            if can_move:
                self.model.grid.move_agent(self, (next_x, next_y))
                if self.state == "MOVING" and (next_x, next_y) == (tx, ty):
                    self.state = "PARKED"
                    self.model.parked_count += 1
                return
        
        self.waiting_time += 1

    def calculate_legal_moves(self, x, y, tx, ty, w, h):
        """Retourne les cases routes adjacentes sans sens interdit"""
        
        # Si cible adjacente, on y va
        if abs(x - tx) + abs(y - ty) == 1:
            return [(tx, ty), (x, y)]

        candidates = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        valid_moves = []
        
        for mx, my in candidates:
            if 0 <= mx < w and 0 <= my < h:
                # Définition des routes (Doit matcher model.py)
                is_vertical_road = (mx % 3 == 0) or (mx == w - 1)
                is_horizontal_road = (my == 0) or (my == 1) or (my == h - 2) or (my == h - 1)
                is_road = is_vertical_road or is_horizontal_road
                
                if is_road or (mx, my) == (tx, ty):
                    valid_moves.append((mx, my))

        if not valid_moves: return [(x, y)]

        # Tri par distance + petit aléatoire pour casser les symétries
        valid_moves.sort(key=lambda m: abs(m[0] - tx) + abs(m[1] - ty) + random.uniform(0, 0.5))
        
        return valid_moves + [(x, y)]