import React, { useState } from "react";
import { X, Upload, CheckCircle2, AlertTriangle, FileText, Sparkles, Building2, MapPin } from "lucide-react";

const SAMPLE_CSV = `customer_id,location_name,latitude,longitude,demand
1,Community Clinic North,26.9350,75.7950,45
2,Civic Center West,26.9020,75.7480,35
3,East Sector Hospital,26.8850,75.8250,55
4,South Shelter Post,26.8450,75.7720,40
5,Central Transit Point,26.9180,75.8080,30
6,Riverside Evacuation Base,26.9650,75.8300,50
`;

export default function CreateScenarioModal({ isOpen, onClose, onCreated, apiBase }) {
  const [name, setName] = useState("");
  const [depotName, setDepotName] = useState("");
  const [depotLat, setDepotLat] = useState("");
  const [depotLon, setDepotLon] = useState("");
  const [csvContent, setCsvContent] = useState("");
  const [fileName, setFileName] = useState("");
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".csv")) {
      setError("Please select a valid .csv file.");
      return;
    }

    setFileName(file.name);
    setError("");

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result;
      if (typeof text === "string") {
        setCsvContent(text);
        validateCsv(text);
      }
    };
    reader.readAsText(file);
  };

  const validateCsv = async (content) => {
    setValidating(true);
    setValidationResult(null);
    setError("");

    try {
      const res = await fetch(`${apiBase}/api/scenarios/validate-csv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_content: content }),
      });
      const data = await res.json();
      if (data.valid) {
        setValidationResult(data);
      } else {
        setError(data.error || "CSV validation failed.");
      }
    } catch (err) {
      setError("Failed to validate CSV: " + err.message);
    } finally {
      setValidating(false);
    }
  };

  const handleLoadSample = () => {
    setName("Jaipur Northern Flood Response");
    setDepotName("Jaipur Emergency Staging Warehouse");
    setDepotLat("26.9124");
    setDepotLon("75.7873");
    setCsvContent(SAMPLE_CSV);
    setFileName("jaipur_north_requirements.csv");
    validateCsv(SAMPLE_CSV);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) return setError("Scenario name is required.");
    if (!depotName.trim()) return setError("Depot name is required.");
    const lat = parseFloat(depotLat);
    const lon = parseFloat(depotLon);
    if (isNaN(lat) || lat < -90 || lat > 90) {
      return setError("Valid depot latitude between -90 and 90 is required.");
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      return setError("Valid depot longitude between -180 and 180 is required.");
    }
    if (!csvContent.trim()) {
      return setError("A valid requirements CSV file must be uploaded.");
    }
    if (!validationResult?.valid) {
      return setError("Please ensure the CSV requirements pass validation.");
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${apiBase}/api/scenarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          depot_name: depotName.trim(),
          depot_latitude: lat,
          depot_longitude: lon,
          csv_content: csvContent,
          auto_solve: true,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to create scenario.");
      }

      const created = await res.json();
      onCreated(created);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-window" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="section-kicker">GEOSPATIAL RELIEF OPERATIONS</div>
            <h2>Create New Relief Scenario</h2>
          </div>
          <button className="icon-close-btn" onClick={onClose} title="Close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && (
            <div className="modal-error-box">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-grid">
            <div className="form-group full-width">
              <label>SCENARIO NAME</label>
              <input
                type="text"
                placeholder="e.g. Jaipur Flood Relief"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="form-group full-width">
              <label>DEPOT NAME</label>
              <input
                type="text"
                placeholder="e.g. Jaipur Central Relief Warehouse"
                value={depotName}
                onChange={(e) => setDepotName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>DEPOT LATITUDE (-90 to +90)</label>
              <input
                type="number"
                step="any"
                placeholder="26.9124"
                value={depotLat}
                onChange={(e) => setDepotLat(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>DEPOT LONGITUDE (-180 to +180)</label>
              <input
                type="number"
                step="any"
                placeholder="75.7873"
                value={depotLon}
                onChange={(e) => setDepotLon(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-section-title">
            <span>REQUIREMENTS CSV FILE</span>
            <button type="button" className="btn-load-sample" onClick={handleLoadSample}>
              <Sparkles size={12} /> Auto-Fill Sample Data
            </button>
          </div>

          <div className="csv-upload-box">
            <input
              type="file"
              id="csv-file-input"
              accept=".csv"
              onChange={handleFileUpload}
              className="csv-hidden-input"
            />
            <label htmlFor="csv-file-input" className="csv-drop-label">
              <Upload size={24} color="var(--amber)" />
              <div className="upload-prompt">
                {fileName ? <b>Selected: {fileName}</b> : "Click to select or upload requirements CSV"}
              </div>
              <span className="upload-hint">
                Required format: <code>customer_id,location_name,latitude,longitude,demand</code>
              </span>
            </label>
          </div>

          {validating && (
            <div className="validation-loading-box">
              <span>Validating CSV structure and coordinate ranges...</span>
            </div>
          )}

          {validationResult?.valid && (
            <div className="csv-preview-card">
              <div className="preview-header">
                <div className="preview-stat">
                  <CheckCircle2 size={16} color="var(--green)" />
                  <span>
                    <b>{validationResult.total_customers} Locations Validated</b>
                  </span>
                </div>
                <div className="preview-stat">
                  <span>
                    Total Demand: <b>{validationResult.total_demand} units</b>
                  </span>
                </div>
                <div className="preview-stat">
                  <span>
                    Stock Bound (70%): <b>{validationResult.estimated_stock} units</b>
                  </span>
                </div>
              </div>

              <div className="preview-table-wrapper">
                <table className="mini-preview-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Location Name</th>
                      <th>Lat, Lon</th>
                      <th>Demand</th>
                    </tr>
                  </thead>
                  <tbody>
                    {validationResult.preview.map((p) => (
                      <tr key={p.customer_id}>
                        <td>#{p.customer_id}</td>
                        <td>{p.location_name}</td>
                        <td>
                          {p.latitude.toFixed(4)}, {p.longitude.toFixed(4)}
                        </td>
                        <td><b>{p.demand}</b></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="nb-button" onClick={onClose} disabled={submitting}>
              CANCEL
            </button>
            <button
              type="submit"
              className="nb-button primary"
              disabled={submitting || !validationResult?.valid}
            >
              {submitting ? "SOLVING WITH AI-05..." : "CREATE & SOLVE SCENARIO"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
