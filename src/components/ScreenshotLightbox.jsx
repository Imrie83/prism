import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ExternalLink } from "lucide-react";

export default function ScreenshotLightbox({ src, url, onClose }) {
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    // Prevent body scroll while lightbox is open
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <AnimatePresence>
      {src && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onClose}
          style={{
            position: "fixed", inset: 0, zIndex: 200,
            background: "rgba(0,0,0,0.88)",
            backdropFilter: "blur(8px)",
            overflowY: "auto",
            padding: "32px",
          }}
        >
          {/* Sticky top bar — sticky to the scrollable overlay, not the image container */}
          <div style={{
            position: "sticky", top: 0, zIndex: 10,
            display: "flex", alignItems: "center", gap: 10,
            padding: "8px 12px", marginBottom: 8,
            background: "rgba(0,0,0,0.7)",
            backdropFilter: "blur(6px)",
            borderRadius: 8,
            maxWidth: "min(90vw, 1280px)",
            marginInline: "auto",
          }}
            onClick={e => e.stopPropagation()}>
            {url && (
              <a href={url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", fontFamily: "var(--font-mono)",
                  flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  display: "flex", alignItems: "center", gap: 4, textDecoration: "none" }}>
                {url} <ExternalLink size={10} />
              </a>
            )}
            <span style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", whiteSpace: "nowrap" }}>
              scroll to see full page · esc to close
            </span>
            <button onClick={onClose}
              style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 6,
                padding: "5px 8px", cursor: "pointer", color: "#fff", display: "flex", flexShrink: 0 }}>
              <X size={15} />
            </button>
          </div>

          {/* Image — no overflow:hidden, full natural height */}
          <motion.div
            initial={{ scale: 0.94, opacity: 0, y: 16 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            onClick={e => e.stopPropagation()}
            style={{
              width: "min(90vw, 1280px)",
              marginInline: "auto",
              borderRadius: 10,
              boxShadow: "0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(77,184,255,0.2)",
              overflow: "visible",
            }}
          >
            <img
              src={`data:image/jpeg;base64,${src}`}
              alt="Page screenshot"
              style={{ display: "block", width: "100%", height: "auto", borderRadius: 10 }}
            />
          </motion.div>
          {/* Bottom padding so last bit of image isn't flush against viewport edge */}
          <div style={{ height: 32 }} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
