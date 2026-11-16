const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const clone = (value) => structuredClone(value);
const TEXT = {
  en: {
    operation:"Operation", diagnostics:"Diagnostics", settings:"Settings", instance:"Instance", loading:"Loading…",
    intro:"Your zones and shared circuit", opHelp:"Everyday controls and reported state.", circuit:"Shared circuit", zones:"Zones",
    state:"Reported state", target:"Supply target", actual:"Actual supply", outdoor:"Outdoor", strategy:"Supply strategy",
    diagnosticTitle:"Understand circuit behavior", diagnosticHelp:"Read reported values and saved configuration without entering an editor.",
    contributions:"Supply target contributions", applied:"Saved base curve", appliedHelp:"Read-only configuration. Learned corrections, trials and boost are separate live values below.",
    unavailable:"Unavailable", noEntries:"No Virtual Climate instances are available.", reload:"Reload saved configuration", supply:"Supply temperature control",
    settingsHelp:"Changes stay in this editor until you review and apply them.", heating:"Heating", cooling:"Cooling", connections:"Measurements and target output",
    constant:"Constant temperature", weather_compensated:"Weather compensation", direct:"Direct circuit", external:"External circuit",
    heating_strategy:"Heating strategy", heating_supply_target:"Constant heating target / fallback (°C)", cooling_supply_target:"Constant cooling target (°C)",
    target_supply_temperature_entity:"Target output", outdoor_sensor:"Outdoor sensor", supply_sensor:"Supply sensor", return_sensor:"Return sensor",
    heating_min:"Minimum heating supply (°C)", heating_max:"Maximum heating supply (°C)", cooling_min:"Minimum cooling supply (°C)", cooling_max:"Maximum cooling supply (°C)",
    learning_mode:"Curve learning", boost_enabled:"Recovery boost", off:"Off", learn:"Learn and apply", frozen:"Apply validated corrections only",
    curve:"Base weather curve", curveHelp:"Evenly spaced outdoor points. Supply temperature must not rise as outdoor temperature rises.",
    outdoor_min:"Outdoor minimum (°C)", outdoor_max:"Outdoor maximum (°C)", pointCount:"Number of points", point:"Point", supplyTemperature:"Supply (°C)", outdoorTemperature:"Outdoor (°C)",
    preview:"Draft preview", saved:"Saved", draft:"Draft", previewHelp:"Preview of the base curve only. It does not command the circuit.",
    invalidCurve:"Complete the numeric fields to preview the curve.", review:"Review changes", apply:"Apply changes", discard:"Discard changes", reviewTitle:"Review before applying",
    reloadWarning:"Applying changes reloads this instance. Circuit outputs may stop and resume after the applicable delays.",
    allReset:"Changing the interval or point count resets all curve learning.", pointsReset:"Learning resets for changed points:",
    noReset:"These changes do not reset curve-point learning.", noChanges:"No changes to apply.", changed:"Changed settings", from:"From", to:"To",
    success:"Settings saved. The instance is reloading.", unsaved:"Unsaved changes", leave:"Discard your unsaved changes?", menu:"Open sidebar",
    editOnly:"Supply settings are available to administrators.", moreSettings:"Other settings remain available in Settings → Devices & services → Virtual Climate.",
    supply_curve_target:"Base curve target", supply_learned_correction:"Learned correction", supply_probe_adjustment:"Trial adjustment", supply_boost:"Recovery boost",
    supply_learning_status:"Learning status", supply_command_error:"Target command error", plant_state:"Circuit sequence", coordinator_phase:"Coordinator phase",
    aggregate:"Demand", cycle:"Cycle", feedback:"Reported actuator activation does not confirm physical flow or heat delivery.",
    adminOnly:"Saved curve details are available to administrators.", retry:"Retry", conflict:"Configuration changed elsewhere. Reload the saved configuration before editing again.",
    failed:"The request failed. Check the connection and try again.", temperature:"Room setpoint", auto:"Follow system", mode:"Zone mode", current:"Room temperature", savedOnly:"Saved base curve",
    coolingHelp:"Cooling uses a constant target. Availability depends on circuit configuration.", fallbackHelp:"Used for constant heating and when outdoor data is invalid during weather compensation.",
    inactiveHelp:"The curve and learning settings are preserved while constant heating is selected.", requiredOutdoor:"Weather compensation requires an outdoor sensor.",
    zonesTab:"Zone settings", zoneEditor:"Zone settings", zoneHelp:"Edit one zone at a time. Changes stay here until you review and apply them.", zone:"Zone",
    savedConfig:"Saved configuration", savedConfigHelp:"Every stored setting of this instance, read-only. Empty optional settings are omitted.", globalSettings:"Instance and circuit", setting:"Setting", value:"Value", moreInfo:"About this setting",
    name:"Name", support_mode:"Supported modes", HEAT:"Heating only", COOL:"Cooling only", BOTH:"Heating and cooling", temperature_filter_enabled:"Smooth room temperature",
    sensor_air:"Room temperature sensor", switch_actuator:"Valve / actuator switch", sensor_rh:"Humidity sensor", sensor_floor:"Floor temperature sensor", window_switch:"Window contact",
    open_s:"Valve opening time (s)", close_s:"Valve closing time (s)", zone_min_on_s:"Minimum on time (s)", zone_min_off_s:"Minimum off time (s)",
    floor_heat_min:"Floor heating minimum (°C)", floor_heat_max:"Floor heating maximum (°C)", floor_cool_min:"Floor cooling minimum (°C)", floor_cool_max:"Floor cooling maximum (°C)",
    zoneSensors:"Sensors and actuator", zoneTiming:"Valve timing", zoneFloor:"Floor limits", zoneFloorHelp:"Optional, 10–40 °C. Heating stops at the heating maximum and cooling at the cooling minimum.",
    rhHelp:"With a humidity sensor configured, the zone stops cooling while it is unavailable. Without one, the zone cools without humidity protection.",
    zoneOther:"Zone ID, thermal profile and thermal parameters stay in Settings → Devices & services → Virtual Climate.", zoneSuccess:"Zone saved. The instance is reloading.",
  },
  ro: {
    operation:"Operare", diagnostics:"Diagnostic", settings:"Setări", instance:"Instanță", loading:"Se încarcă…",
    intro:"Zonele și circuitul comun", opHelp:"Comenzi uzuale și starea raportată.", circuit:"Circuit comun", zones:"Zone",
    state:"Stare raportată", target:"Țintă tur", actual:"Tur măsurat", outdoor:"Exterior", strategy:"Strategie tur",
    diagnosticTitle:"Înțelege comportamentul circuitului", diagnosticHelp:"Consultă valorile raportate și configurația salvată fără a intra în editor.",
    contributions:"Contribuțiile la ținta de tur", applied:"Curba de bază salvată", appliedHelp:"Configurație doar pentru consultare. Corecțiile învățate, probele și boostul sunt valori live separate, afișate mai jos.",
    unavailable:"Indisponibil", noEntries:"Nu sunt disponibile instanțe Virtual Climate.", reload:"Reîncarcă configurația salvată", supply:"Controlul temperaturii de tur",
    settingsHelp:"Modificările rămân în editor până le verifici și le aplici.", heating:"Încălzire", cooling:"Răcire", connections:"Măsurători și ieșire țintă",
    constant:"Temperatură constantă", weather_compensated:"Curbă climatică", direct:"Circuit direct", external:"Circuit extern",
    heating_strategy:"Strategie de încălzire", heating_supply_target:"Țintă constantă încălzire / fallback (°C)", cooling_supply_target:"Țintă constantă răcire (°C)",
    target_supply_temperature_entity:"Ieșire pentru ținta de tur", outdoor_sensor:"Senzor exterior", supply_sensor:"Senzor tur", return_sensor:"Senzor retur",
    heating_min:"Tur minim încălzire (°C)", heating_max:"Tur maxim încălzire (°C)", cooling_min:"Tur minim răcire (°C)", cooling_max:"Tur maxim răcire (°C)",
    learning_mode:"Învățarea curbei", boost_enabled:"Boost de recuperare", off:"Oprit", learn:"Învață și aplică", frozen:"Aplică doar corecțiile validate",
    curve:"Curba climatică de bază", curveHelp:"Puncte exterioare echidistante. Turul nu poate crește odată cu temperatura exterioară.",
    outdoor_min:"Exterior minim (°C)", outdoor_max:"Exterior maxim (°C)", pointCount:"Număr de puncte", point:"Punct", supplyTemperature:"Tur (°C)", outdoorTemperature:"Exterior (°C)",
    preview:"Previzualizare modificări", saved:"Salvat", draft:"Propus", previewHelp:"Previzualizarea curbei de bază. Nu trimite comenzi circuitului.",
    invalidCurve:"Completează câmpurile numerice pentru a vedea curba.", review:"Verifică modificările", apply:"Aplică modificările", discard:"Renunță la modificări", reviewTitle:"Verifică înainte de aplicare",
    reloadWarning:"Aplicarea reîncarcă această instanță. Ieșirile circuitului se pot opri și pot reporni după temporizările aplicabile.",
    allReset:"Schimbarea intervalului sau a numărului de puncte resetează întreaga învățare a curbei.", pointsReset:"Învățarea se resetează pentru punctele modificate:",
    noReset:"Aceste modificări nu resetează învățarea punctelor curbei.", noChanges:"Nu sunt modificări de aplicat.", changed:"Setări modificate", from:"Înainte", to:"După",
    success:"Setările au fost salvate. Instanța se reîncarcă.", unsaved:"Modificări nesalvate", leave:"Renunți la modificările nesalvate?", menu:"Deschide meniul lateral",
    editOnly:"Setările de tur sunt disponibile administratorilor.", moreSettings:"Celelalte setări sunt disponibile în Settings → Devices & services → Virtual Climate.",
    supply_curve_target:"Țintă din curba de bază", supply_learned_correction:"Corecție învățată", supply_probe_adjustment:"Ajustare de probă", supply_boost:"Boost de recuperare",
    supply_learning_status:"Stare învățare", supply_command_error:"Eroare comandă țintă", plant_state:"Secvență circuit", coordinator_phase:"Fază coordonator",
    aggregate:"Cerere", cycle:"Ciclu", feedback:"Activarea raportată a actuatorului nu confirmă debitul fizic sau căldura livrată.",
    adminOnly:"Detaliile curbei salvate sunt disponibile administratorilor.", retry:"Reîncearcă", conflict:"Configurația s-a modificat în altă sesiune. Reîncarcă valorile salvate înainte de a edita din nou.",
    failed:"Cererea a eșuat. Verifică conexiunea și reîncearcă.", temperature:"Temperatură dorită", auto:"Urmează sistemul", mode:"Mod zonă", current:"Temperatură cameră", savedOnly:"Curba de bază salvată",
    coolingHelp:"Răcirea folosește o țintă constantă. Disponibilitatea depinde de configurația circuitului.", fallbackHelp:"Folosită pentru încălzirea constantă și când datele exterioare sunt invalide în modul curbă climatică.",
    inactiveHelp:"Curba și setările de învățare se păstrează când este selectată încălzirea constantă.", requiredOutdoor:"Curba climatică necesită un senzor exterior.",
    zonesTab:"Setări zone", zoneEditor:"Setări zone", zoneHelp:"Editezi câte o zonă. Modificările rămân aici până le verifici și le aplici.", zone:"Zonă",
    savedConfig:"Configurația salvată", savedConfigHelp:"Toate setările salvate ale instanței, doar pentru consultare. Setările opționale goale nu sunt afișate.", globalSettings:"Instanță și circuit", setting:"Setare", value:"Valoare", moreInfo:"Despre această setare",
    name:"Nume", support_mode:"Moduri permise", HEAT:"Doar încălzire", COOL:"Doar răcire", BOTH:"Încălzire și răcire", temperature_filter_enabled:"Netezește temperatura camerei",
    sensor_air:"Senzor temperatură cameră", switch_actuator:"Comutator valvă / actuator", sensor_rh:"Senzor umiditate", sensor_floor:"Senzor temperatură pardoseală", window_switch:"Contact fereastră",
    open_s:"Timp deschidere valvă (s)", close_s:"Timp închidere valvă (s)", zone_min_on_s:"Timp minim pornit (s)", zone_min_off_s:"Timp minim oprit (s)",
    floor_heat_min:"Pardoseală încălzire minim (°C)", floor_heat_max:"Pardoseală încălzire maxim (°C)", floor_cool_min:"Pardoseală răcire minim (°C)", floor_cool_max:"Pardoseală răcire maxim (°C)",
    zoneSensors:"Senzori și actuator", zoneTiming:"Temporizări valvă", zoneFloor:"Limite pardoseală", zoneFloorHelp:"Opțional, 10–40 °C. Încălzirea se oprește la maximul de încălzire, răcirea la minimul de răcire.",
    rhHelp:"Cu senzor de umiditate configurat, zona nu răcește cât timp senzorul e indisponibil. Fără senzor, zona răcește fără protecție la umiditate.",
    zoneOther:"ID-ul zonei, profilul termic și parametrii termici rămân în Settings → Devices & services → Virtual Climate.", zoneSuccess:"Zona a fost salvată. Instanța se reîncarcă.",
  },
};

// Human labels and explanations for stored settings; slugs stay the storage keys.
const FIELD_INFO = {
  global_co_mode_entity: {
    en:["Global mode helper", "Helper (input_select, select or legacy input_boolean) that sets the system mode: HEAT, COOL or OFF. OFF stops new cycles; running circuits still finish minimum run and post-run. Zones set to AUTO follow this mode."],
    ro:["Helper mod global", "Helper-ul (input_select, select sau input_boolean vechi) care stabilește modul sistemului: HEAT, COOL sau OFF. OFF oprește ciclurile noi; circuitul în funcțiune își termină timpul minim și post-funcționarea. Zonele pe AUTO urmează acest mod."]},
  circuit_control: {
    en:["Circuit control", "Who commands the shared circuit. direct: Virtual Climate switches the pump, sources and changeover itself. external: it only sends a heating demand to another controller (circuit_demand_entity); the direct pump, source and changeover fields must then be empty. External control is heating-only."],
    ro:["Control circuit", "Cine comandă circuitul comun. direct: Virtual Climate comută singur pompa, sursele și changeover-ul. external: trimite doar o cerere de încălzire către alt controler (circuit_demand_entity); câmpurile directe pentru pompă, surse și changeover trebuie să fie goale. Controlul extern este doar pentru încălzire."]},
  heating_source_entity: {
    en:["Heating source switch", "Direct profile: switch that requests heat from the boiler or heat pump. Started after the pump and its start delay, kept on at least the minimum run time. Without it (and without a cooling source) a configured pump runs alone and the source must work independently."],
    ro:["Comutator sursă încălzire", "Profil direct: comutatorul care cere căldură de la centrală sau pompa de căldură. Pornește după pompă și întârzierea de pornire și rămâne pornit cel puțin timpul minim de funcționare. Fără el (și fără sursă de răcire), o pompă configurată funcționează singură, iar sursa trebuie să lucreze independent."]},
  cooling_source_entity: {
    en:["Cooling source switch", "Direct profile: switch that requests cooling. Without a cooling source or changeover, cooling is not offered on a circuit that has a heating source."],
    ro:["Comutator sursă răcire", "Profil direct: comutatorul care cere răcire. Fără sursă de răcire sau changeover, răcirea nu este disponibilă pe un circuit care are sursă de încălzire."]},
  circulation_pump_entity: {
    en:["Circulation pump switch", "Direct profile: pump command. It starts only after a zone valve reports open and stops after the pump post-run, so water always has an open path."],
    ro:["Comutator pompă circulație", "Profil direct: comanda pompei. Pornește doar după ce o valvă de zonă raportează deschis și se oprește după post-funcționare, astfel încât apa are mereu un traseu deschis."]},
  changeover_entity: {
    en:["Changeover switch", "Direct profile: tells a shared source which mode to run. off = heating, on = cooling. Switched before the source starts."],
    ro:["Comutator changeover", "Profil direct: indică unei surse comune modul de lucru. off = încălzire, on = răcire. Se comută înainte de pornirea sursei."]},
  circuit_demand_entity: {
    en:["External circuit demand", "External profile: switch or input_boolean turned on when zones need heat. The external controller decides how to run pump and source."],
    ro:["Cerere circuit extern", "Profil extern: switch sau input_boolean pornit când zonele au nevoie de căldură. Controlerul extern decide cum funcționează pompa și sursa."]},
  circuit_state_entity: {
    en:["Reported circuit state", "External profile, optional: sensor showing what the external controller reports. Diagnostic only; it does not shorten any timer."],
    ro:["Stare raportată circuit", "Profil extern, opțional: senzor cu starea raportată de controlerul extern. Doar pentru diagnostic; nu scurtează nicio temporizare."]},
  external_start_delay_seconds: {
    en:["External demand delay (s)", "External profile: extra wait after zone valves open before demand is sent. Use it if the external controller must not start against closed valves."],
    ro:["Întârziere cerere externă (s)", "Profil extern: așteptare suplimentară după deschiderea valvelor, înainte de trimiterea cererii. Util dacă controlerul extern nu trebuie să pornească pe valve închise."]},
  external_post_run_seconds: {
    en:["Zone hold after demand stops (s)", "External profile: valid zones stay open this long after demand is withdrawn. Must be at least as long as the external controller's own pump post-run, otherwise the pump may run against closed valves."],
    ro:["Menținere zone după cerere (s)", "Profil extern: zonele valide rămân deschise atât timp după retragerea cererii. Trebuie să fie cel puțin cât post-funcționarea pompei controlerului extern, altfel pompa poate funcționa pe valve închise."]},
  pump_start_delay_seconds: {
    en:["Pump start delay (s)", "Direct profile: wait between a zone valve reporting open and starting the pump."],
    ro:["Întârziere pornire pompă (s)", "Profil direct: așteptarea dintre deschiderea raportată a unei valve și pornirea pompei."]},
  heating_source_start_delay_seconds: {
    en:["Heating source start delay (s)", "Direct profile: wait after the pump starts before requesting heat."],
    ro:["Întârziere pornire sursă încălzire (s)", "Profil direct: așteptarea după pornirea pompei, înainte de cererea de căldură."]},
  cooling_source_start_delay_seconds: {
    en:["Cooling source start delay (s)", "Direct profile: wait after the pump starts before requesting cooling."],
    ro:["Întârziere pornire sursă răcire (s)", "Profil direct: așteptarea după pornirea pompei, înainte de cererea de răcire."]},
  minimum_run_time_seconds: {
    en:["Minimum run time (s)", "Once a source request (direct) or external demand starts, it stays on at least this long, even if demand disappears, as long as a zone path remains open. Protects equipment from short cycling."],
    ro:["Timp minim de funcționare (s)", "Odată pornită cererea către sursă (direct) sau cererea externă, rămâne activă cel puțin atât, chiar dacă cererea dispare, cât timp există o zonă deschisă. Protejează echipamentul de porniri scurte."]},
  pump_post_run_seconds: {
    en:["Pump post-run (s)", "Direct profile: the pump keeps running this long after the source request stops, with zone valves held open, to remove residual heat or cold."],
    ro:["Post-funcționare pompă (s)", "Profil direct: pompa mai funcționează atât după oprirea cererii către sursă, cu valvele ținute deschise, pentru a evacua căldura sau frigul rămas."]},
  minimum_off_time_seconds: {
    en:["Minimum off time (s)", "After the source request or external demand stops, it cannot restart before this time has passed."],
    ro:["Timp minim oprit (s)", "După oprirea cererii către sursă sau a cererii externe, aceasta nu poate reporni înainte să treacă acest timp."]},
  target_supply_temperature_entity: {
    en:["Supply target output", "Writable number or input_number that receives the calculated supply temperature target. A local device regulates the actual water temperature. Required for weather compensation in the direct profile."],
    ro:["Ieșire țintă tur", "number sau input_number în care se scrie ținta calculată a temperaturii de tur. Temperatura reală a apei o reglează un dispozitiv local. Obligatorie pentru curba climatică în profilul direct."]},
  heating_supply_target: {
    en:["Constant heating target (°C)", "Supply target for constant heating. With weather compensation it is the fallback when outdoor data is invalid."],
    ro:["Țintă constantă încălzire (°C)", "Ținta de tur pentru încălzirea constantă. La curba climatică este valoarea de rezervă când datele exterioare sunt invalide."]},
  cooling_supply_target: {
    en:["Constant cooling target (°C)", "Supply target in cooling. Cooling uses a constant target only. Floor and dew-point protections still apply per zone."],
    ro:["Țintă constantă răcire (°C)", "Ținta de tur la răcire. Răcirea folosește doar țintă constantă. Protecțiile de pardoseală și punct de rouă se aplică în continuare pe fiecare zonă."]},
  packing_mode: {
    en:["Zone scheduling", "simultaneous: zone pulses start together at the beginning of each cycle. staggered: zones are ranked by demand and their pulses are offset, spreading load on the circuit; offsets may overlap to keep minimum on times."],
    ro:["Programarea zonelor", "simultaneous: impulsurile zonelor pornesc împreună la începutul fiecărui ciclu. staggered: zonele sunt ordonate după cerere și impulsurile lor sunt decalate, distribuind sarcina pe circuit; decalajele se pot suprapune pentru a respecta timpii minimi."]},
  t_cycle_seconds: {
    en:["Initial cycle length (s)", "Cycle length used at start-up, before the coordinator adapts it to demand within the minimum and maximum below. In each cycle a zone's valve is open for a share proportional to its demand."],
    ro:["Durată inițială ciclu (s)", "Durata ciclului la pornire, înainte ca coordonatorul să o adapteze la cerere între minimul și maximul de mai jos. În fiecare ciclu, valva unei zone stă deschisă o fracțiune proporțională cu cererea ei."]},
  t_cycle_min: {
    en:["Minimum cycle length (s)", "Shortest cycle the coordinator may choose. Shorter cycles react faster but switch valves and source more often. Must leave room for valve opening time and zone minimum on time."],
    ro:["Durată minimă ciclu (s)", "Cel mai scurt ciclu pe care îl poate alege coordonatorul. Ciclurile scurte reacționează mai repede, dar comută mai des valvele și sursa. Trebuie să încapă timpul de deschidere a valvei și timpul minim pornit al zonei."]},
  t_cycle_max: {
    en:["Maximum cycle length (s)", "Longest cycle the coordinator may choose. Longer cycles mean fewer starts but slower reaction to changing demand."],
    ro:["Durată maximă ciclu (s)", "Cel mai lung ciclu pe care îl poate alege coordonatorul. Ciclurile lungi înseamnă mai puține porniri, dar reacție mai lentă la schimbarea cererii."]},
  rh_alert: {
    en:["Humidity alert (%)", "Cooling only: from this humidity upwards the zone's cooling demand is reduced progressively, down to half at the fault threshold."],
    ro:["Alertă umiditate (%)", "Doar la răcire: de la această umiditate în sus, cererea de răcire a zonei se reduce treptat, până la jumătate la pragul de defect."]},
  rh_fault: {
    en:["Humidity fault (%)", "Cooling only: at or above this humidity the zone stops cooling to avoid condensation, and resumes once humidity is below it again."],
    ro:["Defect umiditate (%)", "Doar la răcire: la sau peste această umiditate zona oprește răcirea pentru a evita condensul și reia când umiditatea scade sub prag."]},
  dp_safety_margin_c: {
    en:["Dew-point safety margin (°C)", "Cooling only: when the floor (or, without a floor sensor, the room) temperature comes within this margin of the room dew point, cooling demand is reduced; at the dew point the zone stops. The dew point comes from room temperature and humidity."],
    ro:["Marjă siguranță punct de rouă (°C)", "Doar la răcire: când temperatura pardoselii (sau a camerei, fără senzor de pardoseală) se apropie de punctul de rouă la mai puțin decât această marjă, cererea de răcire se reduce; la punctul de rouă zona se oprește. Punctul de rouă se calculează din temperatura și umiditatea camerei."]},
  instance_temperature_fallback: {
    en:["Heat zones with missing sensors", "Opt-in. A zone whose room sensor is unavailable can keep heating using the median of the other zones' rooms, only while measured zones are requesting heat. Temporary measure while a sensor is repaired; never used for cooling."],
    ro:["Încălzire zone fără senzor", "Opțional. O zonă cu senzorul de cameră indisponibil poate încălzi folosind mediana celorlalte camere, doar cât timp zonele măsurate cer căldură. Soluție temporară până se repară senzorul; nu se folosește la răcire."]},
  heating_control_strategy: {
    en:["Zone heating strategy", "How zone heating demand becomes valve pulses. legacy: proportional scheduling (default). observe: computes proposals and learns without changing commands. adaptive: experimental thermal-memory control. Independent of the supply-temperature strategy; cooling is unaffected."],
    ro:["Strategie încălzire zone", "Cum se transformă cererea de căldură a zonelor în impulsuri de valvă. legacy: programare proporțională (implicit). observe: calculează propuneri și învață fără a schimba comenzile. adaptive: control experimental cu memorie termică. Independent de strategia temperaturii de tur; răcirea nu este afectată."]},
  thermal_parameters: {
    en:["Thermal parameters", "Advanced model assumptions used by observe and adaptive strategies (delays, gains, comfort limits). Zone values override instance values. Not measured equipment data."],
    ro:["Parametri termici", "Ipoteze avansate de model folosite de strategiile observe și adaptive (întârzieri, câștiguri, limite de confort). Valorile zonei le suprascriu pe cele ale instanței. Nu sunt date măsurate ale echipamentului."]},
  heating_strategy: {
    en:["Heating supply strategy", "constant: fixed heating target. weather_compensated: target follows the outdoor curve; needs an outdoor sensor and, in the direct profile, a target output."],
    ro:["Strategie tur încălzire", "constant: țintă fixă. weather_compensated: ținta urmează curba climatică; necesită senzor exterior și, în profilul direct, o ieșire pentru țintă."]},
  cooling_strategy: {
    en:["Cooling supply strategy", "Cooling supports only a constant target."],
    ro:["Strategie tur răcire", "Răcirea acceptă doar țintă constantă."]},
  outdoor_sensor: {
    en:["Outdoor sensor", "Outdoor temperature used by weather compensation. If it becomes invalid, the constant heating target is used."],
    ro:["Senzor exterior", "Temperatura exterioară folosită de curba climatică. Dacă devine invalidă, se folosește ținta constantă de încălzire."]},
  supply_sensor: {
    en:["Supply sensor", "Optional measured supply water temperature. Enables supply deviation monitoring and supply verification in diagnostics."],
    ro:["Senzor tur", "Opțional, temperatura măsurată a apei pe tur. Permite monitorizarea abaterii turului și verificarea turului în diagnostic."]},
  return_sensor: {
    en:["Return sensor", "Optional return water temperature. Enables the supply-return difference alert."],
    ro:["Senzor retur", "Opțional, temperatura apei pe retur. Permite alerta pentru diferența tur-retur."]},
  outdoor_min: {
    en:["Curve outdoor minimum (°C)", "Coldest end of the curve interval. Outside the interval the end segment is extrapolated and learning pauses. Changing it resets all curve learning."],
    ro:["Exterior minim curbă (°C)", "Capătul rece al intervalului curbei. În afara intervalului se extrapolează ultimul segment și învățarea se oprește. Modificarea resetează toată învățarea curbei."]},
  outdoor_max: {
    en:["Curve outdoor maximum (°C)", "Warmest end of the curve interval. Changing it resets all curve learning."],
    ro:["Exterior maxim curbă (°C)", "Capătul cald al intervalului curbei. Modificarea resetează toată învățarea curbei."]},
  supply_points: {
    en:["Curve supply points (°C)", "2–50 supply temperatures evenly spaced across the outdoor interval, coldest first. They must not rise as outdoor temperature rises. Changing a point resets its learning."],
    ro:["Puncte tur curbă (°C)", "2–50 temperaturi de tur distribuite egal pe intervalul exterior, de la rece spre cald. Nu pot crește odată cu temperatura exterioară. Modificarea unui punct îi resetează învățarea."]},
  heating_min: {en:["Minimum heating supply (°C)", "Lower limit for any heating target, including learning and boost."], ro:["Tur minim încălzire (°C)", "Limita inferioară pentru orice țintă de încălzire, inclusiv învățare și boost."]},
  heating_max: {en:["Maximum heating supply (°C)", "Upper limit for any heating target, including learning and boost. Set it to what the floor or emitters tolerate."], ro:["Tur maxim încălzire (°C)", "Limita superioară pentru orice țintă de încălzire, inclusiv învățare și boost. Setează valoarea suportată de pardoseală sau corpuri."]},
  cooling_min: {en:["Minimum cooling supply (°C)", "Lower limit for the cooling target. Keep it above the risk of condensation."], ro:["Tur minim răcire (°C)", "Limita inferioară pentru ținta de răcire. Păstreaz-o peste riscul de condens."]},
  cooling_max: {en:["Maximum cooling supply (°C)", "Upper limit for the cooling target."], ro:["Tur maxim răcire (°C)", "Limita superioară pentru ținta de răcire."]},
  learning_mode: {
    en:["Curve learning", "off: base curve only. learn: tests small corrections per curve point and keeps those that improve comfort. frozen: applies already validated corrections without new trials. Requires a circuit whose requests Virtual Climate controls."],
    ro:["Învățarea curbei", "off: doar curba de bază. learn: testează corecții mici pe fiecare punct și le păstrează pe cele care îmbunătățesc confortul. frozen: aplică doar corecțiile deja validate, fără probe noi. Necesită un circuit ale cărui cereri sunt controlate de Virtual Climate."]},
  boost_enabled: {
    en:["Recovery boost", "Weather compensation only: temporarily raises the target when rooms lag behind, within boost limits and supply limits."],
    ro:["Boost de recuperare", "Doar la curba climatică: ridică temporar ținta când camerele rămân în urmă, în limitele de boost și de tur."]},
  sample_seconds: {en:["Observation interval (s)", "How often learning and monitoring sample data; at least 60."], ro:["Interval observare (s)", "Cât de des eșantionează învățarea și monitorizarea; minimum 60."]},
  max_gap_seconds: {en:["Maximum data gap (s)", "A gap longer than this invalidates the current observation or trial."], ro:["Pauză maximă date (s)", "O pauză mai lungă invalidează observația sau proba curentă."]},
  sensor_max_age_seconds: {en:["Maximum sensor report age (s)", "Sensor values older than this are treated as invalid. 0 disables the check."], ro:["Vechime maximă senzor (s)", "Valorile mai vechi sunt tratate ca invalide. 0 dezactivează verificarea."]},
  trend_seconds: {en:["Trend window (s)", "Window for room temperature trends; needs at least 90% data coverage."], ro:["Fereastră tendință (s)", "Fereastra pentru tendința temperaturii; necesită acoperire de cel puțin 90%."]},
  minimum_active_fraction: {en:["Minimum activity fraction", "Minimum share of time zones must be active for an observation to count."], ro:["Fracție minimă de activitate", "Fracțiunea minimă de timp activ al zonelor pentru ca o observație să conteze."]},
  learning_seconds: {en:["Observation before a trial (s)", "Valid time accumulated before a learning trial may start."], ro:["Observare înainte de probă (s)", "Timp valid acumulat înainte de a porni o probă de învățare."]},
  probe_seconds: {en:["Trial duration (s)", "Valid time accumulated during a learning trial before it is judged."], ro:["Durată probă (s)", "Timp valid acumulat în timpul unei probe înainte de evaluare."]},
  learning_step: {en:["Trial step (°C)", "Maximum change tested in one learning trial."], ro:["Pas probă (°C)", "Modificarea maximă testată într-o probă de învățare."]},
  correction_limit: {en:["Correction limit (°C)", "Maximum learned correction for any curve point."], ro:["Limită corecție (°C)", "Corecția maximă învățată pentru un punct al curbei."]},
  comfort_tolerance: {en:["Comfort tolerance (°C)", "Room deficit tolerated before learning or boost considers comfort degraded."], ro:["Toleranță confort (°C)", "Deficitul de temperatură tolerat înainte ca învățarea sau boostul să considere confortul degradat."]},
  comfort_persistence_seconds: {en:["Comfort degradation time (s)", "Persistent degradation for this long rejects a trial early."], ro:["Durată degradare confort (s)", "O degradare persistentă atât timp respinge proba mai devreme."]},
  minimum_learning_improvement: {en:["Minimum learning improvement (°C)", "Mean improvement required to keep an upward trial."], ro:["Îmbunătățire minimă învățare (°C)", "Îmbunătățirea medie necesară pentru a păstra o probă în sus."]},
  probe_outdoor_tolerance: {en:["Trial outdoor tolerance (°C)", "Outdoor change that interrupts a running trial."], ro:["Toleranță exterior probă (°C)", "Variația exterioară care întrerupe o probă în curs."]},
  boost_deficit: {en:["Boost threshold (°C)", "Room deficit above which recovery boost may start."], ro:["Prag boost (°C)", "Deficitul peste care poate porni boostul de recuperare."]},
  boost_gain: {en:["Boost gain", "Boost per degree of deficit, reduced while rooms recover."], ro:["Câștig boost", "Boost per grad de deficit, redus cât timp camerele își revin."]},
  boost_max: {en:["Maximum boost (°C)", "Largest boost, still within supply limits."], ro:["Boost maxim (°C)", "Boostul maxim, tot în limitele turului."]},
  boost_rate_per_hour: {en:["Boost rate (°C/h)", "Maximum change of the boost per hour."], ro:["Rată boost (°C/h)", "Variația maximă a boostului pe oră."]},
  minimum_recovery_rate: {en:["Reference recovery rate (°C/h)", "Room warming rate considered adequate recovery."], ro:["Rată de recuperare de referință (°C/h)", "Ritmul de încălzire a camerei considerat recuperare adecvată."]},
  fault_seconds: {en:["Insufficient response window (s)", "Persistent poor room response for this long is reported as a fault."], ro:["Fereastră răspuns insuficient (s)", "Un răspuns slab persistent atât timp este raportat ca defect."]},
  recovery_seconds: {en:["Recovery period (s)", "Acceptable response needed for this long to clear the fault."], ro:["Perioadă recuperare (s)", "Răspuns acceptabil necesar atât timp pentru a anula defectul."]},
  supply_tolerance: {en:["Supply deviation alert (°C)", "Persistent mean difference between target and measured supply that raises an alert. Needs a supply sensor."], ro:["Alertă abatere tur (°C)", "Diferența medie persistentă între țintă și turul măsurat care generează alertă. Necesită senzor de tur."]},
  delta_t_alert: {en:["Supply-return difference alert (°C)", "Persistent mean supply-return difference that raises an alert. Needs supply and return sensors."], ro:["Alertă diferență tur-retur (°C)", "Diferența medie persistentă tur-retur care generează alertă. Necesită senzori de tur și retur."]},
  write_interval_seconds: {en:["Minimum write interval (s)", "Minimum time between writes or retries to the target output."], ro:["Interval minim scriere (s)", "Timpul minim între scrieri sau reîncercări către ieșirea țintă."]},
  write_delta: {en:["Minimum write change (°C)", "Smaller target changes are not written, to avoid flooding the device."], ro:["Variație minimă scriere (°C)", "Schimbările mai mici nu se scriu, pentru a nu încărca dispozitivul."]},
  write_refresh_seconds: {en:["Target refresh (s)", "An unchanged target is re-written this often."], ro:["Reîmprospătare țintă (s)", "O țintă neschimbată se rescrie la acest interval."]},
  id: {en:["Zone ID", "Permanent identifier used in entity IDs, actions and import. Cannot be changed here."], ro:["ID zonă", "Identificator permanent folosit în ID-urile entităților, acțiuni și import. Nu se poate schimba aici."]},
  name: {en:["Zone name", "Display name of the zone and its thermostat."], ro:["Nume zonă", "Numele afișat al zonei și al termostatului ei."]},
  support_mode: {en:["Supported modes", "Modes this zone takes part in: HEAT, COOL or BOTH. A zone outside the active global mode stays closed."], ro:["Moduri permise", "Modurile în care participă zona: HEAT, COOL sau BOTH. O zonă care nu suportă modul global activ rămâne închisă."]},
  temperature_filter_enabled: {en:["Smooth room temperature", "Averages the room reading over about 3 minutes to ignore sensor noise. Floor and dew-point checks use raw values."], ro:["Netezire temperatură cameră", "Mediază citirea camerei pe circa 3 minute pentru a ignora zgomotul senzorului. Verificările de pardoseală și punct de rouă folosesc valorile brute."]},
  sensor_air: {en:["Room temperature sensor", "Main input for zone demand. If unavailable, the zone stops unless the missing-sensor heating fallback is enabled."], ro:["Senzor temperatură cameră", "Intrarea principală pentru cererea zonei. Dacă e indisponibil, zona se oprește, cu excepția cazului în care încălzirea fără senzor este activată."]},
  sensor_rh: {en:["Humidity sensor", "Used in cooling for humidity thresholds and dew point. If configured and unavailable, the zone stops cooling. Not used in heating."], ro:["Senzor umiditate", "Folosit la răcire pentru pragurile de umiditate și punctul de rouă. Dacă e configurat și indisponibil, zona oprește răcirea. Nu se folosește la încălzire."]},
  sensor_floor: {en:["Floor temperature sensor", "Optional. Required for floor limits; in cooling it is the surface compared with the dew point."], ro:["Senzor temperatură pardoseală", "Opțional. Necesar pentru limitele de pardoseală; la răcire este suprafața comparată cu punctul de rouă."]},
  switch_actuator: {en:["Valve / actuator switch", "Switch or group that opens the zone valve. Its reported state drives pump start and timing; it does not confirm real water flow."], ro:["Comutator valvă / actuator", "Comutatorul sau grupul care deschide valva zonei. Starea raportată condiționează pornirea pompei și temporizările; nu confirmă debitul real."]},
  window_switch: {en:["Window contact", "Optional. While open, the zone stops heating or cooling."], ro:["Contact fereastră", "Opțional. Cât timp e deschis, zona nu încălzește și nu răcește."]},
  open_s: {en:["Valve opening time (s)", "Time the actuator needs to open fully; the circuit waits for it before starting."], ro:["Timp deschidere valvă (s)", "Timpul necesar actuatorului ca să se deschidă complet; circuitul îl așteaptă înainte de pornire."]},
  close_s: {en:["Valve closing time (s)", "Time the actuator needs to close fully; included in zone timing."], ro:["Timp închidere valvă (s)", "Timpul necesar actuatorului ca să se închidă complet; inclus în temporizările zonei."]},
  zone_min_on_s: {en:["Zone minimum on time (s)", "Shortest useful valve pulse. Smaller demand is deferred rather than sent as a too-short pulse."], ro:["Timp minim pornit zonă (s)", "Cel mai scurt impuls util al valvei. O cerere mai mică este amânată, nu trimisă ca impuls prea scurt."]},
  zone_min_off_s: {en:["Zone minimum off time (s)", "Minimum rest between two valve pulses of the zone."], ro:["Timp minim oprit zonă (s)", "Pauza minimă între două impulsuri ale valvei zonei."]},
  floor_limits: {en:["Floor limits (°C)", "heat_max stops heating and cool_min stops cooling when reached. heat_min and cool_max are diagnostic only. Requires a floor sensor; never replaces the room setpoint."], ro:["Limite pardoseală (°C)", "heat_max oprește încălzirea, iar cool_min oprește răcirea când sunt atinse. heat_min și cool_max sunt doar pentru diagnostic. Necesită senzor de pardoseală; nu înlocuiește temperatura dorită a camerei."]},
  thermal_profile: {en:["Thermal profile", "underfloor or radiator: default thermal model assumptions for observe and adaptive strategies."], ro:["Profil termic", "underfloor sau radiator: ipotezele implicite ale modelului termic pentru strategiile observe și adaptive."]},
};
const VALUE_LABELS = {
  en:{simultaneous:"Simultaneous", staggered:"Staggered", legacy:"Legacy (proportional)", observe:"Observe only", adaptive:"Adaptive", underfloor:"Underfloor", radiator:"Radiator", learn:"Learn and apply", frozen:"Validated corrections only", off:"Off", constant:"Constant", weather_compensated:"Weather compensation", direct:"Direct", external:"External", HEAT:"Heating only", COOL:"Cooling only", BOTH:"Heating and cooling"},
  ro:{simultaneous:"Simultan", staggered:"Decalat", legacy:"Clasic (proporțional)", observe:"Doar observare", adaptive:"Adaptiv", underfloor:"Pardoseală", radiator:"Radiator", learn:"Învață și aplică", frozen:"Doar corecții validate", off:"Oprit", constant:"Constant", weather_compensated:"Curbă climatică", direct:"Direct", external:"Extern", HEAT:"Doar încălzire", COOL:"Doar răcire", BOTH:"Încălzire și răcire"},
};

class VirtualClimatePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._entries = [];
    this._page = "operation";
    this._busy = false;
    this._onPop = () => this._readRoute();
    this._onUnload = (event) => { if (this._dirty()) { event.preventDefault(); event.returnValue = ""; } };
  }
  t(key) { return TEXT[this._lang()][key] || key; }
  set hass(value) {
    const languageChanged = this._hass && this._hass.language !== value.language;
    this._hass = value;
    if (!this._started && this.isConnected) this._start();
    else if (languageChanged) this._render();
    else this._updateLive();
  }
  set route(value) { this._route = value; if (this._started) this._readRoute(); }
  set narrow(value) { this.toggleAttribute("narrow", value); }
  connectedCallback() {
    window.addEventListener("popstate", this._onPop);
    window.addEventListener("beforeunload", this._onUnload);
    if (this._hass && !this._started) this._start();
  }
  disconnectedCallback() {
    window.removeEventListener("popstate", this._onPop);
    window.removeEventListener("beforeunload", this._onUnload);
    clearInterval(this._timer);
    this._started = false;
  }
  async _start() {
    this._started = true;
    this._render();
    try {
      this._entries = await this._api("entries");
      this._loadedEntries = true;
      this._readRoute(true);
    } catch (error) { this._error = this._errorText(error); this._render(); }
    this._timer = setInterval(() => this._refreshEntries(), 15000);
  }
  async _refreshEntries() {
    try {
      this._entries = await this._api("entries");
      if (!this._entries.some((entry) => entry.entry_id === this._entryId)) this._readRoute(true);
      const editing = () => ["settings", "zones"].includes(this._page);
      if (this._entryId && !editing() && this._hass.user?.is_admin) {
        const id = this._entryId;
        const snapshot = await this._api("settings", {entry_id:id});
        if (id === this._entryId && !editing() && snapshot.revision !== this._snapshot?.revision) {
          await this._loadSnapshots(id);
          this._render();
        }
      }
      this._updateLive();
    } catch { /* The HA connection indicator handles temporary disconnects. */ }
  }
  _api(command, data = {}) { return this._hass.callWS({type:`virtual_climate/panel/${command}`, ...data}); }
  _dirty() {
    const supply = !!this._snapshot && JSON.stringify(this._draft) !== JSON.stringify(this._snapshot.settings);
    return supply || (!!this._zoneDraft && JSON.stringify(this._zoneDraft) !== JSON.stringify(this._savedZone()?.settings));
  }
  _savedZone() { return this._config?.zones.find((zone) => zone.id === this._zoneId); }
  _selectZone(id) {
    this._zoneId = id;
    this._zoneDraft = this._savedZone() ? clone(this._savedZone().settings) : null;
    this._review = null;
  }
  async _loadSnapshots(id) {
    const sequence = this._sequence;
    const [snapshot, config] = await Promise.all([this._api("settings", {entry_id:id}), this._api("config", {entry_id:id})]);
    if (sequence !== this._sequence || id !== this._entryId) return false;
    this._snapshot = snapshot;
    this._draft = clone(snapshot.settings);
    this._config = config;
    this._selectZone(config.zones.some((zone) => zone.id === this._zoneId) ? this._zoneId : config.zones[0]?.id);
    return true;
  }
  _entry() { return this._entries.find((entry) => entry.entry_id === this._entryId); }
  _entity(key) { return this._entry()?.entities.find((entity) => entity.key === key)?.entity_id; }
  _state(key) { return this._hass.states[this._entity(key)]; }
  _value(key) {
    const state = this._state(key);
    if (!state || ["unknown", "unavailable"].includes(state.state)) return this.t("unavailable");
    return `${this.t(state.state)}${state.attributes.unit_of_measurement ? " " + state.attributes.unit_of_measurement : ""}`;
  }
  _navigate(entryId, page) {
    if (this._busy || (this._dirty() && !window.confirm(this.t("leave")))) return;
    const path = `/virtual-climate/${encodeURIComponent(entryId)}/${page}`;
    history.pushState(null, "", path);
    this._switch(entryId, page);
    window.dispatchEvent(new CustomEvent("location-changed", {detail:{replace:false}}));
  }
  _readRoute(force = false) {
    const parts = (this._route?.path || location.pathname.replace(/^\/virtual-climate/, "")).split("/").filter(Boolean);
    const id = this._entries.some((entry) => entry.entry_id === parts[0]) ? parts[0] : this._entries[0]?.entry_id;
    const page = ["operation", "diagnostics", "settings", "zones"].includes(parts[1]) ? parts[1] : "operation";
    if (force || id !== this._entryId || page !== this._page) {
      if (this._dirty() && !window.confirm(this.t("leave"))) {
        history.replaceState(null, "", `/virtual-climate/${this._entryId}/${this._page}`);
        return;
      }
      this._switch(id, page);
    }
  }
  async _switch(id, page) {
    const sequence = this._sequence = (this._sequence || 0) + 1;
    this._entryId = id;
    this._page = page;
    this._snapshot = this._draft = this._review = this._config = this._zoneDraft = null;
    this._error = this._notice = "";
    this._render();
    if (id && this._hass.user?.is_admin) {
      try {
        if (!await this._loadSnapshots(id)) return;
      } catch (error) { if (sequence === this._sequence) this._error = this._errorText(error); }
      if (sequence === this._sequence) this._render();
    }
  }
  _errorText(error) { return error.code === "conflict" ? this.t("conflict") : error.message || this.t("failed"); }
  _metric(key, label) { return `<div class="metric"><span>${this.t(label)}</span><strong data-live="${key}">${escapeHTML(this._value(key))}</strong></div>`; }
  _render() {
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>
      <header><button class="menu" aria-label="${this.t("menu")}">☰</button><b>Virtual Climate</b>
      ${this._entries.length > 1 ? `<label class="instance">${this.t("instance")}<select id="instance" ${this._busy ? "disabled" : ""}>${this._entries.map((entry, index) => `<option value="${entry.entry_id}" ${entry.entry_id === this._entryId ? "selected" : ""}>${escapeHTML(entry.title)} · ${index + 1}</option>`).join("")}</select></label>` : `<span class="instance">${escapeHTML(this._entry()?.title || "")}</span>`}</header>
      <nav aria-label="Virtual Climate">${["operation", "diagnostics", ...(this._hass?.user?.is_admin ? ["settings", "zones"] : [])].map((page) => `<button data-page="${page}" class="${this._page === page ? "active" : ""} ${page === "settings" ? "settings-tab" : ""}" aria-current="${this._page === page ? "page" : "false"}">${["settings", "zones"].includes(page) ? "⚙ " : ""}${this.t(page === "zones" ? "zonesTab" : page)}</button>`).join("")}</nav>
      <main>${this._error ? `<div role="alert" class="alert error">${escapeHTML(this._error)} <button id="retry">${this.t("reload")}</button></div>` : ""}
      ${this._notice ? `<div role="status" class="alert success">${escapeHTML(this._notice)}</div>` : ""}
      ${!this._entries.length ? `<p>${this.t(this._error || this._loadedEntries ? "noEntries" : "loading")}</p>` : !this._entryId ? "" : this._page === "zones" ? this._zonesView() : this._page === "settings" ? this._settingsView() : this._page === "diagnostics" ? this._diagnosticsView() : this._operationView()}</main>`;
    this.shadowRoot.querySelector(".menu").onclick = () => this.dispatchEvent(new CustomEvent("hass-toggle-menu", {bubbles:true, composed:true}));
    this.shadowRoot.querySelectorAll("[data-page]").forEach((button) => button.onclick = () => this._navigate(this._entryId, button.dataset.page));
    const picker = this.shadowRoot.querySelector("#instance");
    if (picker) picker.onchange = () => { this._navigate(picker.value, this._page); picker.value = this._entryId; };
    this.shadowRoot.querySelector("#retry")?.addEventListener("click", () => {
      if (!this._dirty() || window.confirm(this.t("leave"))) this._switch(this._entryId, this._page);
    });
    this._bindSettings();
    this._bindZone();
    this._bindControls();
    this._updateLive();
  }
  _operationView() {
    const climates = this._entry().entities.filter((entity) => entity.entity_id.startsWith("climate."));
    return `<div class="page-heading"><div><p class="eyebrow">${this.t("operation")}</p><h1>${this.t("intro")}</h1><p>${this.t("opHelp")}</p></div></div>
      <section class="card"><h2>${this.t("circuit")}</h2><div class="metrics">${this._metric("plant_state", "state")}${this._metric("supply_target", "target")}${this._metric("supply_actual", "actual")}${this._metric("supply_outdoor", "outdoor")}${this._metric("supply_strategy", "strategy")}</div></section>
      <h2 class="section-title">${this.t("zones")}</h2><div class="zone-grid">${climates.map((entity) => {
        const state = this._hass.states[entity.entity_id];
        return `<section class="card zone"><h3>${escapeHTML(state?.attributes.friendly_name || entity.entity_id)}</h3>
          <div class="room-reading"><strong data-current="${entity.entity_id}"></strong><span>${this.t("current")}</span></div>
          <label>${this.t("temperature")}<input type="number" data-setpoint="${entity.entity_id}" step="${state?.attributes.target_temp_step || 0.5}" min="${state?.attributes.min_temp ?? 5}" max="${state?.attributes.max_temp ?? 35}" value="${state?.attributes.temperature ?? ""}"></label>
          <label>${this.t("mode")}<select data-mode="${entity.entity_id}"><option value="auto" ${state?.state === "auto" ? "selected" : ""}>${this.t("auto")}</option><option value="off" ${state?.state === "off" ? "selected" : ""}>${this.t("off")}</option></select></label>
          <p class="zone-status" data-zone-status="${entity.entity_id}"></p></section>`;
      }).join("")}</div><p class="footnote">${this.t("feedback")}</p>`;
  }
  _diagnosticsView() {
    return `<div class="page-heading"><div><p class="eyebrow">${this.t("diagnostics")}</p><h1>${this.t("diagnosticTitle")}</h1><p>${this.t("diagnosticHelp")}</p></div></div>
      <section class="card"><h2>${this.t("applied")}</h2><p>${this.t("appliedHelp")}</p>${this._snapshot ? `<div class="metrics"><div class="metric"><span>${this.t("strategy")}</span><strong>${this.t(this._snapshot.settings.heating_strategy)}</strong></div><div class="metric"><span>${this.t("heating_supply_target")}</span><strong>${this._snapshot.settings.heating_supply_target} °C</strong></div></div>${this._graph(this._snapshot.settings)}` : `<p>${this.t(this._hass.user?.is_admin ? "loading" : "adminOnly")}</p>`}</section>
      <section class="card"><h2>${this.t("contributions")}</h2><div class="metrics">${["supply_curve_target", "supply_learned_correction", "supply_probe_adjustment", "supply_boost"].map((key) => this._metric(key, key)).join("")}${this._metric("supply_target", "target")}${this._metric("supply_actual", "actual")}</div></section>
      <section class="card"><div class="metrics">${["supply_learning_status", "plant_state", "coordinator_phase"].map((key) => this._metric(key, key)).join("")}</div></section>
      ${this._hass.user?.is_admin ? this._savedConfigView() : ""}<p class="footnote">${this.t("feedback")}</p>`;
  }
  _format(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "boolean") return value ? "✓" : "—";
    if (Array.isArray(value)) return value.map((item) => this._format(item)).join(", ");
    if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${this._format(item)}`).join(" · ");
    return VALUE_LABELS[this._lang()][value] ?? String(value);
  }
  _lang() { return this._hass?.language?.startsWith("ro") ? "ro" : "en"; }
  _label(scope, key) {
    const info = FIELD_INFO[key]?.[this._lang()];
    if (!info) return `<code>${escapeHTML(key)}</code>`;
    const id = `info-${scope}-${key}`.replace(/[^a-zA-Z0-9_-]/g, "_");
    return `<span class="field-label">${escapeHTML(info[0])}<button type="button" class="info" popovertarget="${id}" aria-label="${escapeHTML(this.t("moreInfo"))}: ${escapeHTML(info[0])}">i</button></span>
      <div popover id="${id}" class="info-pop"><strong>${escapeHTML(info[0])}</strong><p>${escapeHTML(info[1])}</p><code>${escapeHTML(key)}</code></div>`;
  }
  _rows(object, scope = "global") {
    return Object.entries(object).filter(([, value]) => value !== null && value !== undefined && value !== "")
      .map(([key, value]) => `<tr><td>${this._label(scope, key)}</td><td>${escapeHTML(this._format(value))}</td></tr>`).join("");
  }
  _savedConfigView() {
    if (!this._config) return `<section class="card"><h2>${this.t("savedConfig")}</h2><p>${this.t("loading")}</p></section>`;
    const {supply_control: supply, ...global} = this._config.config.global;
    const head = `<thead><tr><th>${this.t("setting")}</th><th>${this.t("value")}</th></tr></thead>`;
    return `<section class="card"><h2>${this.t("savedConfig")}</h2><p>${this.t("savedConfigHelp")}</p>
      <details open><summary>${this.t("globalSettings")}</summary><div class="table-scroll"><table>${head}<tbody>${this._rows(global)}</tbody></table></div></details>
      <details><summary>${this.t("supply")}</summary><div class="table-scroll"><table>${head}<tbody>${this._rows(supply || {}, "supply")}</tbody></table></div></details>
      ${this._config.config.zones.map((zone) => `<details><summary>${this.t("zone")}: ${escapeHTML(zone.name || zone.id)}</summary><div class="table-scroll"><table>${head}<tbody>${this._rows(zone, zone.id)}</tbody></table></div></details>`).join("")}</section>`;
  }
  _number(key, min, max, step = "any") {
    return `<label>${this.t(key)}<input name="${key}" type="number" min="${min}" max="${max}" step="${step}" required value="${escapeHTML(this._draft[key])}"></label>`;
  }
  _select(key, choices) {
    return `<label>${this.t(key)}<select name="${key}">${choices.map((value) => `<option value="${value}" ${this._draft[key] === value ? "selected" : ""}>${this.t(value)}</option>`).join("")}</select></label>`;
  }
  _entityInput(key, domains) {
    const options = Object.values(this._hass.states).filter((state) => domains.includes(state.entity_id.split(".")[0]));
    return `<label>${this.t(key)}<input type="text" name="${key}" list="entities-${key}" value="${escapeHTML(this._draft[key])}" placeholder="${domains.join(" / ")}"><datalist id="entities-${key}">${options.map((state) => `<option value="${escapeHTML(state.entity_id)}">${escapeHTML(state.attributes.friendly_name)}</option>`).join("")}</datalist></label>`;
  }
  _settingsView() {
    if (!this._hass.user?.is_admin) return `<p>${this.t("editOnly")}</p>`;
    if (!this._draft) return `<p>${this.t("loading")}</p>`;
    const weather = this._draft.heating_strategy === "weather_compensated";
    return `<div class="page-heading"><div><p class="eyebrow">${this.t("settings")} / ${this.t(this._snapshot.profile)}</p><h1>${this.t("supply")}</h1><p>${this.t("settingsHelp")}</p></div><span id="dirty" class="badge" ${!this._dirty() ? "hidden" : ""}>${this.t("unsaved")}</span></div>
      <form id="supply-form"><fieldset ${this._busy ? "disabled" : ""}><div class="settings-grid"><div>
      <section class="card"><h2>${this.t("heating")}</h2>${this._select("heating_strategy", ["constant", "weather_compensated"])}
      ${this._number("heating_supply_target", 10, 60)}<p class="hint">${this.t("fallbackHelp")}</p>
      <div class="fields">${this._number("heating_min", 0, 90)}${this._number("heating_max", 0, 90)}</div></section>
      <section class="card"><h2>${this.t("connections")}</h2>${this._entityInput("target_supply_temperature_entity", ["number", "input_number"])}
      ${weather ? this._entityInput("outdoor_sensor", ["sensor"]) + `<p class="hint">${this.t("requiredOutdoor")}</p>` : ""}
      <div class="fields">${this._entityInput("supply_sensor", ["sensor"])}${this._entityInput("return_sensor", ["sensor"])}</div></section>
      ${weather ? `<section class="card"><h2>${this.t("curve")}</h2><p>${this.t("curveHelp")}</p><div class="fields">${this._number("outdoor_min", -80, 59)}${this._number("outdoor_max", -79, 60)}</div>
      <label>${this.t("pointCount")}<input id="point-count" type="number" min="2" max="50" step="1" required value="${this._draft.supply_points.length}"></label>
      <div class="table-scroll"><table><thead><tr><th>${this.t("point")}</th><th>${this.t("outdoorTemperature")}</th><th>${this.t("supplyTemperature")}</th></tr></thead><tbody>${this._draft.supply_points.map((point, index) => `<tr><td>${index + 1}</td><td data-outdoor="${index}">${this._outdoorAt(index)}</td><td><input type="number" data-point="${index}" aria-label="${this.t("supplyTemperature")} ${index + 1}" min="0" max="90" step="any" required value="${escapeHTML(point)}"></td></tr>`).join("")}</tbody></table></div>
      ${this._select("learning_mode", ["off", "learn", "frozen"])}<label class="check"><input type="checkbox" name="boost_enabled" ${this._draft.boost_enabled ? "checked" : ""}>${this.t("boost_enabled")}</label></section>` : `<p class="hint">${this.t("inactiveHelp")}</p>`}
      ${this._snapshot.profile !== "external" ? `<section class="card"><h2>${this.t("cooling")}</h2><p>${this.t("coolingHelp")}</p>${this._number("cooling_supply_target", 5, 30)}<div class="fields">${this._number("cooling_min", 0, 90)}${this._number("cooling_max", 0, 90)}</div></section>` : ""}
      </div><aside><section class="card preview-card"><h2>${this.t("preview")}</h2><div id="curve-preview">${this._graph(this._draft, this._snapshot.settings)}</div><p class="hint">${this.t("previewHelp")}</p><div class="legend"><span class="saved-line"></span>${this.t("saved")}<span class="draft-line"></span>${this.t("draft")}</div></section></aside></div>
      <div class="actions"><button type="button" id="discard">${this.t("discard")}</button><button class="primary" type="submit">${this._busy ? this.t("loading") : this.t("review")}</button></div></fieldset></form>
      <div id="review">${this._reviewView()}</div><p class="footnote">${this.t("moreSettings")}</p>`;
  }
  _outdoorAt(index) {
    const d = this._draft;
    return (d.outdoor_min + index * (d.outdoor_max - d.outdoor_min) / (d.supply_points.length - 1)).toFixed(1);
  }
  _graph(draft, saved) {
    const curves = saved ? [saved, draft] : [draft];
    if (curves.some((d) => ![d.outdoor_min, d.outdoor_max, d.heating_supply_target, ...d.supply_points].every((v) => typeof v === "number" && Number.isFinite(v)) || d.outdoor_min >= d.outdoor_max)) return `<p>${this.t("invalidCurve")}</p>`;
    const xmin = Math.min(...curves.map((d) => d.outdoor_min));
    const xmax = Math.max(...curves.map((d) => d.outdoor_max));
    const ys = curves.flatMap((d) => d.heating_strategy === "constant" ? [d.heating_supply_target] : d.supply_points);
    const ymin = Math.floor((Math.min(...ys) - 3) / 5) * 5;
    const ymax = Math.max(ymin + 10, Math.ceil((Math.max(...ys) + 3) / 5) * 5);
    const x = (v) => 54 + 410 * (v - xmin) / (xmax - xmin);
    const y = (v) => 230 - 200 * (v - ymin) / (ymax - ymin);
    const path = (d) => {
      const points = d.heating_strategy === "constant" ? [d.heating_supply_target, d.heating_supply_target] : d.supply_points;
      return points.map((p, i) => `${i ? "L" : "M"}${x(d.outdoor_min + i * (d.outdoor_max - d.outdoor_min) / (points.length - 1))},${y(p)}`).join(" ");
    };
    return `<svg viewBox="0 0 500 280" role="img" aria-label="${this.t("curve")}"><title>${this.t("curve")}</title>
      ${Array.from({length:5}, (_, i) => { const value = ymin + i * (ymax - ymin) / 4; return `<line class="gridline" x1="54" x2="464" y1="${y(value)}" y2="${y(value)}"/><text x="44" y="${y(value) + 4}" text-anchor="end">${value.toFixed(0)}</text>`; }).join("")}
      ${Array.from({length:5}, (_, i) => { const value = xmin + i * (xmax - xmin) / 4; return `<text x="${x(value)}" y="250" text-anchor="middle">${value.toFixed(1)}</text>`; }).join("")}
      <text x="14" y="18">°C</text><text x="260" y="275" text-anchor="middle">${this.t("outdoorTemperature")}</text>
      ${saved ? `<path class="saved-curve" d="${path(saved)}"/>` : ""}<path class="draft-curve" d="${path(draft)}"/>
      ${draft.heating_strategy === "weather_compensated" ? draft.supply_points.map((p, i) => `<circle cx="${x(draft.outdoor_min + i * (draft.outdoor_max - draft.outdoor_min) / (draft.supply_points.length - 1))}" cy="${y(p)}" r="4"><title>${p} °C</title></circle>`).join("") : ""}</svg>`;
  }
  _reviewView() {
    if (!this._review) return "";
    const review = this._review;
    if (!review.changes.length) return `<section class="card" role="status">${this.t("noChanges")}</section>`;
    const format = (value) => escapeHTML(Array.isArray(value) ? value.join(", ") : typeof value === "boolean" ? value ? "✓" : "—" : value === null ? "—" : String(this.t(value)));
    return `<section class="card review-card"><h2>${this.t("reviewTitle")}</h2><div class="table-scroll"><table><thead><tr><th>${this.t("changed")}</th><th>${this.t("from")}</th><th>${this.t("to")}</th></tr></thead><tbody>${review.changes.map((change) => `<tr><td>${this.t(change.key === "supply_points" ? "curve" : change.key)}</td><td>${format(change.before)}</td><td>${format(change.after)}</td></tr>`).join("")}</tbody></table></div>
      <p class="alert">${this.t("reloadWarning")}</p><p ${this._page === "zones" ? "hidden" : ""}>${this.t(review.learning_reset === "all" ? "allReset" : review.learning_reset === "points" ? "pointsReset" : "noReset")} ${review.reset_points.join(", ")}</p>
      <button class="primary" id="apply" ${this._busy ? "disabled" : ""}>${this.t("apply")}</button></section>`;
  }
  _bindSettings() {
    const form = this.shadowRoot.querySelector("#supply-form");
    if (!form) return;
    form.querySelectorAll("[name], [data-point]").forEach((input) => input.addEventListener("input", () => {
      const value = input.type === "checkbox" ? input.checked : input.type === "number" ? input.value === "" ? null : Number(input.value) : input.value || null;
      if (input.hasAttribute("data-point")) this._draft.supply_points[Number(input.dataset.point)] = value;
      else this._draft[input.name] = value;
      this._review = null;
      this._notice = "";
      this.shadowRoot.querySelector("#review").innerHTML = "";
      this.shadowRoot.querySelector("#dirty").hidden = !this._dirty();
      this.shadowRoot.querySelector("#curve-preview").innerHTML = this._graph(this._draft, this._snapshot.settings);
      form.querySelectorAll("[data-outdoor]").forEach((cell) => cell.textContent = this._outdoorAt(Number(cell.dataset.outdoor)));
      if (input.name === "heating_strategy") this._render();
    }));
    const count = form.querySelector("#point-count");
    if (count) count.onchange = () => {
      const n = Number(count.value);
      if (!Number.isInteger(n) || n < 2 || n > 50) return;
      const previous = this._draft.supply_points;
      this._draft.supply_points = Array.from({length:n}, (_, index) => {
        const position = index * (previous.length - 1) / (n - 1);
        const left = Math.min(previous.length - 2, Math.floor(position));
        return Math.round((previous[left] + (position - left) * (previous[left + 1] - previous[left])) * 10) / 10;
      });
      this._review = null;
      this._render();
    };
    form.onsubmit = async (event) => { event.preventDefault(); await this._submit(false); };
    this.shadowRoot.querySelector("#discard").onclick = () => {
      this._draft = clone(this._snapshot.settings); this._review = null; this._error = this._notice = ""; this._render();
    };
    this.shadowRoot.querySelector("#apply")?.addEventListener("click", () => this._submit(true));
  }
  async _submit(save) {
    if (this._busy || (save && !this._review?.changes.length)) return;
    this._busy = true;
    this._error = this._notice = "";
    const id = this._entryId;
    const sequence = this._sequence;
    const payload = {entry_id:id, revision:this._snapshot.revision, changes:clone(this._draft)};
    this._render();
    try {
      const result = await this._api(save ? "save" : "validate", payload);
      if (sequence !== this._sequence) return;
      if (save) {
        await this._loadSnapshots(id);
        this._review = null;
        this._notice = this.t("success");
      } else this._review = result;
    } catch (error) { this._error = this._errorText(error); this._review = null; }
    finally { this._busy = false; this._render(); if (!save) this.shadowRoot.querySelector("#review")?.scrollIntoView({behavior:"smooth", block:"nearest"}); }
  }
  _zoneField(key, type, extra = "") {
    const value = this._zoneDraft[key];
    return `<label>${this.t(key)}<input data-zone-field="${key}" type="${type}" ${extra} value="${escapeHTML(value ?? "")}"></label>`;
  }
  _zoneEntity(key, domains, required = false) {
    const options = Object.values(this._hass.states).filter((state) => domains.includes(state.entity_id.split(".")[0]));
    return `<label>${this.t(key)}<input data-zone-field="${key}" type="text" list="zone-entities-${key}" ${required ? "required" : ""} placeholder="${domains.join(" / ")}" value="${escapeHTML(this._zoneDraft[key] ?? "")}"><datalist id="zone-entities-${key}">${options.map((state) => `<option value="${escapeHTML(state.entity_id)}">${escapeHTML(state.attributes.friendly_name)}</option>`).join("")}</datalist></label>`;
  }
  _zonesView() {
    if (!this._hass.user?.is_admin) return `<p>${this.t("editOnly")}</p>`;
    if (!this._config) return `<p>${this.t("loading")}</p>`;
    if (!this._zoneDraft) return `<p>${this.t("noChanges")}</p>`;
    const d = this._zoneDraft;
    const floor = (key) => this._zoneField(key, "number", `min="10" max="40" step="0.5"`);
    return `<div class="page-heading"><div><p class="eyebrow">${this.t("settings")}</p><h1>${this.t("zoneEditor")}</h1><p>${this.t("zoneHelp")}</p></div><span id="dirty" class="badge" ${!this._dirty() ? "hidden" : ""}>${this.t("unsaved")}</span></div>
      <label class="zone-picker">${this.t("zone")}<select id="zone-picker" ${this._busy ? "disabled" : ""}>${this._config.zones.map((zone) => `<option value="${escapeHTML(zone.id)}" ${zone.id === this._zoneId ? "selected" : ""}>${escapeHTML(zone.settings.name || zone.id)} (${escapeHTML(zone.id)})</option>`).join("")}</select></label>
      <form id="zone-form"><fieldset ${this._busy ? "disabled" : ""}><div class="settings-grid"><div>
      <section class="card"><h2>${this.t("zone")}</h2>${this._zoneField("name", "text", `required maxlength="64"`)}
      <label>${this.t("support_mode")}<select data-zone-field="support_mode">${["BOTH", "HEAT", "COOL"].map((mode) => `<option value="${mode}" ${d.support_mode === mode ? "selected" : ""}>${this.t(mode)}</option>`).join("")}</select></label>
      <label class="check"><input type="checkbox" data-zone-field="temperature_filter_enabled" ${d.temperature_filter_enabled ? "checked" : ""}>${this.t("temperature_filter_enabled")}</label></section>
      <section class="card"><h2>${this.t("zoneSensors")}</h2>${this._zoneEntity("sensor_air", ["sensor"], true)}${this._zoneEntity("switch_actuator", ["switch", "group"], true)}
      ${this._zoneEntity("sensor_rh", ["sensor"])}<p class="hint">${this.t("rhHelp")}</p>${this._zoneEntity("sensor_floor", ["sensor"])}${this._zoneEntity("window_switch", ["binary_sensor"])}</section>
      </div><div>
      <section class="card"><h2>${this.t("zoneTiming")}</h2><div class="fields">${this._zoneField("open_s", "number", `min="0" max="600" step="1" required`)}${this._zoneField("close_s", "number", `min="0" max="600" step="1" required`)}
      ${this._zoneField("zone_min_on_s", "number", `min="0" max="3600" step="1" required`)}${this._zoneField("zone_min_off_s", "number", `min="0" max="3600" step="1" required`)}</div></section>
      <section class="card"><h2>${this.t("zoneFloor")}</h2><p class="hint">${this.t("zoneFloorHelp")}</p><div class="fields">${floor("floor_heat_min")}${floor("floor_heat_max")}${floor("floor_cool_min")}${floor("floor_cool_max")}</div></section>
      </div></div>
      <div class="actions"><button type="button" id="zone-discard">${this.t("discard")}</button><button class="primary" type="submit">${this._busy ? this.t("loading") : this.t("review")}</button></div></fieldset></form>
      <div id="review">${this._reviewView()}</div><p class="footnote">${this.t("zoneOther")}</p>`;
  }
  _bindZone() {
    const picker = this.shadowRoot.querySelector("#zone-picker");
    if (picker) picker.onchange = () => {
      if (this._dirty() && !window.confirm(this.t("leave"))) { picker.value = this._zoneId; return; }
      this._selectZone(picker.value); this._error = this._notice = ""; this._render();
    };
    const form = this.shadowRoot.querySelector("#zone-form");
    if (!form) return;
    form.querySelectorAll("[data-zone-field]").forEach((input) => input.addEventListener("input", () => {
      const key = input.dataset.zoneField;
      this._zoneDraft[key] = input.type === "checkbox" ? input.checked : input.type === "number" ? input.value === "" ? null : Number(input.value) : input.value.trim() || null;
      this._review = null;
      this._notice = "";
      this.shadowRoot.querySelector("#review").innerHTML = "";
      this.shadowRoot.querySelector("#dirty").hidden = !this._dirty();
    }));
    form.onsubmit = async (event) => { event.preventDefault(); await this._submitZone(false); };
    this.shadowRoot.querySelector("#zone-discard").onclick = () => { this._selectZone(this._zoneId); this._error = this._notice = ""; this._render(); };
    this.shadowRoot.querySelector("#apply")?.addEventListener("click", () => this._submitZone(true));
  }
  async _submitZone(save) {
    if (this._busy || (save && !this._review?.changes.length)) return;
    this._busy = true;
    this._error = this._notice = "";
    const id = this._entryId, sequence = this._sequence;
    const payload = {entry_id:id, zone_id:this._zoneId, revision:this._config.revision, changes:clone(this._zoneDraft)};
    this._render();
    try {
      const result = await this._api(save ? "zone_save" : "zone_validate", payload);
      if (sequence !== this._sequence) return;
      if (save) {
        await this._loadSnapshots(id);
        this._review = null;
        this._notice = this.t("zoneSuccess");
      } else this._review = result;
    } catch (error) { this._error = this._errorText(error); this._review = null; }
    finally { this._busy = false; this._render(); if (!save) this.shadowRoot.querySelector("#review")?.scrollIntoView({behavior:"smooth", block:"nearest"}); }
  }
  _bindControls() {
    this.shadowRoot.querySelectorAll("[data-setpoint], [data-mode]").forEach((input) => input.onchange = async () => {
      const entity = input.dataset.setpoint || input.dataset.mode;
      input.disabled = true;
      try {
        await this._hass.callService("climate", input.dataset.setpoint ? "set_temperature" : "set_hvac_mode", {
          entity_id:entity, ...(input.dataset.setpoint ? {temperature:Number(input.value)} : {hvac_mode:input.value}),
        });
      } catch (error) { this._error = this._errorText(error); this._render(); }
      finally { input.disabled = false; }
    });
  }
  _updateLive() {
    if (!this._hass || !this.shadowRoot) return;
    this.shadowRoot.querySelectorAll("[data-live]").forEach((element) => element.textContent = this._value(element.dataset.live));
    this.shadowRoot.querySelectorAll("[data-current]").forEach((element) => {
      const state = this._hass.states[element.dataset.current];
      element.textContent = `${state?.attributes.current_temperature ?? "—"} ${state?.attributes.temperature_unit || this._hass.config.unit_system.temperature}`;
    });
    this.shadowRoot.querySelectorAll("[data-zone-status]").forEach((element) => {
      const state = this._hass.states[element.dataset.zoneStatus];
      element.textContent = state ? [state.attributes.hvac_action, state.attributes.coordinator_status, ...(state.attributes.coordinator_block_reasons || [])].filter(Boolean).join(" · ") : this.t("unavailable");
    });
    this.shadowRoot.querySelectorAll("[data-setpoint], [data-mode]").forEach((input) => {
      if (input === this.shadowRoot.activeElement || input.disabled) return;
      const state = this._hass.states[input.dataset.setpoint || input.dataset.mode];
      if (state) input.value = input.dataset.setpoint ? state.attributes.temperature ?? "" : state.state;
    });
  }
}

const STYLES = `
  :host{display:block;min-height:100%;background:var(--primary-background-color,#f5f6f8);color:var(--primary-text-color,#202b31);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);font-size:14px;--accent:var(--primary-color,#03a9f4)}
  *{box-sizing:border-box}header{height:72px;display:flex;align-items:center;gap:18px;padding:12px 32px;background:var(--card-background-color,#fff);border-bottom:1px solid var(--divider-color,#e5e7eb)}header b{font-size:20px}.instance{margin-left:auto;margin-bottom:0;display:flex;flex-direction:row;align-items:center;gap:12px;color:var(--secondary-text-color,#63717b)}.instance select{min-width:180px;margin:0}.menu{border:0;font-size:22px;padding:8px;background:none;color:inherit}
  nav{display:flex;gap:6px;padding:0 32px;background:var(--card-background-color,#fff);border-bottom:1px solid var(--divider-color,#e5e7eb)}nav button{border:0;border-radius:0;padding:20px 18px;background:none;color:var(--secondary-text-color,#63717b);border-bottom:3px solid transparent}nav button.active{color:var(--accent);border-bottom-color:var(--accent)}nav .settings-tab{margin-left:auto}
  main{max-width:1320px;margin:auto;padding:32px}.page-heading{display:flex;justify-content:space-between;align-items:center;margin:4px 0 26px;gap:16px}.eyebrow{text-transform:uppercase;letter-spacing:.09em;font-size:11px;font-weight:700;color:var(--accent);margin:0 0 8px}h1{font-size:28px;line-height:1.25;letter-spacing:-.6px;margin:0 0 10px;font-weight:600}h2{font-size:18px;margin:0 0 18px;font-weight:600}h3{font-size:16px;margin:0 0 20px}p{line-height:1.6;margin:8px 0 18px;color:var(--secondary-text-color,#63717b)}.card{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e5e7eb);border-radius:14px;padding:24px;margin-bottom:20px}.metrics{display:flex;flex-wrap:wrap;gap:24px 40px}.metric{display:flex;flex-direction:column;gap:10px;min-width:130px}.metric span{font-size:12px;color:var(--secondary-text-color,#63717b)}.metric strong{font-size:21px;font-weight:500}.zone-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}.zone{margin:0}.room-reading{display:flex;align-items:baseline;gap:12px;margin-bottom:24px}.room-reading strong{font-size:30px}.room-reading span{font-size:11px;color:var(--secondary-text-color,#63717b)}.section-title{margin:30px 0 18px}.zone-status{font-size:12px;margin:12px 0 0}.settings-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,1fr);gap:24px;align-items:start}aside{position:sticky;top:20px}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.fields label{min-width:0}label{display:flex;flex-direction:column;gap:8px;font-size:13px;font-weight:500;margin-bottom:18px}input,select{font:inherit;color:inherit;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#cbd1d6);border-radius:8px;padding:12px;min-width:0;width:100%;min-height:44px}input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}input:invalid{border-color:var(--error-color,#db4437)}.check{display:flex;flex-direction:row;align-items:center;gap:10px}.check input{width:18px;min-height:18px}fieldset{border:0;padding:0;margin:0;min-width:0}.hint,.footnote{font-size:12px;color:var(--secondary-text-color,#63717b)}.hint{margin:0 0 20px}.footnote{margin:24px 0}.badge{font-size:12px;background:var(--secondary-background-color,#eef2f5);padding:8px 12px;border-radius:30px;white-space:nowrap}[hidden]{display:none!important}button{font:inherit;font-weight:500;padding:12px 18px;border:1px solid var(--divider-color,#cbd1d6);border-radius:8px;cursor:pointer;background:var(--card-background-color,#fff);color:inherit;min-height:44px}button.primary{background:var(--accent);border-color:var(--accent);color:var(--text-primary-color,#fff)}button:disabled{opacity:.5;cursor:wait}.actions{display:flex;justify-content:flex-end;gap:12px;padding:8px 0 20px}.alert{padding:16px;border-radius:8px;background:var(--secondary-background-color,#eef2f5);line-height:1.6;margin-bottom:20px}.alert.error{border-left:4px solid var(--error-color,#db4437)}.alert.success{border-left:4px solid var(--success-color,#43a047)}.alert button{margin-left:12px}.review-card{border:2px solid var(--accent)}.table-scroll{overflow:auto;margin-bottom:20px}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}td,th{padding:10px 8px;border-bottom:1px solid var(--divider-color,#e5e7eb);max-width:260px;overflow-wrap:anywhere}th{color:var(--secondary-text-color,#63717b);font-weight:500}td input{max-width:120px}svg{display:block;width:100%;height:auto;overflow:visible}svg text{fill:var(--secondary-text-color,#63717b);font-size:11px}svg path{fill:none;stroke-width:3}.gridline{stroke:var(--divider-color,#e5e7eb)}.saved-curve{stroke:var(--secondary-text-color,#63717b);stroke-dasharray:6 5}.draft-curve{stroke:var(--accent)}svg circle{fill:var(--card-background-color,#fff);stroke:var(--accent);stroke-width:2}details{border-top:1px solid var(--divider-color,#e5e7eb);padding:12px 0}summary{cursor:pointer;font-weight:500;padding:4px 0}details table{margin-top:12px}code{font-size:12px}.zone-picker{max-width:420px}.legend{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--secondary-text-color,#63717b)}.saved-line,.draft-line{width:25px;border-top:3px solid var(--accent)}.saved-line{border-top:3px dashed var(--secondary-text-color,#63717b)}.draft-line{margin-left:18px}
  @media(max-width:850px){main{padding:20px}.settings-grid{grid-template-columns:1fr}aside{position:static;grid-row:1}.preview-card{padding:18px}.zone-grid{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}header,nav{padding-left:16px;padding-right:16px}.page-heading{align-items:flex-start}h1{font-size:24px}.badge{white-space:normal}.instance{font-size:0}.instance select{font-size:14px;min-width:130px;max-width:210px}}
  @media(max-width:480px){header{gap:8px}header b{font-size:17px}main{padding:16px}.card{padding:18px}.fields{grid-template-columns:1fr;gap:0}.metrics{gap:22px}.metric{min-width:110px}.metric strong{font-size:18px}nav{gap:0}nav button{padding:16px 12px}.actions{flex-direction:column}.instance select{max-width:150px}.page-heading{display:block}.badge{display:inline-block;margin-top:10px}}
.field-label{display:inline-flex;align-items:center;gap:6px}button.info{flex:none;width:20px;height:20px;min-width:20px;min-height:0;margin:0;padding:0;border-radius:50%;border:1px solid var(--secondary-text-color);background:none;color:var(--secondary-text-color);font:italic 600 11px/1 serif;cursor:pointer}button.info:hover,button.info:focus-visible{color:var(--primary-color);border-color:var(--primary-color)}.info-pop{margin:auto;max-width:min(440px,90vw);padding:16px 18px;border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color,#fff);color:var(--primary-text-color);box-shadow:0 8px 28px rgba(0,0,0,.25);line-height:1.45}.info-pop::backdrop{background:rgba(0,0,0,.15)}.info-pop p{margin:8px 0}.info-pop code{color:var(--secondary-text-color);font-size:12px}
`;

customElements.define("virtual-climate-panel", VirtualClimatePanel);
