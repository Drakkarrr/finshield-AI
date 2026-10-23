import { Badge } from '@/components/ui';
import { formatPercent, riskLevel } from '@/lib/format';

/** Risk score as number + worded level ("62% · Medium"); colour only reinforces the words. */
export default function RiskScore({ score, digits = 0 }: { score: number; digits?: number }) {
  const level = riskLevel(score);
  return (
    <Badge tone={level.tone}>
      <span className="font-mono">{formatPercent(score, digits)}</span>
      <span>· {level.label}</span>
    </Badge>
  );
}
