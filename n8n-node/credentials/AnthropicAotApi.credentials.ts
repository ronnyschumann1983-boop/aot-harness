import { ICredentialType, INodeProperties } from 'n8n-workflow';

export class AnthropicAotApi implements ICredentialType {
  name        = 'anthropicAotApi';
  displayName = 'AoT Harness — Anthropic';
  documentationUrl = 'https://docs.anthropic.com/en/api/getting-started';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'Anthropic API Key (https://console.anthropic.com)',
    },
  ];
}
