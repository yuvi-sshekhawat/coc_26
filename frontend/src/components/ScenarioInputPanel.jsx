import React, { useState, useEffect } from "react";
import {
  Building2,
  Target,
  Home,
  Sparkles,
  Zap,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  MapPin,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import LocationSearchInput from "./LocationSearchInput";

export default function ScenarioInputPanel({
  scenarioName,
  onScenarioNameChange,
  depot,
  onDepotChange,
  destination,
  onDestinationChange,
  houseCount,
  onHouseCountChange,
  houses,
  onHousesChange,
  activePickingTarget,
  onSetActivePickingTarget,
  onSubmit,
  isOptimizing = false,
  error,
}) {
  const [collapsedHouseList, setCollapsedHouseList] = useState(false);

  // Sync houseCount with houses array length
  useEffect(() => {
    const targetCount = Math.min(50, Math.max(1, houseCount));
    if (houses.length !== targetCount) {
      if (houses.length < targetCount) {
        const diff = targetCount - houses.length;
        const newItems = [];
        const hasDepot = depot?.latitude && depot?.longitude;
        const baseLat = hasDepot ? depot.latitude : 0;
        const baseLon = hasDepot ? depot.longitude : 0;
        for (let i = 0; i < diff; i++) {
          const idx = houses.length + i + 1;
          let lat = null;
          let lon = null;
          if (hasDepot) {
            const angle = (idx / targetCount) * 2 * Math.PI + (idx * 0.4);
            const radiusKm = 2.0 + (idx % 6) * 1.5;
            const dLat = (radiusKm / 111.32) * Math.sin(angle);
            const dLon = (radiusKm / (111.32 * Math.cos((baseLat * Math.PI) / 180))) * Math.cos(angle);
            lat = Number((baseLat + dLat).toFixed(5));
            lon = Number((baseLon + dLon).toFixed(5));
          }
          newItems.push({
            house_id: idx,
            location_name: `Community House #${idx}`,
            latitude: lat,
            longitude: lon,
            demand: 10 + (idx % 4) * 5,
          });
        }
        onHousesChange([...houses, ...newItems]);
      } else {
        onHousesChange(houses.slice(0, targetCount));
      }
    }
  }, [houseCount, depot]);

  const handleHouseChange = (idx, updatedLocation) => {
    const updated = [...houses];
    updated[idx] = {
      ...updated[idx],
      location_name: updatedLocation.name || `Community House #${idx + 1}`,
      latitude: updatedLocation.latitude,
      longitude: updatedLocation.longitude,
    };
    onHousesChange(updated);
  };

  const handleAutoPopulateAroundDepot = () => {
    if (!depot?.latitude || !depot?.longitude) {
      return;
    }
    const centerLat = depot.latitude;
    const centerLon = depot.longitude;
    const count = Math.min(50, Math.max(1, houseCount));
    const newHouses = [];

    for (let i = 1; i <= count; i++) {
      const angle = (i / count) * 2 * Math.PI + (i * 0.35);
      const radiusKm = 2.0 + (i % 7) * 1.8;
      const dLat = (radiusKm / 111.32) * Math.sin(angle);
      const dLon = (radiusKm / (111.32 * Math.cos((centerLat * Math.PI) / 180))) * Math.cos(angle);
      newHouses.push({
        house_id: i,
        location_name: `${depot.name ? depot.name.split(" ")[0] : "Community"} Relief Sector #${i}`,
        latitude: Number((centerLat + dLat).toFixed(5)),
        longitude: Number((centerLon + dLon).toFixed(5)),
        demand: 10 + (i % 4) * 5,
      });
    }
    onHousesChange(newHouses);
  };

  const hasAllCoords =
    depot?.latitude &&
    depot?.longitude &&
    houses.every((h) => typeof h.latitude === "number" && typeof h.longitude === "number");

  return (
    <div className="scenario-input-panel">
      <div className="input-panel-header">
        <div>
          <div className="section-kicker">EMERGENCY RELIEF STAGING</div>
          <h2 className="input-panel-title">Staging Inputs</h2>
        </div>
        <div className="input-panel-badge">
          <span>MAX 50 HOUSES</span>
        </div>
      </div>

      <p className="input-panel-subtitle">
        Enter source, destination, and house locations. The backend automatically determines
        fleet size, vehicle capacities, lexicographic fair allocation, and road routes.
      </p>

      {error && (
        <div className="input-panel-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Scenario Title Input */}
      <div className="input-field-group">
        <label className="field-label">SCENARIO NAME</label>
        <input
          type="text"
          value={scenarioName}
          onChange={(e) => onScenarioNameChange(e.target.value)}
          placeholder="e.g. Jaipur Flood Emergency Response"
          className="scenario-name-input"
          required
        />
      </div>

      {/* 1. REPORT / SOURCE / DEPOT LOCATION */}
      <div className="input-section-card">
        <div className="section-card-header">
          <Building2 size={16} color="#fbbf24" />
          <span className="section-card-title">1. SOURCE / DEPOT LOCATION</span>
          <span className="required-tag">MANDATORY</span>
        </div>
        <LocationSearchInput
          label="Search Depot / Staging Warehouse"
          value={depot}
          onChange={onDepotChange}
          onPickOnMap={() => onSetActivePickingTarget(activePickingTarget === "depot" ? null : "depot")}
          isPicking={activePickingTarget === "depot"}
          placeholder="Type e.g. Jaipur Railway Station or Warehouse..."
          required
          badgeColor="#fbbf24"
        />
      </div>

      {/* 2. DESTINATION LOCATION */}
      <div className="input-section-card">
        <div className="section-card-header">
          <Target size={16} color="#a855f7" />
          <span className="section-card-title">2. DESTINATION / TARGET LOCATION</span>
          <span className="optional-tag">OPTIONAL</span>
        </div>
        <LocationSearchInput
          label="Search Destination / Trauma Center"
          value={destination}
          onChange={onDestinationChange}
          onPickOnMap={() => onSetActivePickingTarget(activePickingTarget === "destination" ? null : "destination")}
          isPicking={activePickingTarget === "destination"}
          placeholder="Type e.g. SMS Hospital Jaipur or Evacuation Staging..."
          badgeColor="#a855f7"
        />
      </div>

      {/* 3. NUMBER OF HOUSES (MIN 1, MAX 50) */}
      <div className="input-section-card">
        <div className="section-card-header">
          <Home size={16} color="#10b981" />
          <span className="section-card-title">3. NUMBER OF HOUSES TO DELIVER TO</span>
          <span className="house-count-pill">{houseCount} / 50 HOUSES</span>
        </div>

        <div className="house-slider-row">
          <input
            type="range"
            min="1"
            max="50"
            step="1"
            value={houseCount}
            onChange={(e) => onHouseCountChange(parseInt(e.target.value, 10) || 1)}
            className="house-range-slider"
          />
          <input
            type="number"
            min="1"
            max="50"
            value={houseCount}
            onChange={(e) => onHouseCountChange(Math.min(50, Math.max(1, parseInt(e.target.value, 10) || 1)))}
            className="house-number-input"
          />
        </div>

        <div className="house-actions-strip">
          <button
            type="button"
            className="btn-auto-populate"
            onClick={handleAutoPopulateAroundDepot}
            disabled={!depot?.latitude || !depot?.longitude}
            title={
              depot?.latitude
                ? `Auto-place ${houseCount} community locations in the depot operational area`
                : "Select a Source / Depot location above first"
            }
          >
            <Sparkles size={13} />
            <span>
              {depot?.latitude
                ? `Auto-Distribute ${houseCount} Houses in ${depot.name ? depot.name.split(" ")[0] : "Depot"} Sector`
                : "Select Depot First to Auto-Distribute"}
            </span>
          </button>
        </div>
      </div>

      {/* 4. HOUSE LOCATIONS (DYNAMICALLY RENDERED) */}
      <div className="input-section-card">
        <div
          className="section-card-header clickable"
          onClick={() => setCollapsedHouseList((prev) => !prev)}
        >
          <div className="header-left">
            <MapPin size={16} color="#38bdf8" />
            <span className="section-card-title">4. HOUSE LOCATIONS ({houses.length} ACTIVE)</span>
          </div>
          <button type="button" className="btn-toggle-collapse">
            {collapsedHouseList ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
          </button>
        </div>

        {!collapsedHouseList && (
          <div className="houses-dynamic-list">
            {houses.map((house, idx) => (
              <div key={house.house_id || idx} className="house-input-item">
                <div className="house-item-header">
                  <span className="house-idx-badge">#{idx + 1}</span>
                  <span className="house-title">{house.location_name || `House #${idx + 1}`}</span>
                  {house.latitude && house.longitude && (
                    <span className="house-coords-tag">
                      {house.latitude.toFixed(4)}° N, {house.longitude.toFixed(4)}° E
                    </span>
                  )}
                </div>

                <LocationSearchInput
                  value={{
                    name: house.location_name,
                    latitude: house.latitude,
                    longitude: house.longitude,
                  }}
                  onChange={(loc) => handleHouseChange(idx, loc)}
                  onPickOnMap={() => onSetActivePickingTarget(activePickingTarget === `house_${idx}` ? null : `house_${idx}`)}
                  isPicking={activePickingTarget === `house_${idx}`}
                  placeholder={`Search address/neighborhood for House #${idx + 1}...`}
                  badgeColor="#38bdf8"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SUBMISSION BUTTON */}
      <div className="input-submit-area">
        <button
          type="button"
          className="btn-optimize-submit"
          onClick={onSubmit}
          disabled={isOptimizing || !hasAllCoords}
        >
          {isOptimizing ? (
            <>
              <span className="submit-spinner" />
              <span>OPTIMIZING FAIR ALLOCATION & ROUTES...</span>
            </>
          ) : (
            <>
              <Zap size={16} />
              <span>OPTIMIZE & DISPATCH RELIEF ({houses.length} HOUSES)</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
