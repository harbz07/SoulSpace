import { ProviderFactory, REASONING_MODELS } from './providers/index.js';
import { loadConfig } from './config.js';
import { GetSecondOpinionSchema } from './types.js';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import {
  AgentMeshOrchestrator,
  CreateMigrationPackageSchema,
  DispatchMigrationSchema,
  ListMigrationsSchema,
  RegisterVesselSchema,
  SendDiscordAnnouncementSchema,
} from './agentMesh/index.js';

class MindBridgeServer extends McpServer {
  private providerFactory: ProviderFactory;
  private agentMesh: AgentMeshOrchestrator;
  private agentMeshReady: Promise<void>;

  constructor() {
    super({
      name: 'mindbridge',
      version: '1.2.0'
    }, {
      capabilities: {
        tools: {}
      }
    });

    const config = loadConfig();
    this.providerFactory = new ProviderFactory(config);
    this.agentMesh = new AgentMeshOrchestrator(config.agentMesh);
    this.agentMeshReady = this.agentMesh.initialize().catch((error) => {
      console.error('Failed to initialize Agent Mesh:', error);
      throw error;
    });

    // Register tools
    this.registerTools();
  }

  private async ensureAgentMeshReady(): Promise<void> {
    await this.agentMeshReady;
  }

  private toolError(error: unknown): { content: { type: 'text'; text: string }[]; isError: true } {
    return {
      content: [{ type: 'text', text: `Error: ${error instanceof Error ? error.message : 'An unknown error occurred'}` }],
      isError: true
    };
  }

  private registerTools(): void {
    // Register getSecondOpinion tool
    this.tool('getSecondOpinion',
      'Get responses from various LLM providers',
      GetSecondOpinionSchema.shape,
      async (params) => {
        try {
          // Validate provider exists
          const providerName = params.provider.toLowerCase();
          if (!this.providerFactory.hasProvider(providerName)) {
            const availableProviders = this.providerFactory.getAvailableProviders();
            throw new Error(
              `Provider "${params.provider}" not configured. Available providers: ${availableProviders.join(', ')}`
            );
          }

          const provider = this.providerFactory.getProvider(providerName)!;

          // Validate model exists for provider
          if (!provider.isValidModel(params.model)) {
            const availableModels = provider.getAvailableModels();
            throw new Error(
              `Model "${params.model}" not found for provider "${params.provider}". Available models: ${availableModels.join(', ')}`
            );
          }

          // Check reasoning effort compatibility
          if (params.reasoning_effort && !provider.supportsReasoningEffort()) {
            console.warn(
              `Warning: Provider "${params.provider}" does not support reasoning_effort parameter. It will be ignored.`
            );
          }

          // Get response from provider
          const result = await provider.getResponse(params);

          if (result.isError) {
            return {
              content: [{ type: 'text', text: `Error: ${result.content[0].text}` }],
              isError: true
            };
          }

          return {
            content: result.content
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register listProviders tool
    this.tool('listProviders',
      'List all configured LLM providers and their available models',
      {},
      async () => {
        try {
          const providers = this.providerFactory.getAvailableProviders();
          const result: Record<string, {
            models: string[];
            supportsReasoning: boolean;
          }> = {};

          for (const provider of providers) {
            result[provider] = {
              models: this.providerFactory.getAvailableModelsForProvider(provider),
              supportsReasoning: this.providerFactory.supportsReasoningEffort(provider)
            };
          }

          return {
            content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register listReasoningModels tool
    this.tool('listReasoningModels',
      'List all available models that support reasoning capabilities',
      {},
      async () => {
        try {
          return {
            content: [{
              type: 'text',
              text: JSON.stringify({
                models: REASONING_MODELS,
                description: 'These models are specifically optimized for reasoning tasks and support the reasoning_effort parameter.'
              }, null, 2)
            }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register registerVessel tool
    this.tool('registerVessel',
      'Register or update a vessel for agent migration',
      RegisterVesselSchema.shape,
      async (params) => {
        try {
          await this.ensureAgentMeshReady();
          const vessel = await this.agentMesh.registerVessel(params);
          return {
            content: [{ type: 'text', text: JSON.stringify(vessel, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register listVessels tool
    this.tool('listVessels',
      'List registered vessels and capabilities',
      {},
      async () => {
        try {
          await this.ensureAgentMeshReady();
          const vessels = this.agentMesh.listVessels();
          return {
            content: [{ type: 'text', text: JSON.stringify(vessels, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register prepareAgentMigration tool
    this.tool('prepareAgentMigration',
      'Create a migration package for an agent handoff',
      CreateMigrationPackageSchema.shape,
      async (params) => {
        try {
          await this.ensureAgentMeshReady();
          const migration = await this.agentMesh.createMigrationPackage(params);
          return {
            content: [{ type: 'text', text: JSON.stringify(migration, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register dispatchAgentMigration tool
    this.tool('dispatchAgentMigration',
      'Dispatch a prepared migration package to target vessel',
      DispatchMigrationSchema.shape,
      async (params) => {
        try {
          await this.ensureAgentMeshReady();
          const result = await this.agentMesh.dispatchMigration(params);
          return {
            content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register listAgentMigrations tool
    this.tool('listAgentMigrations',
      'List migration packages and statuses',
      ListMigrationsSchema.shape,
      async (params) => {
        try {
          await this.ensureAgentMeshReady();
          const migrations = this.agentMesh.listMigrations({
            status: params.status,
            limit: params.limit ?? 25
          });
          return {
            content: [{ type: 'text', text: JSON.stringify(migrations, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );

    // Register announceAgentEvent tool
    this.tool('announceAgentEvent',
      'Send an update to Discord webhook or forum webhook',
      SendDiscordAnnouncementSchema.shape,
      async (params) => {
        try {
          await this.ensureAgentMeshReady();
          const results = await this.agentMesh.announceEvent(params);
          return {
            content: [{ type: 'text', text: JSON.stringify(results, null, 2) }]
          };
        } catch (error) {
          return this.toolError(error);
        }
      }
    );
  }
}

export default MindBridgeServer;
