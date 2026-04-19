import React, { useMemo, useState } from "react";
import { Check, Palette, Save, X } from "lucide-react";
import { GoogleLogo, OutlookLogo } from "../../logos";
import "./CalendarLabelsModal.css";

type CalendarIntegration = {
  id: string;
  email: string;
  provider: string;
  label?: string;
  color?: string;
};

interface CalendarLabelsModalProps {
  integrations: CalendarIntegration[];
  loading?: boolean;
  onClose: () => void;
  onSave: (items: CalendarIntegration[]) => void | Promise<void>;
}

const COLOR_OPTIONS = {
  blue: "#3B82F6",
  green: "#22C55E",
  purple: "#A855F7",
  amber: "#F59E0B",
  red: "#EF4444",
  cyan: "#06B6D4",
  pink: "#EC4899",
  lime: "#84CC16",
};

const COLORS = Object.values(COLOR_OPTIONS);

function getProviderLabel(provider: string) {
  if (provider === "microsoft") return "Outlook";
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

function ProviderLogo({ provider }: { provider: string }) {
  if (provider === "google") return <GoogleLogo className="calendar-label-provider-logo" />;
  if (provider === "microsoft") return <OutlookLogo className="calendar-label-provider-logo" />;
  return null;
}

function getInitials(email: string) {
  return email?.charAt(0)?.toUpperCase() || "?";
}

function getDefaultLabel(item: CalendarIntegration) {
  if (item.label?.trim()) return item.label.trim();

  const emailPrefix = item.email?.split("@")[0]?.trim();
  if (emailPrefix) return emailPrefix;

  return getProviderLabel(item.provider);
}

export default function CalendarLabelsModal({
  integrations,
  loading = false,
  onClose,
  onSave,
}: CalendarLabelsModalProps) {
  const sortedIntegrations = useMemo(
    () =>
      [...integrations].sort((a, b) => {
        const providerCompare = a.provider.localeCompare(b.provider);
        if (providerCompare !== 0) return providerCompare;
        return a.email.localeCompare(b.email);
      }),
    [integrations]
  );

  const [items, setItems] = useState<CalendarIntegration[]>(
    sortedIntegrations.map((item, idx) => ({
      ...item,
      label: getDefaultLabel(item),
      color: item.color || COLORS[idx % COLORS.length],
    }))
  );

  const legendItems = useMemo(() => {
    return items.map((item) => ({
      id: item.id,
      label: item.label?.trim() || item.email,
      color: item.color || COLORS[0],
    }));
  }, [items]);

  const normalizedLabels = items.map((item) => (item.label || "").trim().toLowerCase());
  const hasEmptyLabels = normalizedLabels.some((label) => !label);
  const hasDuplicateLabels = new Set(normalizedLabels).size !== normalizedLabels.length;
  const hasValidationError = hasEmptyLabels || hasDuplicateLabels;

  const updateItem = (id: string, patch: Partial<CalendarIntegration>) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, ...patch } : item))
    );
  };

  const handleSave = async () => {
    const cleanItems: CalendarIntegration[] = items.map((item) => ({
      id: item.id,
      email: item.email,
      provider: item.provider,
      label: item.label?.trim(),
      color: item.color,
    }));

    await onSave(cleanItems);
  };

  return (
    <div className="calendar-labels-overlay">
      <div className="calendar-labels-backdrop" onClick={onClose} />

      <div className="calendar-labels-modal">
        <button
          className="calendar-labels-close"
          onClick={onClose}
          aria-label="Close"
          type="button"
        >
          <X size={15} />
        </button>

        <div className="calendar-labels-header">
          <div className="calendar-labels-title">Label calendar accounts</div>
          <div className="calendar-labels-subtitle">
            Create human-friendly names and colors so Ordo can understand things
            like “Work”, “Personal”, or “Sales”.
          </div>
        </div>

        <div className="calendar-labels-legend">
          <div className="calendar-labels-section-title">Legend preview</div>
          <div className="calendar-labels-legend-row">
            {legendItems.map((item) => (
              <div key={item.id} className="calendar-legend-pill">
                <span
                  className="calendar-legend-dot"
                  style={{ background: item.color }}
                />
                {item.label}
              </div>
            ))}
          </div>
        </div>

        <div className="calendar-labels-list">
          {items.map((item) => (
            <div key={item.id} className="calendar-label-card">
              <div className="calendar-label-card-top">
                <div className="calendar-label-account">
                  <div className="calendar-label-avatar">
                    {getInitials(item.email)}
                  </div>
                  <div className="calendar-label-account-copy">
                    <div className="calendar-label-email">{item.email}</div>
                    <div className="calendar-label-provider">
                      <ProviderLogo provider={item.provider} />
                      {getProviderLabel(item.provider)}
                    </div>
                  </div>
                </div>
              </div>

              <div className="calendar-label-form-row">
                <label className="calendar-label-field">
                  <span className="calendar-label-field-title">Label</span>
                  <input
                    value={item.label || ""}
                    onChange={(e) =>
                      updateItem(item.id, { label: e.target.value })
                    }
                    placeholder="Work, Personal, Recruiting..."
                    className="calendar-label-input"
                  />
                </label>
              </div>

              <div className="calendar-label-form-row">
                <div className="calendar-label-field">
                  <span className="calendar-label-field-title">
                    <Palette size={13} />
                    Color
                  </span>

                  <div className="calendar-color-grid">
                    {COLORS.map((color) => {
                      const selected = item.color === color;
                      return (
                        <button
                          key={color}
                          type="button"
                          className={`calendar-color-swatch${selected ? " selected" : ""}`}
                          style={{ background: color }}
                          onClick={() => updateItem(item.id, { color })}
                          aria-label={`Select color ${color}`}
                        >
                          {selected && <Check size={13} />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {(hasEmptyLabels || hasDuplicateLabels) && (
          <div className="calendar-label-error">
            {hasEmptyLabels
              ? "Each calendar needs a label."
              : "Labels must be unique."}
          </div>
        )}

        <div className="calendar-labels-footer">
          <button
            type="button"
            className="calendar-labels-btn secondary"
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            type="button"
            className="calendar-labels-btn primary"
            onClick={handleSave}
            disabled={loading || hasValidationError}
          >
            {loading ? (
              <span className="calendar-labels-spinner" />
            ) : (
              <>
                <Save size={14} />
                Save labels
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
