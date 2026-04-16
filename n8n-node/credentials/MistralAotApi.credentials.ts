import { ICredentialType, INodeProperties } from 'n8n-workflow';

export class MistralAotApi implements ICredentialType {
  name        = 'mistralAotApi';
  displayName = 'AoT Harness — Mistral (EU)';
  documentationUrl = 'https://docs.mistral.ai/api/';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'Mistral API Key (https://console.mistral.ai/) — EU-hosted, GDPR-compliant',
    },
  ];
}
