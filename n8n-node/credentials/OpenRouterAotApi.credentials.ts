import { ICredentialType, INodeProperties } from 'n8n-workflow';

export class OpenRouterAotApi implements ICredentialType {
  name        = 'openRouterAotApi';
  displayName = 'AoT Harness — OpenRouter (Multi-Model Gateway)';
  documentationUrl = 'https://openrouter.ai/docs';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'OpenRouter API Key (https://openrouter.ai/keys) — single key for 100+ models',
    },
    {
      displayName: 'HTTP Referer (optional)',
      name: 'referer',
      type: 'string',
      default: '',
      description: 'Optional — your app URL for OpenRouter rankings (e.g. https://yourapp.com)',
    },
    {
      displayName: 'X-Title (optional)',
      name: 'title',
      type: 'string',
      default: '',
      description: 'Optional — your app name for OpenRouter rankings',
    },
  ];
}
