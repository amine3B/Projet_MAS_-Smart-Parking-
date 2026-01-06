import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Play, Pause, RotateCcw, Zap, Activity, DollarSign, AlertCircle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// Adresse du Backend Python
const API_URL = "http://127.0.0.1:8000";

const SmartParkingClient = () => {
  // --- ÉTATS ---
  const [isPlaying, setIsPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Données de simulation
  const [gridConfig, setGridConfig] = useState({ width: 20, height: 20 });
  const [simState, setSimState] = useState({ 
    spots: [], 
    cars: [], 
    metrics: { occupancy: 0, revenue: 0, step: 0 } 
  });
  const [history, setHistory] = useState([]);
  
  // Paramètres utilisateur
  const [mode, setMode] = useState('FCFS');
  const [spawnRate, setSpawnRate] = useState(0.3);

  const timerRef = useRef(null);

  // --- API COMMUNICATIONS ---

  // 1. Initialiser (Reset)
  const initSimulation = async () => {
    setLoading(true);
    setIsPlaying(false);
    try {
      // On envoie les paramètres au Python
      const res = await fetch(`${API_URL}/init?spawn_rate=${spawnRate}&mode=${mode}`, { 
        method: 'POST' 
      });
      if (!res.ok) throw new Error("Erreur Backend");
      
      const data = await res.json();
      setGridConfig(data.config); // Adapter la grille à la config Python
      
      // Récupérer l'état initial (Step 0)
      await fetchStep(); 
      setHistory([]);
      setError(null);
    } catch (err) {
      console.error("Connection Error:", err);
      setError("Impossible de contacter le serveur Python. Vérifiez que 'uvicorn' tourne bien.");
    }
    setLoading(false);
  };

  // 2. Étape suivante
  const fetchStep = async () => {
    try {
      const res = await fetch(`${API_URL}/step`);
      const data = await res.json();
      
      if (data.error) {
        // Si le serveur a redémarré, on réinitialise
        await initSimulation();
        return;
      }

      setSimState(data);
      
      // Mise à jour de l'historique pour le graphique
      setHistory(prev => {
        // Sécurité si metrics est manquant
        const currentRevenue = data.metrics?.revenue || 0;
        const currentStep = data.metrics?.step || 0;
        
        const newEntry = { step: currentStep, revenue: currentRevenue };
        const newHistory = [...prev, newEntry];
        if (newHistory.length > 50) newHistory.shift(); // Garder les 50 derniers points
        return newHistory;
      });

    } catch (err) {
      console.error("Step Error:", err);
      setIsPlaying(false);
    }
  };

  // --- LIFECYCLE ---

  // Démarrage initial
  useEffect(() => {
    initSimulation();
  }, []);

  // Boucle de jeu
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(fetchStep, 200); // 5 FPS (200ms)
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [isPlaying]);

  // Changement de mode = Reset
  const handleModeChange = (newMode) => {
    setMode(newMode);
    // On laisse le useEffect sur [mode] ou on appelle init manuellement
    // Ici on force un petit délai pour que l'état se mette à jour avant l'appel
    setTimeout(() => {
       // Note: Dans une vraie app, on utiliserait un useEffect sur 'mode' qui déclenche init
       // Mais ici on veut contrôler le moment du reset pour éviter les boucles
    }, 0);
  };
  
  // Re-init quand le mode change effectivement via l'UI
  useEffect(() => {
      if(!loading) initSimulation();
  }, [mode]);


  // --- RENDU OPTIMISÉ ---

  // Création d'une map pour accès O(1) aux positions au lieu de find() O(N)
  const gridMap = useMemo(() => {
    const map = {};
    simState.spots.forEach(s => { map[`${s.x}-${s.y}`] = { type: 'spot', data: s }; });
    simState.cars.forEach(c => { 
      // La voiture écrase le spot dans la map visuelle, ou on gère la superposition
      if (map[`${c.x}-${c.y}`]) {
          map[`${c.x}-${c.y}`].car = c;
      } else {
          map[`${c.x}-${c.y}`] = { type: 'car_only', car: c };
      }
    });
    return map;
  }, [simState]);

  const renderCell = (x, y) => {
    const cellKey = `${x}-${y}`;
    const cellData = gridMap[cellKey];
    
    let baseClass = "w-full h-full rounded-sm flex items-center justify-center text-[8px] transition-colors duration-200 relative";
    let bgClass = "bg-slate-100"; // Couleur Route par défaut

    let spot = null;
    let car = null;

    if (cellData) {
        if (cellData.type === 'spot') spot = cellData.data;
        if (cellData.car) car = cellData.car;
        
        if (spot) {
            // Logique couleur des places
            if (spot.occupied && car && car.state === 'PARKED') bgClass = "bg-red-500"; // Garé
            else if (spot.occupied) bgClass = "bg-red-200"; // Réservé mais pas encore arrivé
            else if (spot.type === 'VIP') bgClass = "bg-amber-400";
            else if (spot.type === 'Handicap') bgClass = "bg-blue-500";
            else bgClass = "bg-emerald-500";
        }
    }

    return (
      <div key={cellKey} className={`${baseClass} ${bgClass}`} style={{ width: '22px', height: '22px', margin: '1px' }}>
        {spot && !car && <span className="opacity-30 font-bold select-none text-[6px]">{spot.type[0]}</span>}
        
        {car && (
          <div className={`absolute w-[18px] h-[18px] rounded-full shadow-md flex items-center justify-center z-10 
              ${car.state === 'SEARCHING' ? 'bg-purple-600 animate-pulse' : 'bg-slate-900'}
              transition-all duration-300`}>
            {/* Affiche le budget si disponible */}
            <span className="text-[6px] text-white font-mono">${car.budget}</span>
          </div>
        )}
      </div>
    );
  };

  // Génération de la grille
  const gridCells = [];
  for (let y = 0; y < gridConfig.height; y++) {
    for (let x = 0; x < gridConfig.width; x++) {
      gridCells.push(renderCell(x, y));
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans text-slate-800 flex flex-col items-center">
      
      {/* HEADER */}
      <div className="w-full max-w-6xl bg-white p-4 rounded-2xl shadow-sm border border-slate-200 mb-6 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-lg text-white"><Zap size={24} /></div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Smart Parking (Python Core)</h1>
            <p className="text-xs text-slate-500 flex items-center gap-2">
               {error ? <span className="text-red-500 font-bold flex items-center gap-1"><AlertCircle size={12}/> {error}</span> : <span className="text-emerald-600 font-bold">● Backend Connected</span>}
            </p>
          </div>
        </div>

        <div className="flex gap-2 bg-slate-100 p-1 rounded-lg">
           <button onClick={() => setMode('FCFS')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'FCFS' ? 'bg-white shadow text-indigo-600' : 'text-slate-500'}`}>FCFS</button>
           <button onClick={() => setMode('AUCTION')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'AUCTION' ? 'bg-white shadow text-amber-600' : 'text-slate-500'}`}>Enchères</button>
        </div>

        <div className="flex gap-2">
           <button onClick={() => setIsPlaying(!isPlaying)} disabled={!!error} className={`p-3 text-white rounded-xl shadow-lg transition-all ${error ? 'bg-slate-300' : 'bg-indigo-600 hover:bg-indigo-700 shadow-indigo-200'}`}>
             {isPlaying ? <Pause size={20} /> : <Play size={20} />}
           </button>
           <button onClick={initSimulation} className="p-3 bg-white border border-slate-200 text-slate-600 rounded-xl hover:bg-slate-50">
             <RotateCcw size={20} />
           </button>
        </div>
      </div>

      <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* STATS & CHARTS */}
        <div className="lg:col-span-4 flex flex-col gap-4">
           {/* Cards */}
           <div className="grid grid-cols-2 gap-3">
             <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm">
                <div className="flex items-center gap-2 text-slate-400 mb-1"><Activity size={14} /> <span className="text-[10px] uppercase font-bold">Occupancy</span></div>
                <div className="text-2xl font-bold text-slate-800">{Math.round(simState.metrics.occupancy)}%</div>
             </div>
             <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm">
                <div className="flex items-center gap-2 text-emerald-500 mb-1"><DollarSign size={14} /> <span className="text-[10px] uppercase font-bold">Revenue</span></div>
                <div className="text-2xl font-bold text-emerald-600">
                  ${(simState.metrics?.revenue || 0).toFixed(2)}
                </div>
             </div>
           </div>
           
           {/* Parameters */}
           <div className="bg-white p-5 rounded-xl border border-slate-100 shadow-sm space-y-4">
             <div>
               <label className="text-xs font-bold text-slate-500 mb-2 block flex justify-between">
                 <span>Trafic (Spawn Rate)</span>
                 <span className="text-indigo-600">{spawnRate}</span>
               </label>
               <input 
                 type="range" min="0.05" max="0.9" step="0.05" 
                 value={spawnRate} 
                 onChange={(e) => setSpawnRate(parseFloat(e.target.value))} 
                 className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
               />
             </div>
           </div>

           {/* Chart */}
           <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm flex-grow min-h-[200px]">
             <h3 className="text-xs font-bold text-slate-400 uppercase mb-4">Revenue Trend</h3>
             <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={history}>
                  <defs>
                    <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="step" hide />
                  <YAxis tick={{fontSize: 10}} stroke="#cbd5e1" />
                  <Tooltip contentStyle={{borderRadius:'8px', border:'none', boxShadow:'0 4px 12px rgba(0,0,0,0.1)'}} />
                  <Area type="monotone" dataKey="revenue" stroke="#10b981" fillOpacity={1} fill="url(#colorRev)" strokeWidth={2} />
                </AreaChart>
             </ResponsiveContainer>
           </div>
        </div>

        {/* PARKING GRID */}
        <div className="lg:col-span-8">
           <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col items-center">
              <div className="w-full flex justify-between items-center mb-4 px-4">
                 <h2 className="font-bold text-slate-700">Live Map ({gridConfig.width}x{gridConfig.height})</h2>
                 <div className="flex gap-3 text-[10px] font-bold uppercase text-slate-400">
                    <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-slate-900"></div> Car</div>
                    <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-sm bg-purple-600 animate-pulse"></div> Search</div>
                    <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-sm bg-amber-400"></div> VIP</div>
                 </div>
              </div>
              
              <div 
                className="grid gap-0 bg-slate-50 p-4 rounded-xl border border-slate-100 transition-all"
                style={{ gridTemplateColumns: `repeat(${gridConfig.width}, min-content)` }}
              >
                 {gridCells}
              </div>
           </div>
        </div>

      </div>
    </div>
  );
};

export default SmartParkingClient;