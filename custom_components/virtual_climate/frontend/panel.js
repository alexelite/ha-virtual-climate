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
  },
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
  t(key) { return TEXT[this._hass?.language?.startsWith("ro") ? "ro" : "en"][key] || key; }
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
      if (this._entryId && this._page !== "settings" && this._hass.user?.is_admin) {
        const id = this._entryId;
        const snapshot = await this._api("settings", {entry_id:id});
        if (id === this._entryId && this._page !== "settings" && snapshot.revision !== this._snapshot?.revision) {
          this._snapshot = snapshot;
          this._draft = clone(snapshot.settings);
          this._render();
        }
      }
      this._updateLive();
    } catch { /* The HA connection indicator handles temporary disconnects. */ }
  }
  _api(command, data = {}) { return this._hass.callWS({type:`virtual_climate/panel/${command}`, ...data}); }
  _dirty() { return !!this._snapshot && JSON.stringify(this._draft) !== JSON.stringify(this._snapshot.settings); }
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
    const page = ["operation", "diagnostics", "settings"].includes(parts[1]) ? parts[1] : "operation";
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
    this._snapshot = this._draft = this._review = null;
    this._error = this._notice = "";
    this._render();
    if (id && this._hass.user?.is_admin) {
      try {
        const snapshot = await this._api("settings", {entry_id:id});
        if (sequence !== this._sequence) return;
        this._snapshot = snapshot;
        this._draft = clone(snapshot.settings);
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
      <nav aria-label="Virtual Climate">${["operation", "diagnostics", ...(this._hass?.user?.is_admin ? ["settings"] : [])].map((page) => `<button data-page="${page}" class="${this._page === page ? "active" : ""} ${page === "settings" ? "settings-tab" : ""}" aria-current="${this._page === page ? "page" : "false"}">${page === "settings" ? "⚙ " : ""}${this.t(page)}</button>`).join("")}</nav>
      <main>${this._error ? `<div role="alert" class="alert error">${escapeHTML(this._error)} <button id="retry">${this.t("reload")}</button></div>` : ""}
      ${this._notice ? `<div role="status" class="alert success">${escapeHTML(this._notice)}</div>` : ""}
      ${!this._entries.length ? `<p>${this.t(this._error || this._loadedEntries ? "noEntries" : "loading")}</p>` : !this._entryId ? "" : this._page === "settings" ? this._settingsView() : this._page === "diagnostics" ? this._diagnosticsView() : this._operationView()}</main>`;
    this.shadowRoot.querySelector(".menu").onclick = () => this.dispatchEvent(new CustomEvent("hass-toggle-menu", {bubbles:true, composed:true}));
    this.shadowRoot.querySelectorAll("[data-page]").forEach((button) => button.onclick = () => this._navigate(this._entryId, button.dataset.page));
    const picker = this.shadowRoot.querySelector("#instance");
    if (picker) picker.onchange = () => { this._navigate(picker.value, this._page); picker.value = this._entryId; };
    this.shadowRoot.querySelector("#retry")?.addEventListener("click", () => {
      if (!this._dirty() || window.confirm(this.t("leave"))) this._switch(this._entryId, this._page);
    });
    this._bindSettings();
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
      <section class="card"><div class="metrics">${["supply_learning_status", "plant_state", "coordinator_phase"].map((key) => this._metric(key, key)).join("")}</div></section><p class="footnote">${this.t("feedback")}</p>`;
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
      <p class="alert">${this.t("reloadWarning")}</p><p>${this.t(review.learning_reset === "all" ? "allReset" : review.learning_reset === "points" ? "pointsReset" : "noReset")} ${review.reset_points.join(", ")}</p>
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
        this._snapshot = {...this._snapshot, settings:result.settings, revision:result.revision};
        this._draft = clone(result.settings);
        this._review = null;
        this._notice = this.t("success");
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
  main{max-width:1320px;margin:auto;padding:32px}.page-heading{display:flex;justify-content:space-between;align-items:center;margin:4px 0 26px;gap:16px}.eyebrow{text-transform:uppercase;letter-spacing:.09em;font-size:11px;font-weight:700;color:var(--accent);margin:0 0 8px}h1{font-size:28px;line-height:1.25;letter-spacing:-.6px;margin:0 0 10px;font-weight:600}h2{font-size:18px;margin:0 0 18px;font-weight:600}h3{font-size:16px;margin:0 0 20px}p{line-height:1.6;margin:8px 0 18px;color:var(--secondary-text-color,#63717b)}.card{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e5e7eb);border-radius:14px;padding:24px;margin-bottom:20px}.metrics{display:flex;flex-wrap:wrap;gap:24px 40px}.metric{display:flex;flex-direction:column;gap:10px;min-width:130px}.metric span{font-size:12px;color:var(--secondary-text-color,#63717b)}.metric strong{font-size:21px;font-weight:500}.zone-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}.zone{margin:0}.room-reading{display:flex;align-items:baseline;gap:12px;margin-bottom:24px}.room-reading strong{font-size:30px}.room-reading span{font-size:11px;color:var(--secondary-text-color,#63717b)}.section-title{margin:30px 0 18px}.zone-status{font-size:12px;margin:12px 0 0}.settings-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,1fr);gap:24px;align-items:start}aside{position:sticky;top:20px}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.fields label{min-width:0}label{display:flex;flex-direction:column;gap:8px;font-size:13px;font-weight:500;margin-bottom:18px}input,select{font:inherit;color:inherit;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#cbd1d6);border-radius:8px;padding:12px;min-width:0;width:100%;min-height:44px}input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}input:invalid{border-color:var(--error-color,#db4437)}.check{display:flex;flex-direction:row;align-items:center;gap:10px}.check input{width:18px;min-height:18px}fieldset{border:0;padding:0;margin:0;min-width:0}.hint,.footnote{font-size:12px;color:var(--secondary-text-color,#63717b)}.hint{margin:0 0 20px}.footnote{margin:24px 0}.badge{font-size:12px;background:var(--secondary-background-color,#eef2f5);padding:8px 12px;border-radius:30px;white-space:nowrap}[hidden]{display:none!important}button{font:inherit;font-weight:500;padding:12px 18px;border:1px solid var(--divider-color,#cbd1d6);border-radius:8px;cursor:pointer;background:var(--card-background-color,#fff);color:inherit;min-height:44px}button.primary{background:var(--accent);border-color:var(--accent);color:var(--text-primary-color,#fff)}button:disabled{opacity:.5;cursor:wait}.actions{display:flex;justify-content:flex-end;gap:12px;padding:8px 0 20px}.alert{padding:16px;border-radius:8px;background:var(--secondary-background-color,#eef2f5);line-height:1.6;margin-bottom:20px}.alert.error{border-left:4px solid var(--error-color,#db4437)}.alert.success{border-left:4px solid var(--success-color,#43a047)}.alert button{margin-left:12px}.review-card{border:2px solid var(--accent)}.table-scroll{overflow:auto;margin-bottom:20px}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}td,th{padding:10px 8px;border-bottom:1px solid var(--divider-color,#e5e7eb);max-width:260px;overflow-wrap:anywhere}th{color:var(--secondary-text-color,#63717b);font-weight:500}td input{max-width:120px}svg{display:block;width:100%;height:auto;overflow:visible}svg text{fill:var(--secondary-text-color,#63717b);font-size:11px}svg path{fill:none;stroke-width:3}.gridline{stroke:var(--divider-color,#e5e7eb)}.saved-curve{stroke:var(--secondary-text-color,#63717b);stroke-dasharray:6 5}.draft-curve{stroke:var(--accent)}svg circle{fill:var(--card-background-color,#fff);stroke:var(--accent);stroke-width:2}.legend{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--secondary-text-color,#63717b)}.saved-line,.draft-line{width:25px;border-top:3px solid var(--accent)}.saved-line{border-top:3px dashed var(--secondary-text-color,#63717b)}.draft-line{margin-left:18px}
  @media(max-width:850px){main{padding:20px}.settings-grid{grid-template-columns:1fr}aside{position:static;grid-row:1}.preview-card{padding:18px}.zone-grid{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}header,nav{padding-left:16px;padding-right:16px}.page-heading{align-items:flex-start}h1{font-size:24px}.badge{white-space:normal}.instance{font-size:0}.instance select{font-size:14px;min-width:130px;max-width:210px}}
  @media(max-width:480px){header{gap:8px}header b{font-size:17px}main{padding:16px}.card{padding:18px}.fields{grid-template-columns:1fr;gap:0}.metrics{gap:22px}.metric{min-width:110px}.metric strong{font-size:18px}nav{gap:0}nav button{padding:16px 12px}.actions{flex-direction:column}.instance select{max-width:150px}.page-heading{display:block}.badge{display:inline-block;margin-top:10px}}
`;

customElements.define("virtual-climate-panel", VirtualClimatePanel);
