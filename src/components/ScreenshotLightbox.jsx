import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ExternalLink } from "lucide-react";

export default function ScreenshotLightbox({ src, url, onClose }) {
  // Close on Escape
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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
            background: "rgba(0,0,0,0.85)",
            backdropFilter: "blur(8px)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: 32,
          }}
        >
          <motion.div
            initial={{ scale: 0.88, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.92, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            onClick={e => e.stopPropagation()}
            style={{
              position: "relative",
              maxWidth: "90vw",
              maxHeight: "88vh",
              borderRadius: 12,
              overflow: "hidden",
              boxShadow: "0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(77,184,255,0.2)",
            }}
          >
            <img
              src={`data:image/jpeg;base64,${src}`}
              alt="Page screenshot"
              style={{
                display: "block",
                maxWidth: "90vw",
                maxHeight: "88vh",
                objectFit: "contain",
              }}
            />

            {/* Top bar */}
            <div style={{
              position: "absolute", top: 0, left: 0, right: 0,
              padding: "10px 14px",
              background: "linear-gradient(180deg, rgba(0,0,0,0.7) 0%, transparent 100%)",
              display: "flex", alignItems: "center", gap: 10,
            }}>
              {url && (
                <a href={url} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize:11, color:"rgba(255,255,255,0.7)", fontFamily:"var(--font-mono)",
                    flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
                    display:"flex", alignItems:"center", gap:4, textDecoration:"none" }}>
                  {url} <ExternalLink size={10} />
                </a>
              )}
              <button onClick={onClose}
                style={{ background:"rgba(255,255,255,0.1)", border:"none", borderRadius:6,
                  padding:"5px 8px", cursor:"pointer", color:"#fff", display:"flex" }}>
                <X size={15} />
              </button>
            </div>

            {/* Bottom hint */}
            <div style={{
              position: "absolute", bottom: 0, left: 0, right: 0,
              padding: "20px 14px 10px",
              background: "linear-gradient(0deg, rgba(0,0,0,0.6) 0%, transparent 100%)",
              fontSize: 11, color: "rgba(255,255,255,0.45)", textAlign: "center",
            }}>
              Click outside or press Esc to close
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
