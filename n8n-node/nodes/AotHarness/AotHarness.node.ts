import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  INodePropertyOptions,
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

import {
  ProviderId,
  MODEL_OPTIONS,
  DEFAULT_MODEL,
  callLLM,
  resolveCredentials,
  LLMConfig,
} from './llm.router';

// ── UI helper: build display-options for per-provider model dropdown ─────────

const modelOptionsForProvider = (p: ProviderId): INodePropertyOptions[] => MODEL_OPTIONS[p];

export class AotHarness implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'AoT Harness',
    name:        'aotHarness',
    icon:        'fa:brain',
    group:       ['transform'],
    version:     1,
    subtitle:    '={{$parameter["goal"].substring(0,45)}}...',
    description: 'CHIP + Atom of Thoughts (AoT) — multi-provider (Anthropic, OpenAI, Google, Mistral, OpenRouter)',
    defaults:    { name: 'AoT Harness' },
    inputs:      ['main'],
    outputs:     ['main'],
    credentials: [
      { name: 'anthropicAotApi',   required: true, displayOptions: { show: { provider: ['anthropic'] } } },
      { name: 'openAiAotApi',      required: true, displayOptions: { show: { provider: ['openai'] } } },
      { name: 'googleGeminiAotApi',required: true, displayOptions: { show: { provider: ['google'] } } },
      { name: 'mistralAotApi',     required: true, displayOptions: { show: { provider: ['mistral'] } } },
      { name: 'openRouterAotApi',  required: true, displayOptions: { show: { provider: ['openrouter'] } } },

      // Mixed-mode: separate decomposer credentials
      { name: 'anthropicAotApi',   required: true,
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['anthropic'] } } },
      { name: 'openAiAotApi',      required: true,
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['openai'] } } },
      { name: 'googleGeminiAotApi',required: true,
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['google'] } } },
      { name: 'mistralAotApi',     required: true,
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['mistral'] } } },
      { name: 'openRouterAotApi',  required: true,
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['openrouter'] } } },
    ],

    properties: [
      // ── Provider Section ──────────────────────────────────────────────────
      {
        displayName: 'Provider',
        name:        'provider',
        type:        'options',
        default:     'anthropic',
        description: 'LLM provider used for atom execution + QA',
        options: [
          { name: 'Anthropic (Claude)',                value: 'anthropic' },
          { name: 'OpenAI (GPT)',                       value: 'openai' },
          { name: 'Google (Gemini)',                    value: 'google' },
          { name: 'Mistral (EU-hosted, GDPR)',          value: 'mistral' },
          { name: 'OpenRouter (100+ models, 1 key)',    value: 'openrouter' },
        ],
      },
      {
        displayName: 'Model',
        name:        'model',
        type:        'options',
        default:     'claude-sonnet-4-5',
        description: 'Model to use. Defaults reflect the provider\'s recommended choice.',
        options:     modelOptionsForProvider('anthropic'),
        displayOptions: { show: { provider: ['anthropic'] } },
      },
      {
        displayName: 'Model',
        name:        'model',
        type:        'options',
        default:     'gpt-4o',
        options:     modelOptionsForProvider('openai'),
        displayOptions: { show: { provider: ['openai'] } },
      },
      {
        displayName: 'Model',
        name:        'model',
        type:        'options',
        default:     'gemini-2.0-flash',
        options:     modelOptionsForProvider('google'),
        displayOptions: { show: { provider: ['google'] } },
      },
      {
        displayName: 'Model',
        name:        'model',
        type:        'options',
        default:     'mistral-large-latest',
        options:     modelOptionsForProvider('mistral'),
        displayOptions: { show: { provider: ['mistral'] } },
      },
      {
        displayName: 'Model',
        name:        'model',
        type:        'options',
        default:     'anthropic/claude-sonnet-4-5',
        options:     modelOptionsForProvider('openrouter'),
        displayOptions: { show: { provider: ['openrouter'] } },
      },

      // ── Goal ──────────────────────────────────────────────────────────────
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
        displayName: 'Mode',
        name:        'mode',
        type:        'options',
        options: [
          { name: 'CHIP + AoT (full)',    value: 'chip',    description: 'AoT decomposition + atom solving + QA' },
          { name: 'AoT only (fast)',       value: 'aot',     description: 'Just AoT decomposition without QA' },
          { name: 'Webhook (Python)',      value: 'webhook', description: 'Calls a running aot-harness Python server' },
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

      // ── Mixed-Mode Section (killer feature) ───────────────────────────────
      {
        displayName: '🪙 Enable Mixed-Provider Mode (cost-saving)',
        name:        'enableMixedMode',
        type:        'boolean',
        default:     false,
        description: 'Use a separate (smarter) provider for AoT decomposition while a cheaper one executes atoms. Typical saving: 60-80%.',
      },
      {
        displayName: 'Decomposer Provider',
        name:        'decomposerProvider',
        type:        'options',
        default:     'anthropic',
        description: 'High-quality LLM for the initial AoT decomposition step (only — atoms still use the main provider above)',
        options: [
          { name: 'Anthropic (Claude)',  value: 'anthropic' },
          { name: 'OpenAI (GPT)',        value: 'openai' },
          { name: 'Google (Gemini)',     value: 'google' },
          { name: 'Mistral',             value: 'mistral' },
          { name: 'OpenRouter',          value: 'openrouter' },
        ],
        displayOptions: { show: { enableMixedMode: [true] } },
      },
      {
        displayName: 'Decomposer Model',
        name:        'decomposerModel',
        type:        'options',
        default:     'claude-opus-4-5',
        options:     modelOptionsForProvider('anthropic'),
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['anthropic'] } },
      },
      {
        displayName: 'Decomposer Model',
        name:        'decomposerModel',
        type:        'options',
        default:     'gpt-4o',
        options:     modelOptionsForProvider('openai'),
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['openai'] } },
      },
      {
        displayName: 'Decomposer Model',
        name:        'decomposerModel',
        type:        'options',
        default:     'gemini-1.5-pro',
        options:     modelOptionsForProvider('google'),
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['google'] } },
      },
      {
        displayName: 'Decomposer Model',
        name:        'decomposerModel',
        type:        'options',
        default:     'mistral-large-latest',
        options:     modelOptionsForProvider('mistral'),
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['mistral'] } },
      },
      {
        displayName: 'Decomposer Model',
        name:        'decomposerModel',
        type:        'options',
        default:     'anthropic/claude-opus-4-5',
        options:     modelOptionsForProvider('openrouter'),
        displayOptions: { show: { enableMixedMode: [true], decomposerProvider: ['openrouter'] } },
      },

      // ── Advanced ──────────────────────────────────────────────────────────
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
      const goal             = this.getNodeParameter('goal', i) as string;
      const mode             = this.getNodeParameter('mode', i) as string;
      const provider         = this.getNodeParameter('provider', i) as ProviderId;
      const model            = this.getNodeParameter('model', i) as string;
      const enableMixedMode  = this.getNodeParameter('enableMixedMode', i, false) as boolean;
      const advanced         = this.getNodeParameter('advanced', i) as Record<string, unknown>;

      const maxTokens   = (advanced.maxTokens   as number)  ?? 1500;
      const qaThreshold = (advanced.qaThreshold as number)  ?? 0.75;
      const qaRetry     = (advanced.qaRetry     as boolean) ?? true;
      const language    = (advanced.language    as string)  ?? 'de';

      // ── Resolve executor + (optional) decomposer LLM configs ────────────
      const executorConfig: LLMConfig = await resolveCredentials(this, provider, model, maxTokens);

      let decomposerConfig: LLMConfig = executorConfig;
      if (enableMixedMode) {
        const dProvider = this.getNodeParameter('decomposerProvider', i) as ProviderId;
        const dModel    = (this.getNodeParameter('decomposerModel', i) as string) || DEFAULT_MODEL[dProvider];
        decomposerConfig = await resolveCredentials(this, dProvider, dModel, maxTokens);
      }

      let harnessResult: HarnessResult;

      // ── Webhook-Modus ──────────────────────────────────────────────────────
      if (mode === 'webhook') {
        const url = this.getNodeParameter('webhookUrl', i) as string;
        const resp = await this.helpers.request({
          method: 'POST',
          url,
          json: true,
          body: {
            goal,
            // Pass provider config to the Python server for v0.3 multi-provider Python orchestrator
            provider:           executorConfig.provider,
            model:              executorConfig.model,
            api_key:            executorConfig.apiKey,
            decomposer_provider: enableMixedMode ? decomposerConfig.provider : undefined,
            decomposer_model:    enableMixedMode ? decomposerConfig.model    : undefined,
            decomposer_api_key:  enableMixedMode ? decomposerConfig.apiKey   : undefined,
          },
        });
        harnessResult = resp as HarnessResult;

      } else {
        // ── AoT Decomposition (uses decomposer LLM in mixed mode, else executor) ────
        const decomposeRaw  = await callLLM(this, decomposerConfig, DECOMPOSE_PROMPT(goal, language));
        const decomposeData = parseJson<{ atoms: Array<{ id: string; question: string; depends_on: string[] }> }>(
          decomposeRaw, { atoms: [] }
        );

        if (!decomposeData.atoms.length) {
          decomposeData.atoms = [{ id: 'a1', question: goal, depends_on: [] }];
        }

        const graph: AtomGraph = { goal, atoms: {} };
        for (const a of decomposeData.atoms) {
          graph.atoms[a.id] = { ...a, status: 'pending' };
        }

        // ── Atoms loesen (executor LLM) ────────────────────────────────────
        const specialistOutputs: Record<string, string> = {};
        let rounds = 0;
        const maxRounds = Object.keys(graph.atoms).length * 4;

        while (!isComplete(graph) && rounds < maxRounds) {
          rounds++;
          const ready = readyAtoms(graph);
          if (!ready.length) break;

          const ctx = compressedContext(graph);
          for (const atom of ready) atom.status = 'running';

          await Promise.all(ready.map(async (atom) => {
            try {
              const raw    = await callLLM(this, executorConfig, SOLVE_PROMPT(goal, atom.question, ctx, language));
              atom.result  = raw;
              atom.status  = 'done';
              specialistOutputs[atom.id] = raw;
            } catch {
              atom.status = 'failed';
            }
          }));
        }

        // ── QA (executor LLM, optional retry) ─────────────────────────────
        const allOutputs = JSON.stringify(specialistOutputs, null, 2);
        let qaData = { final_output: '', qa_score: 0, bestanden: false, anmerkungen: [] as string[] };
        let attempts = qaRetry ? 2 : 1;

        while (attempts > 0) {
          const qaRaw = await callLLM(this, executorConfig, QA_PROMPT(goal, allOutputs, language, qaThreshold));
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
          provider_used:           executorConfig.provider,
          model_used:              executorConfig.model,
          decomposer_provider_used: enableMixedMode ? decomposerConfig.provider : undefined,
          decomposer_model_used:    enableMixedMode ? decomposerConfig.model    : undefined,
        },
      });
    }

    return [results];
  }
}
