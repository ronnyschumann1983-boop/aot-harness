/**
 * llm.router.ts
 * Provider-agnostic HTTP LLM caller for the n8n AoT-Harness node.
 *
 * Supports: anthropic, openai, google, mistral, openrouter
 *
 * Backward-compat: legacy `aotHarnessApi` credential maps to anthropic.
 *
 * v0.3 — every call returns { text, usage } so the node can aggregate
 * per-atom cost in TypeScript without a Python round-trip.
 */
import { IExecuteFunctions } from 'n8n-workflow';

export interface LLMUsage {
  prompt_tokens:     number;
  completion_tokens: number;
  cost_usd:          number;
}

export interface LLMResult {
  text:  string;
  usage: LLMUsage;
}

/** Pricing per 1M tokens [input, output] in USD. Updated April 2026. */
export const PRICING_PER_1M: Record<string, [number, number]> = {
  // Anthropic
  'claude-opus-4-7':             [15.00, 75.00],
  'claude-sonnet-4-6':           [ 3.00, 15.00],
  'claude-haiku-4-5-20251001':   [ 0.80,  4.00],
  // OpenAI
  'gpt-4o':                [ 2.50, 10.00],
  'gpt-4o-mini':           [ 0.15,  0.60],
  'o1':                    [15.00, 60.00],
  'o1-mini':               [ 3.00, 12.00],
  // Google Gemini
  'gemini-2.0-flash':      [ 0.10,  0.40],
  'gemini-1.5-pro':        [ 1.25,  5.00],
  'gemini-1.5-flash':      [ 0.075, 0.30],
  // Mistral
  'mistral-large-latest':  [ 2.00,  6.00],
  'mistral-small-latest':  [ 0.20,  0.60],
  'codestral-latest':      [ 0.20,  0.60],
  // OpenRouter (strip provider prefix and lookup base model)
  'anthropic/claude-opus-4-7':   [15.00, 75.00],
  'anthropic/claude-sonnet-4-6': [ 3.00, 15.00],
  'openai/gpt-4o':               [ 2.50, 10.00],
  'google/gemini-2.0-flash':     [ 0.10,  0.40],
  'deepseek/deepseek-chat':      [ 0.14,  0.28],
  'meta-llama/llama-3.3-70b-instruct': [ 0.30,  0.50],
  'qwen/qwen-2.5-72b-instruct':  [ 0.40,  0.80],
};

function calcCost(model: string, promptTokens: number, completionTokens: number): number {
  const rate = PRICING_PER_1M[model];
  if (!rate) return 0;
  return (promptTokens / 1_000_000) * rate[0] + (completionTokens / 1_000_000) * rate[1];
}

export type ProviderId = 'anthropic' | 'openai' | 'google' | 'mistral' | 'openrouter';

export const DEFAULT_MODEL: Record<ProviderId, string> = {
  anthropic:  'claude-sonnet-4-6',
  openai:     'gpt-4o',
  google:     'gemini-2.0-flash',
  mistral:    'mistral-large-latest',
  openrouter: 'anthropic/claude-sonnet-4-6',
};

export const CREDENTIAL_NAME: Record<ProviderId, string> = {
  anthropic:  'anthropicAotApi',
  openai:     'openAiAotApi',
  google:     'googleGeminiAotApi',
  mistral:    'mistralAotApi',
  openrouter: 'openRouterAotApi',
};

/** Curated model options per provider for the n8n UI dropdown. */
export const MODEL_OPTIONS: Record<ProviderId, Array<{ name: string; value: string }>> = {
  anthropic: [
    { name: 'Claude Opus 4.7 (highest quality)',    value: 'claude-opus-4-7' },
    { name: 'Claude Sonnet 4.6 (recommended)',      value: 'claude-sonnet-4-6' },
    { name: 'Claude Haiku 4.5 (fast + cheap)',      value: 'claude-haiku-4-5-20251001' },
  ],
  openai: [
    { name: 'GPT-4o',          value: 'gpt-4o' },
    { name: 'GPT-4o Mini',     value: 'gpt-4o-mini' },
    { name: 'o1 (reasoning)',  value: 'o1' },
    { name: 'o1-mini',         value: 'o1-mini' },
  ],
  google: [
    { name: 'Gemini 2.0 Flash (recommended)',  value: 'gemini-2.0-flash' },
    { name: 'Gemini 1.5 Pro (high quality)',   value: 'gemini-1.5-pro' },
    { name: 'Gemini 1.5 Flash',                value: 'gemini-1.5-flash' },
  ],
  mistral: [
    { name: 'Mistral Large (EU)',  value: 'mistral-large-latest' },
    { name: 'Mistral Small (EU)',  value: 'mistral-small-latest' },
    { name: 'Codestral (EU)',      value: 'codestral-latest' },
  ],
  openrouter: [
    { name: 'Claude Sonnet 4.6',    value: 'anthropic/claude-sonnet-4-6' },
    { name: 'GPT-4o',               value: 'openai/gpt-4o' },
    { name: 'Gemini 2.0 Flash',     value: 'google/gemini-2.0-flash' },
    { name: 'DeepSeek V3',          value: 'deepseek/deepseek-chat' },
    { name: 'Llama 3.3 70B',        value: 'meta-llama/llama-3.3-70b-instruct' },
    { name: 'Qwen 2.5 72B',         value: 'qwen/qwen-2.5-72b-instruct' },
  ],
};

const DEFAULT_SYSTEM =
  'You are a precise AI agent. When asked for JSON, output ONLY raw valid JSON — no markdown fences, no explanation before or after.';

export interface LLMConfig {
  provider:      ProviderId;
  model:         string;
  apiKey:        string;
  maxTokens:     number;
  /** OpenRouter-only */
  referer?:      string;
  title?:        string;
  /** OpenAI-only */
  organizationId?: string;
}

/**
 * Send a prompt to any of the 5 providers. Returns text + usage (tokens + cost_usd).
 */
export async function callLLM(
  ctx:    IExecuteFunctions,
  config: LLMConfig,
  prompt: string,
): Promise<LLMResult> {
  switch (config.provider) {
    case 'anthropic':  return callAnthropic(ctx, config, prompt);
    case 'openai':     return callOpenAI(ctx, config, prompt);
    case 'google':     return callGoogle(ctx, config, prompt);
    case 'mistral':    return callMistral(ctx, config, prompt);
    case 'openrouter': return callOpenRouter(ctx, config, prompt);
    default:
      throw new Error(`Unsupported provider: ${config.provider}`);
  }
}

/** Convenience: callLLM but return only the text (legacy callers). */
export async function callLLMText(
  ctx:    IExecuteFunctions,
  config: LLMConfig,
  prompt: string,
): Promise<string> {
  return (await callLLM(ctx, config, prompt)).text;
}

// ── Anthropic ────────────────────────────────────────────────────────────────

async function callAnthropic(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<LLMResult> {
  const resp = await ctx.helpers.request({
    method: 'POST',
    url:    'https://api.anthropic.com/v1/messages',
    headers: {
      'x-api-key':         c.apiKey,
      'anthropic-version': '2023-06-01',
      'content-type':      'application/json',
    },
    json: true,
    body: {
      model:      c.model,
      max_tokens: c.maxTokens,
      system:     DEFAULT_SYSTEM,
      messages:   [{ role: 'user', content: prompt }],
    },
  });
  type AnthroResp = {
    content: Array<{ text: string }>;
    usage?:  { input_tokens?: number; output_tokens?: number };
  };
  const r = resp as AnthroResp;
  const text = r.content[0].text.trim();
  const pt   = r.usage?.input_tokens  ?? 0;
  const ct   = r.usage?.output_tokens ?? 0;
  return { text, usage: { prompt_tokens: pt, completion_tokens: ct, cost_usd: calcCost(c.model, pt, ct) } };
}

// ── OpenAI ───────────────────────────────────────────────────────────────────

async function callOpenAI(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<LLMResult> {
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${c.apiKey}`,
    'Content-Type':  'application/json',
  };
  if (c.organizationId) headers['OpenAI-Organization'] = c.organizationId;

  const resp = await ctx.helpers.request({
    method: 'POST',
    url:    'https://api.openai.com/v1/chat/completions',
    headers,
    json: true,
    body: {
      model: c.model,
      max_tokens: c.maxTokens,
      messages: [
        { role: 'system', content: DEFAULT_SYSTEM },
        { role: 'user',   content: prompt },
      ],
    },
  });
  type OpenAIResp = {
    choices: Array<{ message: { content: string } }>;
    usage?:  { prompt_tokens?: number; completion_tokens?: number };
  };
  const r = resp as OpenAIResp;
  const text = r.choices[0].message.content.trim();
  const pt   = r.usage?.prompt_tokens     ?? 0;
  const ct   = r.usage?.completion_tokens ?? 0;
  return { text, usage: { prompt_tokens: pt, completion_tokens: ct, cost_usd: calcCost(c.model, pt, ct) } };
}

// ── Google Gemini ────────────────────────────────────────────────────────────

async function callGoogle(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<LLMResult> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(c.model)}:generateContent?key=${encodeURIComponent(c.apiKey)}`;
  const resp = await ctx.helpers.request({
    method: 'POST',
    url,
    headers: { 'Content-Type': 'application/json' },
    json: true,
    body: {
      systemInstruction: { parts: [{ text: DEFAULT_SYSTEM }] },
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: { maxOutputTokens: c.maxTokens },
    },
  });
  type GoogleResp = {
    candidates: Array<{ content: { parts: Array<{ text: string }> } }>;
    usageMetadata?: { promptTokenCount?: number; candidatesTokenCount?: number };
  };
  const r = resp as GoogleResp;
  const text = r.candidates[0].content.parts[0].text.trim();
  const pt   = r.usageMetadata?.promptTokenCount     ?? 0;
  const ct   = r.usageMetadata?.candidatesTokenCount ?? 0;
  return { text, usage: { prompt_tokens: pt, completion_tokens: ct, cost_usd: calcCost(c.model, pt, ct) } };
}

// ── Mistral ──────────────────────────────────────────────────────────────────

async function callMistral(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<LLMResult> {
  const resp = await ctx.helpers.request({
    method: 'POST',
    url:    'https://api.mistral.ai/v1/chat/completions',
    headers: {
      'Authorization': `Bearer ${c.apiKey}`,
      'Content-Type':  'application/json',
    },
    json: true,
    body: {
      model: c.model,
      max_tokens: c.maxTokens,
      messages: [
        { role: 'system', content: DEFAULT_SYSTEM },
        { role: 'user',   content: prompt },
      ],
    },
  });
  type MistralResp = {
    choices: Array<{ message: { content: string } }>;
    usage?:  { prompt_tokens?: number; completion_tokens?: number };
  };
  const r = resp as MistralResp;
  const text = r.choices[0].message.content.trim();
  const pt   = r.usage?.prompt_tokens     ?? 0;
  const ct   = r.usage?.completion_tokens ?? 0;
  return { text, usage: { prompt_tokens: pt, completion_tokens: ct, cost_usd: calcCost(c.model, pt, ct) } };
}

// ── OpenRouter (meta-provider) ───────────────────────────────────────────────

async function callOpenRouter(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<LLMResult> {
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${c.apiKey}`,
    'Content-Type':  'application/json',
  };
  if (c.referer) headers['HTTP-Referer'] = c.referer;
  if (c.title)   headers['X-Title']      = c.title;

  const resp = await ctx.helpers.request({
    method: 'POST',
    url:    'https://openrouter.ai/api/v1/chat/completions',
    headers,
    json: true,
    body: {
      model: c.model,
      max_tokens: c.maxTokens,
      messages: [
        { role: 'system', content: DEFAULT_SYSTEM },
        { role: 'user',   content: prompt },
      ],
    },
  });
  type ORResp = {
    choices: Array<{ message: { content: string } }>;
    usage?:  { prompt_tokens?: number; completion_tokens?: number };
  };
  const r = resp as ORResp;
  const text = r.choices[0].message.content.trim();
  const pt   = r.usage?.prompt_tokens     ?? 0;
  const ct   = r.usage?.completion_tokens ?? 0;
  return { text, usage: { prompt_tokens: pt, completion_tokens: ct, cost_usd: calcCost(c.model, pt, ct) } };
}

/**
 * Resolve credential data for a given provider into a normalized LLMConfig.
 * Used by the node executor to convert n8n credentials → llm router config.
 */
export async function resolveCredentials(
  ctx:       IExecuteFunctions,
  provider:  ProviderId,
  model:     string,
  maxTokens: number,
): Promise<LLMConfig> {
  const credName = CREDENTIAL_NAME[provider];
  const creds    = await ctx.getCredentials(credName);
  return {
    provider,
    model:          model || DEFAULT_MODEL[provider],
    apiKey:         creds.apiKey         as string,
    maxTokens,
    referer:        creds.referer        as string | undefined,
    title:          creds.title          as string | undefined,
    organizationId: creds.organizationId as string | undefined,
  };
}
