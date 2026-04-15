import { useState, useEffect, type FormEvent } from "react";
import {
  listDownloads,
  getDownloadStats,
  createIPTag,
  deleteIPTag,
  getSearchPrefs,
  updateSearchPrefs,
} from "../api";
import type { DownloadRecord, DownloadStat, WeightRule } from "../api";

const ALL_FORMATS = [
  "epub", "mobi", "pdf", "azw3", "txt", "djvu", "cbr", "cbz", "doc", "rtf",
];

const TAG_PRESETS = [
  { value: "provider", label: "Provider", description: "Boost/demote specific IRC bots" },
  { value: "quality", label: "Quality", description: "Flag high or low quality sources" },
  { value: "language", label: "Language", description: "Prefer certain languages" },
  { value: "format", label: "Format", description: "Weight by file format details" },
  { value: "custom", label: "Custom", description: "Your own category" },
];

export default function AdminPage() {
  const [downloads, setDownloads] = useState<DownloadRecord[]>([]);
  const [stats, setStats] = useState<DownloadStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [ipFilter, setIpFilter] = useState("");

  // Tag form
  const [tagIp, setTagIp] = useState("");
  const [tagName, setTagName] = useState("");
  const [tagNotes, setTagNotes] = useState("");
  const [tagError, setTagError] = useState("");

  // Search prefs
  const [allowedFormats, setAllowedFormats] = useState<string[]>(["epub"]);
  const [weightRules, setWeightRules] = useState<WeightRule[]>([]);
  const [prefsLoading, setPrefsLoading] = useState(true);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsSaved, setPrefsSaved] = useState(false);

  // New rule form
  const [newTag, setNewTag] = useState("provider");
  const [newPattern, setNewPattern] = useState("");
  const [newWeight, setNewWeight] = useState(10);
  const [newLabel, setNewLabel] = useState("");

  const [tab, setTab] = useState<"activity" | "ips" | "settings">("settings");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [dl, st] = await Promise.all([
        listDownloads(ipFilter || undefined),
        getDownloadStats(),
      ]);
      setDownloads(dl);
      setStats(st);
    } catch (err) {
      console.error("Failed to load admin data:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPrefs = async () => {
    setPrefsLoading(true);
    try {
      const prefs = await getSearchPrefs();
      setAllowedFormats(prefs.allowed_formats);
      setWeightRules(prefs.weight_rules);
    } catch (err) {
      console.error("Failed to load search prefs:", err);
    } finally {
      setPrefsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchPrefs();
  }, []);

  useEffect(() => {
    if (tab === "activity") fetchData();
  }, [ipFilter]);

  const handleTag = async (e: FormEvent) => {
    e.preventDefault();
    setTagError("");

    if (!tagIp || !tagName) {
      setTagError("IP and name are required");
      return;
    }

    try {
      await createIPTag(tagIp, tagName, tagNotes || undefined);
      setTagIp("");
      setTagName("");
      setTagNotes("");
      fetchData();
    } catch (err: any) {
      setTagError(err.message);
    }
  };

  const handleDeleteTag = async (id: number) => {
    try {
      await deleteIPTag(id);
      fetchData();
    } catch (err: any) {
      console.error("Failed to delete tag:", err);
    }
  };

  const handleIpClick = (ip: string) => {
    setTagIp(ip);
    setTab("ips");
  };

  // --- Search prefs handlers ---

  const toggleFormat = (fmt: string) => {
    setAllowedFormats((prev) =>
      prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt]
    );
    setPrefsSaved(false);
  };

  const addRule = () => {
    if (!newPattern.trim()) return;
    setWeightRules((prev) => [
      ...prev,
      {
        tag: newTag,
        pattern: newPattern.trim(),
        weight: newWeight,
        label: newLabel.trim() || `${newTag}: ${newPattern.trim()}`,
      },
    ]);
    setNewPattern("");
    setNewLabel("");
    setNewWeight(10);
    setPrefsSaved(false);
  };

  const removeRule = (idx: number) => {
    setWeightRules((prev) => prev.filter((_, i) => i !== idx));
    setPrefsSaved(false);
  };

  const savePrefs = async () => {
    setPrefsSaving(true);
    setPrefsSaved(false);
    try {
      await updateSearchPrefs({
        allowed_formats: allowedFormats,
        weight_rules: weightRules,
      });
      setPrefsSaved(true);
      setTimeout(() => setPrefsSaved(false), 3000);
    } catch (err) {
      console.error("Failed to save prefs:", err);
    } finally {
      setPrefsSaving(false);
    }
  };

  const tagColor = (tag: string) => {
    const colors: Record<string, string> = {
      provider: "#7c6fff",
      quality: "#34d399",
      language: "#fbbf24",
      format: "#f472b6",
      custom: "#6b7080",
    };
    return colors[tag] || colors.custom;
  };

  return (
    <div className="admin-page">
      <h2>Admin</h2>

      <div className="tab-bar">
        <button
          className={tab === "settings" ? "active" : ""}
          onClick={() => setTab("settings")}
        >
          Search Settings
        </button>
        <button
          className={tab === "activity" ? "active" : ""}
          onClick={() => setTab("activity")}
        >
          Download Activity
        </button>
        <button
          className={tab === "ips" ? "active" : ""}
          onClick={() => setTab("ips")}
        >
          IP Tracking
        </button>
      </div>

      {tab === "settings" && (
        <div className="settings-tab">
          {prefsLoading ? (
            <div className="search-status">
              <div className="spinner" />
              <p>Loading preferences...</p>
            </div>
          ) : (
            <>
              {/* Format filter */}
              <div className="settings-section">
                <h3>Allowed Formats</h3>
                <p className="settings-desc">
                  Only these file formats will be shown in search results.
                  Uncheck all to show everything.
                </p>
                <div className="format-toggles">
                  {ALL_FORMATS.map((fmt) => (
                    <label
                      key={fmt}
                      className={`format-toggle ${allowedFormats.includes(fmt) ? "active" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={allowedFormats.includes(fmt)}
                        onChange={() => toggleFormat(fmt)}
                      />
                      {fmt.toUpperCase()}
                    </label>
                  ))}
                </div>
              </div>

              {/* Weight rules */}
              <div className="settings-section">
                <h3>Result Weighting Rules</h3>
                <p className="settings-desc">
                  Results matching a pattern get their weight added to their score.
                  Higher scores appear first. Use negative weights to push results down.
                </p>

                {weightRules.length > 0 && (
                  <div className="rules-list">
                    {weightRules.map((rule, i) => (
                      <div key={i} className="rule-item">
                        <span
                          className="rule-tag"
                          style={{
                            background: `${tagColor(rule.tag)}20`,
                            color: tagColor(rule.tag),
                          }}
                        >
                          {rule.tag}
                        </span>
                        <span className="rule-pattern">"{rule.pattern}"</span>
                        <span
                          className={`rule-weight ${rule.weight >= 0 ? "positive" : "negative"}`}
                        >
                          {rule.weight > 0 ? "+" : ""}
                          {rule.weight}
                        </span>
                        <span className="rule-label">{rule.label}</span>
                        <button
                          className="btn-small btn-danger"
                          onClick={() => removeRule(i)}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="add-rule-form">
                  <h4>Add Rule</h4>
                  <div className="add-rule-fields">
                    <select
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                    >
                      {TAG_PRESETS.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label} - {t.description}
                        </option>
                      ))}
                    </select>
                    <input
                      type="text"
                      value={newPattern}
                      onChange={(e) => setNewPattern(e.target.value)}
                      placeholder="Pattern to match (e.g. bot name, keyword)"
                    />
                    <div className="weight-input">
                      <label>Weight:</label>
                      <input
                        type="number"
                        value={newWeight}
                        onChange={(e) => setNewWeight(parseInt(e.target.value) || 0)}
                      />
                    </div>
                    <input
                      type="text"
                      value={newLabel}
                      onChange={(e) => setNewLabel(e.target.value)}
                      placeholder="Description (optional)"
                    />
                    <button
                      onClick={addRule}
                      disabled={!newPattern.trim()}
                      className="btn-secondary"
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>

              {/* Save button */}
              <div className="settings-actions">
                <button onClick={savePrefs} disabled={prefsSaving}>
                  {prefsSaving ? "Saving..." : "Save Preferences"}
                </button>
                {prefsSaved && (
                  <span className="save-confirmation">Saved</span>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "activity" && (
        <div className="activity-tab">
          <div className="filter-row">
            <input
              type="text"
              value={ipFilter}
              onChange={(e) => setIpFilter(e.target.value)}
              placeholder="Filter by IP..."
            />
            <button onClick={fetchData} className="btn-secondary">
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="search-status">
              <div className="spinner" />
              <p>Loading...</p>
            </div>
          ) : downloads.length === 0 ? (
            <p className="muted">No download activity yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Book</th>
                  <th>IP</th>
                  <th>Who</th>
                </tr>
              </thead>
              <tbody>
                {downloads.map((d) => (
                  <tr key={d.id}>
                    <td>
                      {new Date(d.downloaded_at).toLocaleString()}
                    </td>
                    <td>
                      <strong>{d.book_title}</strong>
                      {d.book_author && (
                        <span className="muted"> by {d.book_author}</span>
                      )}
                    </td>
                    <td>
                      <span
                        className="ip-link"
                        onClick={() => handleIpClick(d.ip_address)}
                      >
                        {d.ip_address}
                      </span>
                    </td>
                    <td>
                      {d.ip_tag ? (
                        <span className="tag-badge">{d.ip_tag.tag_name}</span>
                      ) : (
                        <span
                          className="tag-unset"
                          onClick={() => handleIpClick(d.ip_address)}
                        >
                          Tag
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "ips" && (
        <div className="ips-tab">
          <div className="ip-stats">
            <h3>Download Stats by IP</h3>
            {stats.length === 0 ? (
              <p className="muted">No data yet.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>IP Address</th>
                    <th>Downloads</th>
                    <th>Last Active</th>
                    <th>Tag</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {stats.map((s) => (
                    <tr key={s.ip_address}>
                      <td>
                        <span
                          className="ip-link"
                          onClick={() => {
                            setTagIp(s.ip_address);
                          }}
                        >
                          {s.ip_address}
                        </span>
                      </td>
                      <td>{s.download_count}</td>
                      <td>
                        {s.last_download
                          ? new Date(s.last_download).toLocaleString()
                          : "Never"}
                      </td>
                      <td>
                        {s.ip_tag ? (
                          <span className="tag-badge">
                            {s.ip_tag.tag_name}
                          </span>
                        ) : (
                          <span className="muted">Untagged</span>
                        )}
                      </td>
                      <td>
                        {s.ip_tag && (
                          <button
                            className="btn-small btn-danger"
                            onClick={() => handleDeleteTag(s.ip_tag!.id)}
                          >
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="tag-form-section">
            <h3>Tag an IP</h3>
            <form onSubmit={handleTag} className="tag-form">
              <input
                type="text"
                value={tagIp}
                onChange={(e) => setTagIp(e.target.value)}
                placeholder="IP Address"
              />
              <input
                type="text"
                value={tagName}
                onChange={(e) => setTagName(e.target.value)}
                placeholder='Name (e.g. "Dave")'
              />
              <input
                type="text"
                value={tagNotes}
                onChange={(e) => setTagNotes(e.target.value)}
                placeholder="Notes (optional)"
              />
              <button type="submit">Save Tag</button>
              {tagError && <p className="error">{tagError}</p>}
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
