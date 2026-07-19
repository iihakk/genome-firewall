/** Domain types.
 *
 * Deliberately mirrors how a laboratory actually thinks: a *specimen* is
 * accessioned, analysed, reviewed by a named person, released, and later
 * reconciled against the culture result that eventually arrives.
 */

export type Call = "RESISTANT" | "SUSCEPTIBLE" | "INDETERMINATE";

/** Why the firewall declined to answer. Four gates, see pipeline/firewall.py. */
export type DeferReason =
  | "confidence"
  | "unrecognised machinery"
  | "sparse genome"
  | "incoherent with profile";

export interface Evidence {
  token: string;
  gene: string;
  mechanism: string | null;
  clinical: string;
  contribution: number;
  present: boolean;
  /** Mutations and truncations are invisible to gene-presence lookup tools. */
  invisibleToLookup: boolean;
}

export interface InvestigativeLead {
  likelyMechanism: string;
  drugClassesAtRisk: string[];
  confidence: number;
  recommendedAction: string;
  reasoning: string;
}

export interface DrugResult {
  drug: string;
  call: Call;
  probability: number;
  reason: string | null;
  /** What a ResFinder/PointFinder-style genotype lookup would report. */
  lookupSays: Call | null;
  /** Lookup reports susceptible; the isolate is resistant. The error that kills. */
  lookupDangerouslyWrong: boolean;
  evidence: Evidence[];
  lead?: InvestigativeLead;
  /** Culture AST once it arrives, for reconciliation. */
  cultureResult?: "Resistant" | "Susceptible" | null;
  /** Laboratory ground truth where known, shown on reconciled specimens. */
  truth?: string | null;
  /** Reviewer changed the call, with a mandatory reason. */
  override?: { to: Call; reason: string; by: string; at: string } | null;
}

export type SpecimenStatus = "analysing" | "review" | "released" | "reconciled";
export type Priority = "urgent" | "routine";

export interface Specimen {
  id: string;
  accession: string;
  organism: string;
  source: string;
  priority: Priority;
  status: SpecimenStatus;
  receivedAt: string;
  collectedAt: string;
  requestedBy: string;
  ward: string;
  patientRef: string;
  genomeId: string;
  determinants: string[];
  drugs: DrugResult[];
  /** Audit trail. Every state change is recorded; nothing is silently mutated. */
  audit: AuditEntry[];
  releasedBy?: string | null;
  releasedAt?: string | null;
}

export interface AuditEntry {
  at: string;
  who: string;
  action: string;
  detail?: string;
}

export interface ValidationSummary {
  mean: Record<string, number | null>;
  rule: {
    mean_rule: number;
    mean_model: number;
    mean_gain: number;
    wins: number;
    ties: number;
    losses: number;
  };
}

export interface Thresholds {
  abstainLow: number;
  abstainHigh: number;
  /** Unrecognised machinery blocks a SUSCEPTIBLE call at any confidence. */
  noveltyBlocksSusceptible: boolean;
  sparseGate: boolean;
  coherenceGate: boolean;
}

export const DEFAULT_THRESHOLDS: Thresholds = {
  abstainLow: 0.35,
  abstainHigh: 0.65,
  noveltyBlocksSusceptible: true,
  sparseGate: true,
  coherenceGate: true,
};

/** Drugs excluded from clinical use, with the measured reason. */
export const EXCLUDED_DRUGS: Record<string, string> = {
  colistin:
    "Loses to the rule baseline (−0.064) and scores at chance (0.500) cross-species. Not approved for use.",
  cefepime: "Marginally below the rule baseline (−0.023). Interpret with caution.",
};
