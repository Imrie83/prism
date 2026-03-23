import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

function easeOutExpo(t) { return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); }
function easeOutBack(t) { const c1 = 1.70158,c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1,3) + c1 * Math.pow(t - 1,2); }

function useCountUp(target, duration = 1400, delay = 150) {
  const [value, setValue] = useState(0);
  const raf = useRef(null);
  useEffect(() => {
    setValue(0);
    const timeout = setTimeout(() => {
      let start = null;
      function tick(ts) {
        if (!start) start = ts;
        const elapsed = ts - start;
        const progress = Math.min(elapsed / duration, 1);
        setValue(Math.round(easeOutExpo(progress) * target));
        if (progress < 1) raf.current = requestAnimationFrame(tick);
      }
      raf.current = requestAnimationFrame(tick);
    }, delay);
    return () => { clearTimeout(timeout); if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target, duration, delay]);
  return value;
}

const scoreColor = (s) => s >= 75 ? "var(--green)" : s >= 45 ? "var(--yellow)" : "var(--red)";
const scoreRgba = (s) => s >= 75 ? "rgba(52,211,153,0.55)" : s >= 45 ? "rgba(251,191,36,0.55)" : "rgba(248,113,113,0.55)";

// Spark particles that burst out when score finishes counting
function Sparks({ active, color, size }) {
  if (!active) return null;
  const count = 10;
  return (
    <AnimatePresence>
      {Array.from({ length: count }).map((_, i) => {
        const angle = (i / count) * 2 * Math.PI;
        const dist = size * 0.6 + Math.random() * size * 0.25;
        const tx = Math.cos(angle) * dist;
        const ty = Math.sin(angle) * dist;
        const delay = 0.9 + i * 0.03;
        return (
          <motion.div key={i}
            initial={{ opacity: 1, x: 0, y: 0, scale: 1 }}
            animate={{ opacity: 0, x: tx, y: ty, scale: 0 }}
            exit={{}}
            transition={{ duration: 0.55, delay, ease: "easeOut" }}
            style={{
              position: "absolute",
              top: "50%", left: "50%",
              width: 4, height: 4,
              borderRadius: "50%",
              background: color,
              boxShadow: `0 0 6px ${color}`,
              marginTop: -2, marginLeft: -2,
              pointerEvents: "none",
              zIndex: 3,
            }}
          />
        );
      })}
    </AnimatePresence>
  );
}

export default function ScoreRing({ score, size = 110 }) {
  const stroke = Math.max(size * 0.065, 6);
  const radius = size / 2 - stroke - 2;
  const circ = 2 * Math.PI * radius;
  const color = scoreColor(score);
  const glow = scoreRgba(score);
  const filterId = `glow-${size}-${Math.round(score)}`;

  const displayed = useCountUp(score, 1300, 220);
  const offset = circ - (displayed / 100) * circ;
  const done = displayed >= score && score > 0;

  // Tip dot position
  const tipAngle = (2 * Math.PI * (displayed / 100)) - Math.PI / 2;
  const tipX = size / 2 + radius * Math.cos(tipAngle);
  const tipY = size / 2 + radius * Math.sin(tipAngle);

  return (
    <div className="score-ring" style={{ width: size, height: size }}>

      {/* Breathing radial glow */}
      <motion.div
        initial={{ opacity: 0, scale: 0.7 }}
        animate={{ opacity: [0.15, 0.5, 0.15], scale: [0.85, 1.08, 0.85] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut", delay: 0.8 }}
        style={{
          position: "absolute", inset: 0, borderRadius: "50%", pointerEvents: "none",
          background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
        }}
      />

      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}
        style={{ position: "relative", zIndex: 1, overflow: "visible" }}>
        <defs>
          <filter id={filterId} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <linearGradient id={`grad-${filterId}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.6" />
          </linearGradient>
        </defs>

        {/* Outer glow ring */}
        <circle cx={size / 2} cy={size / 2} r={radius + stroke * 0.6}
          fill="none" stroke={color} strokeWidth={1} opacity={0.12} />

        {/* Background track */}
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--border)" strokeWidth={stroke} />

        {/* Shimmer tick marks */}
        {Array.from({ length: 20 }).map((_, i) => {
          const a = (i / 20) * 2 * Math.PI - Math.PI / 2;
          const r1 = radius - stroke / 2 - 1;
          const r2 = radius + stroke / 2 + 1;
          return (
            <line key={i}
              x1={size / 2 + r1 * Math.cos(a)} y1={size / 2 + r1 * Math.sin(a)}
              x2={size / 2 + r2 * Math.cos(a)} y2={size / 2 + r2 * Math.sin(a)}
              stroke="var(--bg)" strokeWidth={1.5} opacity={0.5}
            />
          );
        })}

        {/* Main arc */}
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={`url(#grad-${filterId})`}
          strokeWidth={stroke}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `url(#${filterId}) drop-shadow(0 0 6px ${glow})` }}
          initial={{ strokeDashoffset: circ, opacity: 0 }}
          animate={{ strokeDashoffset: offset, opacity: 1 }}
          transition={{ duration: 1.4, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        />

        {/* Glowing tip dot */}
        <motion.circle
          r={stroke * 0.7}
          fill={color}
          cx={tipX} cy={tipY}
          style={{ filter: `drop-shadow(0 0 5px ${glow})` }}
          initial={{ opacity: 0, r: 0 }}
          animate={{ opacity: 1, r: stroke * 0.7, cx: tipX, cy: tipY }}
          transition={{ duration: 1.4, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        />

        {/* Pulse ring at completion */}
        {done && (
          <motion.circle
            cx={size / 2} cy={size / 2} r={radius}
            fill="none" stroke={color} strokeWidth={stroke * 0.4}
            initial={{ opacity: 0.6, scale: 1 }}
            animate={{ opacity: 0, scale: 1.3 }}
            style={{ transformOrigin: `${size / 2}px ${size / 2}px` }}
            transition={{ duration: 0.8, delay: 0 }}
          />
        )}
      </svg>

      {/* Spark burst */}
      <Sparks active={done} color={color} size={size} />

      {/* Centre label */}
      <div className="score-ring__label" style={{ zIndex: 2 }}>
        <motion.span
          className="score-ring__number"
          style={{ color, fontSize: size * 0.25, letterSpacing: "-1.5px", fontWeight: 800 }}
          initial={{ opacity: 0, scale: 0.3, filter: "blur(10px)" }}
          animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          transition={{ duration: 0.55, delay: 0.22, type: "spring", stiffness: 280, damping: 20 }}
        >
          {displayed}
        </motion.span>
        <motion.span className="score-ring__sub"
          initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.3 }}>
          /100
        </motion.span>
      </div>
    </div>
  );
}
