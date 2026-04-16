import { ICredentialType, INodeProperties } from 'n8n-workflow';

export class OpenAiAotApi implements ICredentialType {
  name        = 'openAiAotApi';
  displayName = 'AoT Harness — OpenAI';
  documentationUrl = 'https://platform.openai.com/api-keys';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'OpenAI API Key (https://platform.openai.com/api-keys)',
    },
    {
      displayName: 'Organization ID',
      name: 'organizationId',
      type: 'string',
      default: '',
      description: 'Optional — for organisations with multiple OpenAI orgs',
    },
  ];
}
