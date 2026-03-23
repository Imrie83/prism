import { motion } from "framer-motion";
import { Zap } from "lucide-react";
import { useSettingsStore } from "../stores/settingsStore";

function formatCost(usd) {
  if (usd <= 0) return null;
  if (usd < 0.001) return "< $0.001";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

export default function TokenBadge({ tokens, label = "", costType = "audit" }) {
  // costType: "audit" uses Haiku rates, "email" uses Sonnet rates
  const auditIn = useSettingsStore(s => s.auditInputCostPer1M);
  const auditOut = useSettingsStore(s => s.auditOutputCostPer1M);
  const emailIn = useSettingsStore(s => s.emailInputCostPer1M);
  const emailOut = useSettingsStore(s => s.emailOutputCostPer1M);
  const inputCost = costType === "email" ? emailIn : auditIn;
  const outputCost = costType === "email" ? emailOut : auditOut;

  if (!tokens?.total_tokens) return null;

  const promptT = tokens.prompt_tokens ?? 0;
  const completionT = tokens.completion_tokens ?? 0;
  const total = tokens.total_tokens;
  const model = tokens.model || "";
  const genCount = tokens.generationCount;

  const costUsd = (promptT / 1_000_000) * inputCost + (completionT / 1_000_000) * outputCost;
  const showCost = inputCost > 0 || outputCost > 0;
  const cost = showCost ? formatCost(costUsd) : null;

  const tooltip = [
    genCount > 1 ? `${genCount} generations combined` : null,
    `${promptT.toLocaleString()} prompt + ${completionT.toLocaleString()} completion = ${total.toLocaleString()} tokens`,
    model ? `Model: ${model}` : null,
    cost ? `Est. cost: ${cost} (input $${inputCost}/1M · output $${outputCost}/1M)` : null,
  ].filter(Boolean).join("\n");

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.4 }}
      title={tooltip}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        fontSize: 10, fontFamily: "var(--font-mono)",
        color: "var(--ink3)", padding: "3px 8px",
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 99, cursor: "help", userSelect: "none",
      }}
    >
      <Zap size={9} style={{ color: "var(--yellow)", flexShrink: 0 }} />
      {total.toLocaleString()}t
      {genCount > 1 && (
        <span style={{ opacity: 0.6 }}>×{genCount}</span>
      )}
      {cost && (
        <span style={{ borderLeft: "1px solid var(--border)", paddingLeft: 5, marginLeft: 2 }}>
          {cost}
        </span>
      )}
      {label && <span style={{ opacity: 0.5 }}>· {label}</span>}
    </motion.div>
  );
}
