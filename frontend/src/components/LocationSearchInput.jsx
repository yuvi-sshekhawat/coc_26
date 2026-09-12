import React, { useState, useEffect, useRef } from "react";
import { Search, MapPin, Loader2, X, Crosshair } from "lucide-react";

export default function LocationSearchInput({
  label,
  value,
  onChange,
  onPickOnMap,
  isPicking = false,
  placeholder = "Search location or landmark (e.g. Jaipur Railway Station)",
  required = false,
  badgeColor = "var(--accent-primary)",
}) {
  const [query, setQuery] = useState(value?.name || "");
  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const containerRef = useRef(null);
  const timeoutRef = useRef(null);

  // Sync external value name changes
  useEffect(() => {
    if (value?.name !== undefined && value.name !== query) {
      setQuery(value.name || "");
    }
  }, [value?.name]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleInputChange = (e) => {
    const text = e.target.value;
    setQuery(text);
    if (!text.trim()) {
      setSuggestions([]);
      setIsOpen(false);
      if (onChange) {
        onChange({ name: "", latitude: null, longitude: null });
      }
      return;
    }

    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      fetchSuggestions(text);
    }, 280);
  };

  const fetchSuggestions = async (searchText) => {
    if (!searchText || searchText.trim().length < 2) return;
    setIsLoading(true);

    const apiKey = import.meta.env.VITE_MAPTILER_API_KEY;
    let results = [];

    // 1. Primary: MapTiler Geocoding API
    if (apiKey) {
      try {
        const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(
          searchText.trim()
        )}.json?key=${apiKey}&autocomplete=true&limit=5`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (data.features && data.features.length > 0) {
            results = data.features.map((f) => ({
              name: f.place_name || f.text,
              latitude: Number(f.geometry.coordinates[1].toFixed(5)),
              longitude: Number(f.geometry.coordinates[0].toFixed(5)),
            }));
          }
        }
      } catch (err) {
        // Fall through to Nominatim
      }
    }

    // 2. Fallback: OpenStreetMap Nominatim API
    if (results.length === 0) {
      try {
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          searchText.trim()
        )}&limit=5`;
        const res = await fetch(url, {
          headers: { "User-Agent": "FairReliefPlanner/2.0" },
        });
        if (res.ok) {
          const data = await res.json();
          results = data.map((d) => ({
            name: d.display_name,
            latitude: Number(parseFloat(d.lat).toFixed(5)),
            longitude: Number(parseFloat(d.lon).toFixed(5)),
          }));
        }
      } catch (err) {
        // Handled silently
      }
    }

    setSuggestions(results);
    setIsOpen(results.length > 0);
    setIsLoading(false);
  };

  const handleSelectSuggestion = (item) => {
    setQuery(item.name);
    setSuggestions([]);
    setIsOpen(false);
    if (onChange) {
      onChange(item);
    }
  };

  const handleClear = () => {
    setQuery("");
    setSuggestions([]);
    setIsOpen(false);
    if (onChange) {
      onChange({ name: "", latitude: null, longitude: null });
    }
  };

  const hasCoords =
    typeof value?.latitude === "number" &&
    !isNaN(value.latitude) &&
    typeof value?.longitude === "number" &&
    !isNaN(value.longitude);

  return (
    <div className="location-search-container" ref={containerRef}>
      {label && (
        <div className="search-label-row">
          <label className="search-field-label">{label}</label>
          {hasCoords && (
            <span className="search-coord-badge" style={{ borderColor: badgeColor }}>
              <span className="coord-dot" style={{ background: badgeColor }} />
              {value.latitude.toFixed(4)}° N, {value.longitude.toFixed(4)}° E
            </span>
          )}
        </div>
      )}

      <div className={`search-input-wrapper ${isPicking ? "is-picking" : ""}`}>
        <Search size={14} className="search-lead-icon" />
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true);
          }}
          placeholder={placeholder}
          required={required}
          className="search-text-input"
        />

        {isLoading ? (
          <Loader2 size={13} className="search-spinner" />
        ) : query ? (
          <button type="button" className="search-clear-btn" onClick={handleClear} title="Clear location">
            <X size={13} />
          </button>
        ) : null}

        {onPickOnMap && (
          <button
            type="button"
            className={`btn-pick-on-map ${isPicking ? "active" : ""}`}
            onClick={onPickOnMap}
            title={isPicking ? "Click on the map to set this location" : "Pick this location on the map"}
          >
            <Crosshair size={13} />
            <span>{isPicking ? "CLICK MAP" : "MAP PICK"}</span>
          </button>
        )}
      </div>

      {isOpen && suggestions.length > 0 && (
        <ul className="search-suggestions-dropdown">
          {suggestions.map((item, idx) => (
            <li
              key={idx}
              className="suggestion-item"
              onClick={() => handleSelectSuggestion(item)}
            >
              <MapPin size={13} className="suggestion-icon" />
              <div className="suggestion-info">
                <span className="suggestion-name">{item.name}</span>
                <span className="suggestion-coords">
                  {item.latitude.toFixed(4)}° N, {item.longitude.toFixed(4)}° E
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
