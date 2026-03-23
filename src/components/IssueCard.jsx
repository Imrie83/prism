import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const SEV_META = {
  high: { label: "High", cls: "sev-counts__item--high", bar: "var(--red)", glow: "rgba(248,113,113,0.15)" },
  medium: { label: "Medium", cls: "sev-counts__item--medium", bar: "var(--yellow)", glow: "rgba(251,191,36,0.12)" },
  low: { label: "Low", cls: "sev-counts__item--low", bar: "var(--green)", glow: "rgba(52,211,153,0.1)" },
};

export default function IssueCard({ issue, defaultOpen = false, index = 0, checked, onCheckedChange }) {
  const [open, setOpen] = useState(defaultOpen);
  const sev = SEV_META[issue.severity] || SEV_META.low;
  const type = (issue.type || "unknown").replace(/_/g, " ");
  const hasCheckbox = checked !== undefined && onCheckedChange;

  return (
    <motion.div
      className="issue-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: index * 0.04, ease: "easeOut" }}
      whileHover={{ borderColor: "var(--border2)", boxShadow: `0 4px 20px ${sev.glow}` }}
      style={{ overflow: "hidden" }}
    >
      {/* Severity bar */}
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 0.45, delay: 0.1 + index * 0.04, ease: "easeOut" }}
        style={{
          height: 2,
          background: sev.bar,
          transformOrigin: "left",
          boxShadow: `0 0 8px ${sev.glow}`,
          opacity: 0.7,
        }}
      />

      {/* Header */}
      <motion.div
        className="issue-card__header"
        onClick={() => setOpen(o => !o)}
        style={{ cursor: "pointer" }}
        whileTap={{ scale: 0.995 }}
      >
        {/* Checkbox — shown when email integration is active */}
        {hasCheckbox && (
          <div
            onClick={e => { e.stopPropagation(); onCheckedChange(!checked); }}
            style={{
              width: 15, height: 15, borderRadius: 3, flexShrink: 0, cursor: "pointer",
              border: `2px solid ${checked ? "var(--blue)" : "var(--border2)"}`,
              background: checked ? "var(--blue)" : "transparent",
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.15s",
            }}>
            {checked && <svg width="9" height="7" viewBox="0 0 9 7" fill="none"><path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
          </div>
        )}

        {/* Coloured severity dot */}
        <motion.div
          animate={issue.severity === "high"
            ? { scale: [1, 1.35, 1], opacity: [1, 0.5, 1] }
            : {}}
          transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
          style={{
            width: 8, height: 8, borderRadius: "50%",
            background: sev.bar, flexShrink: 0,
            boxShadow: issue.severity === "high" ? `0 0 8px ${sev.bar}` : "none",
          }}
        />

        <span className="issue-card__type">{type}</span>

        {issue.location && (
          <span className="issue-card__location">{issue.location}</span>
        )}

        <span className={`issue-card__sev issue-card__sev--${issue.severity}`}>
          {sev.label}
        </span>

        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.22, ease: "easeInOut" }}
          style={{ color: "var(--ink3)", flexShrink: 0 }}
        >
          <ChevronDown size={14} />
        </motion.div>
      </motion.div>

      {/* Body */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div className="issue-card__body">
              {issue.original && (
                <div className="issue-card__row">
                  <span className="issue-card__row-label">Found</span>
                  <span className="issue-card__original">{issue.original}</span>
                </div>
              )}
              {issue.suggestion && (
                <div className="issue-card__row">
                  <span className="issue-card__row-label">Fix</span>
                  <span className="issue-card__suggestion">{issue.suggestion}</span>
                </div>
              )}
              {issue.explanation && (
                <div className="issue-card__row">
                  <span className="issue-card__row-label">Why</span>
                  <span className="issue-card__why">{issue.explanation}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
