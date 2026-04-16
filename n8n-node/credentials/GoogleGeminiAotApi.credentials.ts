import { ICredentialType, INodeProperties } from 'n8n-workflow';

export class GoogleGeminiAotApi implements ICredentialType {
  name        = 'googleGeminiAotApi';
  displayName = 'AoT Harness — Google Gemini';
  documentationUrl = 'https://ai.google.dev/gemini-api/docs/api-key';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'Google AI Studio API Key (https://aistudio.google.com/app/apikey)',
    },
  ];
}
