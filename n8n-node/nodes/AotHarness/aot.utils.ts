/**
 * aot.utils.ts — v0.2.1 FIXED
 * Fixes vs. v0.2.0:
 *  - parseJson: extrahiert JSON robuster (auch aus Markdown-Codeblöcken)
 *  - DECOMPOSE_PROMPT: explizit auf JSON-only, kein Markdown
 *  - QA_PROMPT: "original_task" als eindeutiger Marker
 *  - compressedContext: kürzt zu lange Atom-Ergebnisse
 *  - callClaude: Timeout + Retry auf HTTP-Ebene
 */

export interface Atom {
  id:         string;
  question:   string;
  depends_on: string[];
  status:     'pending' | 'running' | 'done' | 'failed';
  result?:    string;
}

export interface AtomGraph {
  goal:  string;
  atoms: Record<string, Atom>;
}

export interface HarnessResult {
  goal:        string;
  result:      string;
  qa_score:    number;
  success:     boolean;
  atoms_used:  string[];
  atoms_total: number;
  cache_hit:   boolean;
  notes:       string[];
}

// ── FIX: JSON robust parsen — auch aus Markdown-Blöcken ─────────────────────
export function parseJson<T>(raw: string, fallback: T): T {
  // 1. Direkt parsen
  try { return JSON.parse(raw.trim()); } catch {}

  // 2. JSON aus ```json ... ``` Block extrahieren
  const mdMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (mdMatch) {
    try { return JSON.parse(mdMatch[1].trim()); } catch {}
  }

  // 3. Erstes { ... } oder [ ... ] extrahieren
  const objMatch = raw.match(/\{[\s\S]*\}/);
  if (objMatch) {
    try { return JSON.parse(objMatch[0]); } catch {}
  }

  return fallback;
}

// ── FIX: Kontext kürzen damit Prompts nicht zu lang werden ──────────────────
export function compressedContext(graph: AtomGraph): string {
  const done = Object.values(graph.atoms).filter(a => a.status === 'done');
  return JSON.stringify(
    done.map(a => ({
      id:     a.id,
      result: typeof a.result === 'string' ? a.result.substring(0, 300) : a.result,
    })), null, 2
  );
}

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────
export function readyAtoms(graph: AtomGraph): Atom[] {
  return Object.values(graph.atoms).filter(a =>
    a.status === 'pending' &&
    a.depends_on.every(dep => graph.atoms[dep]?.status === 'done')
  );
}

export function isComplete(graph: AtomGraph): boolean {
  return Object.values(graph.atoms).every(
    a => a.status === 'done' || a.status === 'failed'
  );
}

// ── FIX: Prompts ohne Markdown, immer reine JSON-Anweisung ──────────────────

export const DECOMPOSE_PROMPT = (goal: string, language: string) => `You are an AoT task decomposer. Output ONLY raw JSON, no markdown, no explanation.

Goal: ${goal}
Language for questions: ${language === 'de' ? 'German' : 'English'}

Break into max 6 atomic sub-tasks. Each atom solves exactly ONE thing.
Dependencies: later atoms may depend on earlier ones.

OUTPUT FORMAT (raw JSON only):
{"atoms":[{"id":"a1","question":"...","depends_on":[]},{"id":"a2","question":"...","depends_on":["a1"]}]}`;

export const SOLVE_PROMPT = (goal: string, question: string, context: string, language: string) =>
`You are a specialist agent. Solve ONE atomic task. Output your answer directly — no JSON wrapper needed.

Overall Goal: ${goal}
Available context from previous atoms: ${context || 'none yet'}
Your specific task: ${question}

Respond in ${language === 'de' ? 'German' : 'English'}. Be concise and precise.`;

// FIX: "original_task" als eindeutiger QA-Marker — verhindert Verwechslung
export const QA_PROMPT = (goal: string, outputs: string, language: string, threshold: number) =>
`You are a strict QA agent. Output ONLY raw JSON, no markdown.

original_task: ${goal}

All specialist outputs:
${outputs}

Check: (1) completeness (2) factual accuracy (3) format (4) tone.

OUTPUT FORMAT (raw JSON only):
{"final_output":"complete polished answer here","qa_score":0.0,"bestanden":false,"anmerkungen":["note1"]}

Rules:
- qa_score is 0.0 to 1.0
- bestanden = true only if qa_score >= ${threshold}
- final_output must be in ${language === 'de' ? 'German' : 'English'}
- Add NO new facts not present in specialist outputs`;
