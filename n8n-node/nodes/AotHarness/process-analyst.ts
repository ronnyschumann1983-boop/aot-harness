/**
 * process-analyst.ts — v0.5.0
 *
 * Process Analyst Worker.
 * Turns unstructured operational input (email, support case, document excerpt,
 * automotive service request, internal note) into a structured next-step
 * decision payload for n8n workflows.
 *
 * Worker is read-only by design: it returns analysis + a draft response, but
 * never sends, mutates or finalizes anything. Human-in-the-Loop is part of
 * the contract.
 */

export type ProcessProfile =
  | 'generic'
  | 'email_support'
  | 'document_intake'
  | 'automotive_service';

export type AnalysisLanguage = 'de' | 'en';

export interface ProcessAnalysisResult {
  process_type:                string;
  business_area:               string;
  summary:                     string;
  detected_entities:           Record<string, string | null>;
  urgency:                     'low' | 'medium' | 'high' | 'unknown';
  confidence:                  number;
  missing_information:         string[];
  next_best_action:            string;
  automation_potential:        'low' | 'medium' | 'high' | 'unknown';
  human_review_required:       boolean;
  risk_flags:                  string[];
  recommended_workflow_tags:   string[];
  draft_response:              string | null;
  /** Optional metadata added by the post-processor for transparency. */
  _profile?:                   ProcessProfile;
  _trigger_reasons?:           string[];
}

const PROFILE_FOCUS: Record<ProcessProfile, string> = {
  generic:
    'General operational case. Stay branch-neutral. Classify the type of process and identify the next sensible step.',
  email_support:
    'Customer support email. Focus on: customer concern, urgency, missing info, escalation need, support category, and a polite draft reply.',
  document_intake:
    'Inbound document/form. Focus on: document type, mandatory fields detected, missing fields, plausibility, extraction hints, next processing step.',
  automotive_service:
    'Workshop / car dealership case. Focus on: vehicle (make, model), license_plate, requested_date, service topic, urgency, callback need, missing vehicle info, and the next workshop process step.',
};

const PROFILE_ENTITY_HINTS: Record<ProcessProfile, string[]> = {
  generic:
    ['customer_name', 'company', 'email', 'phone', 'topic', 'requested_date'],
  email_support:
    ['customer_name', 'company', 'email', 'phone', 'topic', 'support_category', 'order_id'],
  document_intake:
    ['document_type', 'sender_name', 'company', 'date', 'reference_id', 'amount'],
  automotive_service:
    ['customer_name', 'company', 'email', 'phone', 'vehicle', 'license_plate', 'requested_date', 'topic'],
};

/**
 * Build the analyst prompt. Profile-specific focus + JSON-only contract.
 * The model is instructed to emit ONLY the structured JSON payload.
 */
export function PROCESS_ANALYST_PROMPT(
  input:                 string,
  profile:               ProcessProfile,
  language:              AnalysisLanguage,
  humanReviewThreshold:  number,
  includeDraftResponse:  boolean,
): string {
  const focus  = PROFILE_FOCUS[profile];
  const hints  = PROFILE_ENTITY_HINTS[profile].join(', ');
  const langName = language === 'de' ? 'German' : 'English';

  const draftRule = includeDraftResponse
    ? `Provide a polite, professional "draft_response" in ${langName}, addressed to the originator. ` +
      `If essential information is missing, the draft must be a follow-up question that asks for it — do not invent details.`
    : `Set "draft_response" to null. Do not generate a reply.`;

  return `You are a Process Analyst. Analyze ONE operational case and return a single valid JSON object — no markdown fences, no commentary before or after.

Profile: ${profile}
Focus: ${focus}

Output language for "summary", "next_best_action", "draft_response", "missing_information" and "risk_flags": ${langName}.
Field names and enum values stay in English.

Required entity hints for this profile (use null when not present): ${hints}.
You may add other entities you find. Never fabricate values — if unsure, leave the field null and add a missing_information note.

Hard rules:
- Only state facts that are present in the input.
- Every gap (missing fact, unclear date, ambiguous wish) goes into "missing_information".
- Anything legal, monetary, contractual, safety-relevant or with unclear customer identity → add to "risk_flags".
- "human_review_required" must be true whenever confidence < ${humanReviewThreshold}, when missing_information is non-empty, or when any risk_flags exist.
- "automation_potential" reflects how cleanly the next step can be executed without a human (low / medium / high / unknown).
- "urgency" must be one of: low | medium | high | unknown.
- "confidence" is a number 0.0–1.0 reflecting how sure you are about the classification + entities.
- ${draftRule}

OUTPUT FORMAT (raw JSON only, exact keys):
{
  "process_type": "string (e.g. terminanfrage, schadenmeldung, rechnungseingang)",
  "business_area": "string (e.g. service, sales, support, finance, intake)",
  "summary": "string (1–2 sentences)",
  "detected_entities": { "customer_name": null, "company": null, "email": null, "phone": null, "topic": null },
  "urgency": "low|medium|high|unknown",
  "confidence": 0.0,
  "missing_information": [],
  "next_best_action": "string",
  "automation_potential": "low|medium|high|unknown",
  "human_review_required": false,
  "risk_flags": [],
  "recommended_workflow_tags": [],
  "draft_response": ${includeDraftResponse ? '"string"' : 'null'}
}

Operational case to analyze:
"""
${input}
"""`;
}

/**
 * Deterministic post-processor — never trust the model alone.
 *
 * Forces human_review_required = true whenever:
 *  - confidence falls below the configured threshold
 *  - missing_information is non-empty
 *  - any risk_flags are present
 *  - input is too short to be reliable
 *
 * Also normalizes enum values and clamps confidence to [0, 1].
 */
export function applyHumanReviewLogic(
  raw:                  Partial<ProcessAnalysisResult>,
  inputLength:          number,
  humanReviewThreshold: number,
  profile:              ProcessProfile,
  includeDraftResponse: boolean,
): ProcessAnalysisResult {
  const triggers: string[] = [];

  const confidence = clamp01(toNumber(raw.confidence, 0.5));
  const missing    = Array.isArray(raw.missing_information) ? raw.missing_information.filter(isNonEmptyString) : [];
  const flags      = Array.isArray(raw.risk_flags)          ? raw.risk_flags.filter(isNonEmptyString)          : [];
  const tags       = Array.isArray(raw.recommended_workflow_tags) ? raw.recommended_workflow_tags.filter(isNonEmptyString) : [];

  if (confidence < humanReviewThreshold) triggers.push(`confidence ${confidence.toFixed(2)} < threshold ${humanReviewThreshold}`);
  if (missing.length > 0)                triggers.push(`${missing.length} missing fact(s)`);
  if (flags.length > 0)                  triggers.push(`${flags.length} risk flag(s)`);
  if (inputLength < 20)                  triggers.push('input too short to be reliable (<20 chars)');

  const humanReview = triggers.length > 0 || raw.human_review_required === true;
  if (humanReview && !tags.includes('human_review')) tags.push('human_review');

  return {
    process_type:               isNonEmptyString(raw.process_type)      ? raw.process_type      : 'unknown',
    business_area:              isNonEmptyString(raw.business_area)     ? raw.business_area     : 'unknown',
    summary:                    isNonEmptyString(raw.summary)           ? raw.summary           : '',
    detected_entities:          isObject(raw.detected_entities)         ? raw.detected_entities as Record<string, string | null> : {},
    urgency:                    normalizeUrgency(raw.urgency),
    confidence,
    missing_information:        missing,
    next_best_action:           isNonEmptyString(raw.next_best_action)  ? raw.next_best_action  : 'Manual triage required.',
    automation_potential:       normalizeAutomation(raw.automation_potential),
    human_review_required:      humanReview,
    risk_flags:                 flags,
    recommended_workflow_tags:  tags,
    draft_response:             includeDraftResponse
                                  ? (isNonEmptyString(raw.draft_response) ? raw.draft_response : null)
                                  : null,
    _profile:                   profile,
    _trigger_reasons:           triggers,
  };
}

/** Fallback used when the LLM output cannot be parsed at all. */
export function emptyAnalysis(profile: ProcessProfile, includeDraftResponse: boolean): ProcessAnalysisResult {
  return {
    process_type:              'unknown',
    business_area:             'unknown',
    summary:                   '',
    detected_entities:         {},
    urgency:                   'unknown',
    confidence:                0,
    missing_information:       ['analysis output could not be parsed'],
    next_best_action:          'Manual triage required — analyst output was not valid JSON.',
    automation_potential:      'unknown',
    human_review_required:     true,
    risk_flags:                ['parser_error'],
    recommended_workflow_tags: ['human_review', 'parser_error'],
    draft_response:            includeDraftResponse ? null : null,
    _profile:                  profile,
    _trigger_reasons:          ['parser_error'],
  };
}

// ── helpers ────────────────────────────────────────────────────────────────

function isNonEmptyString(v: unknown): v is string {
  return typeof v === 'string' && v.trim().length > 0;
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function toNumber(v: unknown, fallback: number): number {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

function clamp01(n: number): number {
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

function normalizeUrgency(v: unknown): ProcessAnalysisResult['urgency'] {
  const s = typeof v === 'string' ? v.toLowerCase() : '';
  if (s === 'low' || s === 'medium' || s === 'high') return s;
  return 'unknown';
}

function normalizeAutomation(v: unknown): ProcessAnalysisResult['automation_potential'] {
  const s = typeof v === 'string' ? v.toLowerCase() : '';
  if (s === 'low' || s === 'medium' || s === 'high') return s;
  return 'unknown';
}
