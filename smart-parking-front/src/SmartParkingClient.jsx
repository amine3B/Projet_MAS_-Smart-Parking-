import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Play, Pause, RotateCcw, Zap, Activity, DollarSign, AlertCircle, Clock, CarFront, LogOut, LogIn, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';
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
    metrics: { occupancy: 0, revenue: 0, step: 0, fairness_variance: 0, entered: 0, exited: 0 } 
  });
  const [history, setHistory] = useState([]);
  
  // Paramètres utilisateur
  const [mode, setMode] = useState('FCFS');
  const [spawnRate, setSpawnRate] = useState(0.3);

  const timerRef = useRef(null);

  // --- API COMMUNICATIONS ---

  const initSimulation = async () => {
    setLoading(true);
    setIsPlaying(false);
    try {
      const res = await fetch(`${API_URL}/init?spawn_rate=${spawnRate}&mode=${mode}`, { 
        method: 'POST' 
      });
      if (!res.ok) throw new Error("Erreur Backend");
      
      const data = await res.json();
      if (data.config) {
          setGridConfig(data.config); 
      }
      
      await fetchStep(); 
      setHistory([]);
      setError(null);
    } catch (err) {
      console.error("Connection Error:", err);
      setError("Impossible de contacter le serveur Python. Vérifiez que 'uvicorn' tourne bien sur le port 8000.");
    }
    setLoading(false);
  };

  const fetchStep = async () => {
    try {
      const res = await fetch(`${API_URL}/step`);
      const data = await res.json();
      
      if (data.error) {
        await initSimulation();
        return;
      }

      setSimState(data);
      
      setHistory(prev => {
        const currentRevenue = data.metrics?.revenue || 0;
        const currentStep = data.metrics?.step || 0;
        const newEntry = { step: currentStep, revenue: currentRevenue };
        const newHistory = [...prev, newEntry];
        if (newHistory.length > 50) newHistory.shift(); 
        return newHistory;
      });

    } catch (err) {
      console.error("Step Error:", err);
      setIsPlaying(false);
    }
  };

  // --- LIFECYCLE ---

  useEffect(() => {
    initSimulation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(fetchStep, 200); 
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [isPlaying]);

  useEffect(() => {
      if(!loading) initSimulation();
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);


  // --- RENDU RÉALISTE ---

  const gridMap = useMemo(() => {
    const map = {};
    simState.spots.forEach(s => { map[`${s.x}-${s.y}`] = { type: 'spot', data: s }; });
    simState.cars.forEach(c => { 
      if (map[`${c.x}-${c.y}`]) {
          map[`${c.x}-${c.y}`].car = c;
      } else {
          map[`${c.x}-${c.y}`] = { type: 'car_only', car: c };
      }
    });
    return map;
  }, [simState]);

  // Logique de direction des routes (copiée du Backend pour la visualisation)
  const getRoadDirection = (x, y, w, h) => {
      // Routes horizontales
      if (y === 0) return 'left-right'; // Haut (Entrée G -> Sortie D)
      if (y === h - 1) return 'left-right'; // Bas (Sortie G <- Entrée D)

      // Routes verticales
      if (x === 0) return 'down'; // Entrée principale
      if (x === w - 1) return 'up'; // Entrée secondaire qui monte
      
      const idx = Math.round(x / 3);
      if (idx % 2 !== 0) return 'up'; // Impair = Monte
      return 'down'; // Pair = Descend
  };

  const renderCell = (x, y) => {
    const cellKey = `${x}-${y}`;
    const cellData = gridMap[cellKey];
    
    // Style de base (Route / Asphalte)
    let containerClass = "relative flex items-center justify-center";
    let bgStyle = { backgroundColor: '#334155' }; 
    
    let content = null;
    let overlayLabel = null; 
    let roadMarking = null;

    // --- MARQUAGE CROISÉ : 2 ENTRÉES / 2 SORTIES ---
    // IN : Haut-Gauche (0,0) et Bas-Droite (W-1, H-1)
    // OUT : Haut-Droite (W-1, 0) et Bas-Gauche (0, H-1)
    
    const isTopLeft = (x === 0 && y === 0);
    const isBottomRight = (x === gridConfig.width - 1 && y === gridConfig.height - 1);
    
    const isTopRight = (x === gridConfig.width - 1 && y === 0);
    const isBottomLeft = (x === 0 && y === gridConfig.height - 1);

    if (isTopLeft || isBottomRight) {
        overlayLabel = (
            <div className="absolute inset-0 border-2 border-emerald-500/60 bg-emerald-500/20 z-0 flex items-center justify-center pointer-events-none">
                 <span className="text-[5px] font-black text-emerald-300 -rotate-90 tracking-tighter shadow-sm">IN</span>
            </div>
        );
    } else if (isTopRight || isBottomLeft) {
        overlayLabel = (
            <div className="absolute inset-0 border-2 border-red-500/60 bg-red-500/20 z-0 flex items-center justify-center pointer-events-none">
                 <span className="text-[5px] font-black text-red-300 -rotate-90 tracking-tighter shadow-sm">OUT</span>
            </div>
        );
    }

    // --- DÉTECTION TYPE DE CASE ---
    const isRoad = !cellData || cellData.type === 'car_only';

    if (isRoad) {
        // Ajouter flèches directionnelles sur la route
        const dir = getRoadDirection(x, y, gridConfig.width, gridConfig.height);
        
        // --- DOUBLE SENS VISUEL (DIVISÉ) ---
        // Simule deux voies (Aller/Retour) en dessinant une ligne pointillée centrale
        // et en affichant des flèches opposées si nécessaire, ou une flèche principale si sens unique.
        
        // Pour cette simulation spécifique, nous gardons des sens uniques par colonne
        // pour simplifier le pathfinding (comme des rues à sens unique en ville).
        // Mais nous visualisons cela clairement.
        
        if (y % 4 === 2 || (y === 0 && x % 4 === 2) || (y === gridConfig.height - 1 && x % 4 === 2)) {
            let ArrowIcon = null;
            // Pour simuler "Aller/Vient" sur une même case, on pourrait mettre deux petites flèches
            // Mais ici, le modèle de données est à sens unique par case. 
            // On affiche donc le sens unique de la rue.
            if (dir === 'down') ArrowIcon = ArrowDown;
            if (dir === 'up') ArrowIcon = ArrowUp;
            
            if (ArrowIcon) {
                roadMarking = (
                    <div className="absolute inset-0 flex items-center justify-center opacity-20 pointer-events-none">
                        <ArrowIcon size={10} className="text-slate-300" />
                    </div>
                );
            }
        }
        
        // Texture bitume avec ligne médiane (Séparation des voies si applicable)
        if (x % 3 === 0 || x === gridConfig.width - 1 || y === 0 || y === gridConfig.height - 1) {
            bgStyle = { ...bgStyle, backgroundImage: 'linear-gradient(to bottom, transparent 40%, rgba(255,255,255,0.05) 40%, rgba(255,255,255,0.05) 60%, transparent 60%)' };
            // Ligne jaune centrale pour simuler la double voie si on voulait (visuel)
            // bgStyle.borderLeft = "1px dashed rgba(255, 255, 0, 0.1)"; 
        }
    }

    if (cellData) {
        const { type, data: spot, car } = cellData;

        // --- Rendu d'une Place de Parking ---
        if (type === 'spot' && spot) {
            let borderColor = '#64748b'; 
            let markIcon = null;

            // Logique de zone (Basée sur distance sortie)
            if (spot.type === 'VIP') {
                borderColor = '#fbbf24'; 
                bgStyle = { backgroundColor: '#2d2518' }; 
                markIcon = <span className="absolute bottom-0.5 right-0.5 text-[5px] text-amber-500/60 font-bold">VIP</span>;
            } else if (spot.type === 'Handicap') {
                borderColor = '#3b82f6'; 
                bgStyle = { backgroundColor: '#172554' }; 
                markIcon = <span className="absolute bottom-0.5 right-0.5 text-[5px] text-blue-400/60 font-bold">♿</span>;
            } else {
                bgStyle = { backgroundColor: '#475569' }; 
            }

            containerClass += " border-x border-t"; 
            
            const isParked = spot.occupied && car && car.state === 'PARKED';
            const isReserved = spot.occupied && !isParked; 
            
            content = (
                <div className="w-full h-full relative flex items-center justify-center" style={{ borderColor: borderColor, borderWidth: '1px', borderStyle: 'solid', borderBottom: 'none' }}>
                    {!isParked && markIcon}
                    {isReserved && <div className="absolute w-1 h-1 rounded-full bg-red-500 animate-pulse top-1 right-1"></div>}
                    {car && (
                        <div className={`absolute inset-0 flex items-center justify-center transition-all duration-300 z-10`}>
                            <CarFront 
                                size={18} 
                                className={`drop-shadow-md ${
                                    car.state === 'SEARCHING' ? 'text-purple-400 animate-pulse' : 
                                    isParked ? 'text-emerald-400' : 'text-slate-200'
                                }`} 
                                fill={isParked ? "#059669" : "#475569"} 
                            />
                            {car.budget !== undefined && (
                                <span className="absolute -top-1 right-0 bg-black/80 text-white text-[5px] px-0.5 rounded shadow z-20">
                                    ${car.budget}
                                </span>
                            )}
                        </div>
                    )}
                </div>
            );
        }
        
        // --- Rendu d'une Voiture sur la Route ---
        else if (type === 'car_only' && car) {
             content = (
                <div className="absolute inset-0 flex items-center justify-center z-20">
                     <CarFront 
                        size={18} 
                        className="text-indigo-400 drop-shadow-xl" 
                        fill="#4338ca"
                    />
                </div>
             );
        }
    } else {
        // --- Route Vide ---
        bgStyle = { backgroundColor: '#334155' }; 
    }

    return (
      <div key={cellKey} className={containerClass} style={{ width: '24px', height: '24px', ...bgStyle }}>
        {overlayLabel}
        {roadMarking}
        {content}
      </div>
    );
  };

  const gridCells = [];
  for (let y = 0; y < gridConfig.height; y++) {
    for (let x = 0; x < gridConfig.width; x++) {
      gridCells.push(renderCell(x, y));
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 p-4 md:p-8 font-sans text-slate-200 flex flex-col items-center">
      
      {/* HEADER */}
      <div className="w-full max-w-6xl bg-slate-800 p-4 rounded-2xl shadow-lg border border-slate-700 mb-6 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-500 p-2 rounded-lg text-white shadow-lg shadow-indigo-500/30"><Zap size={24} /></div>
          <div>
            <h1 className="text-xl font-bold text-white">Smart Parking Simulator</h1>
            <p className="text-xs text-slate-400 flex items-center gap-2">
               {error ? <span className="text-red-400 font-bold flex items-center gap-1"><AlertCircle size={12}/> {error}</span> : <span className="text-emerald-400 font-bold">● System Online</span>}
            </p>
          </div>
        </div>

        <div className="flex gap-2 bg-slate-900/50 p-1 rounded-lg border border-slate-700">
           <button onClick={() => setMode('FCFS')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'FCFS' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}>FCFS</button>
           <button onClick={() => setMode('AUCTION')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'AUCTION' ? 'bg-amber-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}>Enchères</button>
           <button onClick={() => setMode('PRIORITY')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'PRIORITY' ? 'bg-pink-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}>Priorité</button>
        </div>

        <div className="flex gap-2">
           <button onClick={() => setIsPlaying(!isPlaying)} disabled={!!error} className={`p-3 text-white rounded-xl shadow-lg transition-all ${error ? 'bg-slate-700' : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-900/50'}`}>
             {isPlaying ? <Pause size={20} /> : <Play size={20} />}
           </button>
           <button onClick={initSimulation} className="p-3 bg-slate-700 border border-slate-600 text-slate-300 rounded-xl hover:bg-slate-600">
             <RotateCcw size={20} />
           </button>
        </div>
      </div>

      <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* STATS & CHARTS */}
        <div className="lg:col-span-4 flex flex-col gap-4">
           {/* Cards */}
           <div className="grid grid-cols-2 gap-3">
             <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
                <div className="flex items-center gap-2 text-slate-400 mb-1"><Activity size={14} /> <span className="text-[10px] uppercase font-bold">Occupancy</span></div>
                <div className="text-2xl font-bold text-white">{Math.round(simState.metrics.occupancy)}%</div>
             </div>
             <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
                <div className="flex items-center gap-2 text-emerald-400 mb-1"><DollarSign size={14} /> <span className="text-[10px] uppercase font-bold">Revenue</span></div>
                <div className="text-2xl font-bold text-emerald-400">
                  ${(simState.metrics?.revenue || 0).toFixed(2)}
                </div>
             </div>
             
             {/* Traffic Flow Metric */}
             <div className="col-span-2 bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg flex justify-between items-center">
                 <div className="flex gap-6 w-full">
                    <div className="flex flex-col items-center flex-1 border-r border-slate-700">
                        <div className="flex items-center gap-1 text-emerald-400 mb-1"><LogIn size={14} /> <span className="text-[10px] uppercase font-bold">Entered</span></div>
                        <div className="text-xl font-bold text-white">{simState.metrics.entered || 0}</div>
                    </div>
                    <div className="flex flex-col items-center flex-1">
                        <div className="flex items-center gap-1 text-red-400 mb-1"><LogOut size={14} /> <span className="text-[10px] uppercase font-bold">Exited</span></div>
                        <div className="text-xl font-bold text-white">{simState.metrics.exited || 0}</div>
                    </div>
                 </div>
             </div>

             {/* Fairness Metric */}
             <div className="col-span-2 bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg flex justify-between items-center">
                <div>
                    <div className="flex items-center gap-2 text-amber-500 mb-1"><Clock size={14} /> <span className="text-[10px] uppercase font-bold">Inequity Index</span></div>
                    <div className="text-[10px] text-slate-500">Waiting Time Variance</div>
                </div>
                <div className="text-xl font-bold text-slate-200 font-mono">
                  {(simState.metrics?.fairness_variance || 0).toFixed(1)}
                </div>
             </div>
           </div>
           
           {/* Parameters */}
           <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-lg space-y-4">
             <div>
               <label className="text-xs font-bold text-slate-400 mb-2 flex justify-between">
                 <span>Trafic (Spawn Rate)</span>
                 <span className="text-indigo-400">{spawnRate}</span>
               </label>
               <input 
                 type="range" min="0.05" max="0.9" step="0.05" 
                 value={spawnRate} 
                 onChange={(e) => setSpawnRate(parseFloat(e.target.value))} 
                 className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
               />
             </div>
           </div>

           {/* Chart */}
           <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg flex-grow min-h-[200px]">
             <h3 className="text-xs font-bold text-slate-400 uppercase mb-4">Revenue Trend</h3>
             <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={history}>
                  <defs>
                    <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0.2}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
                  <XAxis dataKey="step" hide />
                  <YAxis tick={{fontSize: 10, fill: '#94a3b8'}} stroke="#475569" />
                  <Tooltip contentStyle={{backgroundColor: '#1e293b', borderRadius:'8px', border:'1px solid #334155', color: '#fff'}} />
                  <Area type="monotone" dataKey="revenue" stroke="#10b981" fillOpacity={1} fill="url(#colorRev)" strokeWidth={2} />
                </AreaChart>
             </ResponsiveContainer>
           </div>
        </div>

        {/* PARKING GRID */}
        <div className="lg:col-span-8">
           <div className="bg-slate-800 p-6 rounded-2xl shadow-lg border border-slate-700 flex flex-col items-center">
              <div className="w-full flex justify-between items-center mb-4 px-4">
                 <h2 className="font-bold text-slate-200">Live Map ({gridConfig.width}x{gridConfig.height})</h2>
                 <div className="flex gap-3 text-[10px] font-bold uppercase text-slate-400">
                    <div className="flex items-center gap-1"><ArrowDown size={10}/> / <ArrowUp size={10}/> Flow</div>
                    <div className="flex items-center gap-1"><LogIn size={12} className="text-emerald-400"/> IN</div>
                    <div className="flex items-center gap-1"><LogOut size={12} className="text-red-400"/> OUT</div>
                 </div>
              </div>
              
              <div 
                className="grid gap-0 bg-slate-900 p-4 rounded-xl border border-slate-700 shadow-inner"
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

export default SmartParkingClient ;