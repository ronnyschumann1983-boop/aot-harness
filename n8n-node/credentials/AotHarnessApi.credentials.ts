import { ICredentialType, INodeProperties } from 'n8n-workflow';

export class AotHarnessApi implements ICredentialType {
  name        = 'aotHarnessApi';
  displayName = 'AoT Harness (Claude API)';

  properties: INodeProperties[] = [
    {
      displayName: 'Anthropic API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
    },
    {
      displayName: 'Claude Modell',
      name: 'model',
      type: 'options',
      options: [
        { name: 'Claude Opus 4.5 (empfohlen)', value: 'claude-opus-4-5' },
        { name: 'Claude Sonnet 4.5',           value: 'claude-sonnet-4-5' },
        { name: 'Claude Haiku 3.5 (schnell)',  value: 'claude-haiku-3-5' },
      ],
      default: 'claude-sonnet-4-5',
    },
  ];
}
