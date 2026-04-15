import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

import {
  AtomGraph,
  HarnessResult,
  DECOMPOSE_PROMPT,
  SOLVE_PROMPT,
  QA_PROMPT,
  parseJson,
  readyAtoms,
  isComplete,
  compressedContext,
} from './aot.utils';

export class AotHarness implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'AoT Harness',
    name:        'aotHarness',
    icon:        'fa:brain',
    group:       ['transform'],
    version:     1,
    subtitle:    '={{$parameter["goal"].substring(0,45)}}...',
    description: 'CHIP + Atom of Thoughts (AoT) — löst komplexe Tasks automatisch mit Spezialisten + QA',
    defaults:    { name: 'AoT Harness' },
    inputs:      ['main'],
    outputs:     ['main'],
    credentials: [{ name: 'aotHarnessApi', required: true }],

    properties: [
      {
        displayName: 'Goal (Task)',
        name:        'goal',
        type:        'string',
        typeOptions: { rows: 3 },
        default:     '',
        required:    true,
        placeholder: 'Erstelle IDD-Dokumentation fuer Kunde Mustermann, 42J., Haftpflicht',
        description: 'Was soll das System erledigen? Ein natuerlicher Satz genuegt.',
      },
      {
        displayName: 'Modus',
        name:        'mode',
        type:        'options',
        options: [
          { name: 'CHIP + AoT (vollstaendig)',    value: 'chip',    description: 'AoT + Spezialisten + QA — beste Qualitaet' },
          { name: 'AoT Direkt (schnell)',          value: 'aot',     description: 'Nur AoT ohne Spezialisierung' },
          { name: 'Webhook (Python-Server)',        value: 'webhook', description: 'Ruft laufenden aot-harness Server auf' },
        ],
        default: 'chip',
      },
      {
        displayName: 'Webhook URL',
        name:        'webhookUrl',
        type:        'string',
        default:     'http://localhost:8765/run',
        displayOptions: { show: { mode: ['webhook'] } },
      },
      {
        displayName: 'Optionen',
        name:        'advanced',
        type:        'collection',
        placeholder: 'Option hinzufuegen',
        default:     {},
        options: [
          {
            displayName: 'QA-Schwellenwert',
            name:        'qaThreshold',
            type:        'number',
            typeOptions: { minValue: 0, maxValue: 1, numberStepSize: 0.05 },
            default:     0.75,
            description: 'Mindest-Score — darunter gilt Task als fehlgeschlagen',
          },
          {
            displayName: 'Max. Atoms',
            name:        'maxAtoms',
            type:        'number',
            default:     6,
          },
          {
            displayName: 'Max. Tokens pro Atom',
            name:        'maxTokens',
            type:        'number',
            default:     1500,
          },
          {
            displayName: 'QA Retry bei Score < Schwellenwert',
            name:        'qaRetry',
            type:        'boolean',
            default:     true,
            description: 'Wenn aktiviert: bei niedrigem Score nochmal versuchen',
          },
          {
            displayName: 'Ausgabe-Sprache',
            name:        'language',
            type:        'options',
            options: [
              { name: 'Deutsch', value: 'de' },
              { name: 'Englisch', value: 'en' },
            ],
            default: 'de',
          },
        ],
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items   = this.getInputData();
    const results: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      const goal      = this.getNodeParameter('goal', i) as string;
      const mode      = this.getNodeParameter('mode', i) as string;
      const advanced  = this.getNodeParameter('advanced', i) as Record<string, unknown>;
      const creds     = await this.getCredentials('aotHarnessApi');

      const apiKey      = creds.apiKey as string;
      const model       = (creds.model as string) || 'claude-sonnet-4-5';
      const maxTokens   = (advanced.maxTokens   as number)  ?? 1500;
      const qaThreshold = (advanced.qaThreshold as number)  ?? 0.75;
      const qaRetry     = (advanced.qaRetry     as boolean) ?? true;
      const language    = (advanced.language    as string)  ?? 'de';

      // ── Claude API Helper ──────────────────────────────────────────────────
      const callClaude = async (prompt: string): Promise<string> => {
        const resp = await this.helpers.request({
          method: 'POST',
          url:    'https://api.anthropic.com/v1/messages',
          headers: {
            'x-api-key':         apiKey,
            'anthropic-version': '2023-06-01',
            'content-type':      'application/json',
          },
          json: true,
          body: {
            model,
            max_tokens: maxTokens,
            system:     'You are a precise AI agent. When asked for JSON, output ONLY raw valid JSON — no markdown fences, no explanation before or after.',
            messages:   [{ role: 'user', content: prompt }],
          },
        });
        return (resp as { content: Array<{ text: string }> }).content[0].text.trim();
      };

      let harnessResult: HarnessResult;

      // ── Webhook-Modus ──────────────────────────────────────────────────────
      if (mode === 'webhook') {
        const url = this.getNodeParameter('webhookUrl', i) as string;
        const resp = await this.helpers.request({ method: 'POST', url, json: true, body: { goal } });
        harnessResult = resp as HarnessResult;

      } else {
        // ── AoT Decomposition ──────────────────────────────────────────────
        const decomposeRaw  = await callClaude(DECOMPOSE_PROMPT(goal, language));
        const decomposeData = parseJson<{ atoms: Array<{ id: string; question: string; depends_on: string[] }> }>(
          decomposeRaw, { atoms: [] }
        );

        // Fallback: mindestens 1 Atom wenn Parsing fehlschlägt
        if (!decomposeData.atoms.length) {
          decomposeData.atoms = [{ id: 'a1', question: goal, depends_on: [] }];
        }

        const graph: AtomGraph = { goal, atoms: {} };
        for (const a of decomposeData.atoms) {
          graph.atoms[a.id] = { ...a, status: 'pending' };
        }

        // ── Atoms lösen ────────────────────────────────────────────────────
        const specialistOutputs: Record<string, string> = {};
        let rounds = 0;
        const maxRounds = Object.keys(graph.atoms).length * 4;

        while (!isComplete(graph) && rounds < maxRounds) {
          rounds++;
          const ready = readyAtoms(graph);
          if (!ready.length) break;

          for (const atom of ready) {
            atom.status = 'running';
            const ctx = compressedContext(graph);
            try {
              const raw    = await callClaude(SOLVE_PROMPT(goal, atom.question, ctx, language));
              atom.result  = raw;
              atom.status  = 'done';
              specialistOutputs[atom.id] = raw;
            } catch {
              atom.status = 'failed';
            }
          }
        }

        // ── QA — mit optionalem Retry ─────────────────────────────────────
        const allOutputs = JSON.stringify(specialistOutputs, null, 2);
        let qaData = { final_output: '', qa_score: 0, bestanden: false, anmerkungen: [] as string[] };
        let attempts = qaRetry ? 2 : 1;

        while (attempts > 0) {
          const qaRaw = await callClaude(QA_PROMPT(goal, allOutputs, language, qaThreshold));
          const parsed = parseJson<typeof qaData>(qaRaw, {
            final_output: allOutputs,
            qa_score:     0.5,
            bestanden:    false,
            anmerkungen:  ['QA parse error — raw: ' + qaRaw.substring(0, 100)],
          });
          qaData = parsed;
          if (qaData.bestanden || !qaRetry) break;
          attempts--;
        }

        // Fallback: wenn final_output leer ist, kombiniere alle Atom-Ergebnisse
        if (!qaData.final_output || qaData.final_output.length < 10) {
          qaData.final_output = Object.values(specialistOutputs).join('\n\n');
          qaData.qa_score     = qaData.qa_score || 0.6;
        }

        harnessResult = {
          goal,
          result:      qaData.final_output,
          qa_score:    qaData.qa_score,
          success:     qaData.bestanden && qaData.qa_score >= qaThreshold,
          atoms_used:  Object.keys(graph.atoms).filter(k => graph.atoms[k].status === 'done'),
          atoms_total: Object.keys(graph.atoms).length,
          cache_hit:   false,
          notes:       qaData.anmerkungen || [],
        };
      }

      results.push({
        json: {
          ...harnessResult,
          output:     harnessResult.result,
          atoms_done: harnessResult.atoms_used?.length ?? 0,
        },
      });
    }

    return [results];
  }
}
