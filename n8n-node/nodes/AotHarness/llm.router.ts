/**
 * llm.router.ts
 * Provider-agnostic HTTP LLM caller for the n8n AoT-Harness node.
 *
 * Supports: anthropic, openai, google, mistral, openrouter
 *
 * Backward-compat: legacy `aotHarnessApi` credential maps to anthropic.
 */
import { IExecuteFunctions } from 'n8n-workflow';

export type ProviderId = 'anthropic' | 'openai' | 'google' | 'mistral' | 'openrouter';

export const DEFAULT_MODEL: Record<ProviderId, string> = {
  anthropic:  'claude-sonnet-4-5',
  openai:     'gpt-4o',
  google:     'gemini-2.0-flash',
  mistral:    'mistral-large-latest',
  openrouter: 'anthropic/claude-sonnet-4-5',
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
    { name: 'Claude Opus 4.5 (highest quality)',    value: 'claude-opus-4-5' },
    { name: 'Claude Sonnet 4.5 (recommended)',      value: 'claude-sonnet-4-5' },
    { name: 'Claude Haiku 3.5 (fast + cheap)',      value: 'claude-haiku-3-5' },
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
    { name: 'Claude Sonnet 4.5',    value: 'anthropic/claude-sonnet-4-5' },
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
 * Send a prompt to any of the 5 providers. Returns the response text.
 */
export async function callLLM(
  ctx:    IExecuteFunctions,
  config: LLMConfig,
  prompt: string,
): Promise<string> {
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

// ── Anthropic ────────────────────────────────────────────────────────────────

async function callAnthropic(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<string> {
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
  return (resp as { content: Array<{ text: string }> }).content[0].text.trim();
}

// ── OpenAI ───────────────────────────────────────────────────────────────────

async function callOpenAI(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<string> {
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
  return (resp as { choices: Array<{ message: { content: string } }> }).choices[0].message.content.trim();
}

// ── Google Gemini ────────────────────────────────────────────────────────────

async function callGoogle(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<string> {
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
  type GoogleResp = { candidates: Array<{ content: { parts: Array<{ text: string }> } }> };
  return (resp as GoogleResp).candidates[0].content.parts[0].text.trim();
}

// ── Mistral ──────────────────────────────────────────────────────────────────

async function callMistral(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<string> {
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
  return (resp as { choices: Array<{ message: { content: string } }> }).choices[0].message.content.trim();
}

// ── OpenRouter (meta-provider) ───────────────────────────────────────────────

async function callOpenRouter(ctx: IExecuteFunctions, c: LLMConfig, prompt: string): Promise<string> {
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
  return (resp as { choices: Array<{ message: { content: string } }> }).choices[0].message.content.trim();
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
