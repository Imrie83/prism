import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const SEV_META = {
  high:   { label: "High",   cls: "sev-counts__item--high",   bar: "var(--red)",    glow: "rgba(248,113,113,0.15)" },
  medium: { label: "Medium", cls: "sev-counts__item--medium", bar: "var(--yellow)", glow: "rgba(251,191,36,0.12)" },
  low:    { label: "Low",    cls: "sev-counts__item--low",    bar: "var(--green)",  glow: "rgba(52,211,153,0.1)" },
};

export default function IssueCard({ issue, defaultOpen = false, index = 0 }) {
  const [open, setOpen] = useState(defaultOpen);
  const sev  = SEV_META[issue.severity] || SEV_META.low;
  const type = (issue.type || "unknown").replace(/_/g, " ");

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
