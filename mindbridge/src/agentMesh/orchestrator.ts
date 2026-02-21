import { createHash, randomUUID } from 'node:crypto';
import type { AgentMeshConfig } from '../types.js';
import { sendDiscordWebhook } from './discord.js';
import { AgentMeshStore } from './store.js';
import type {
  CreateMigrationPackageInput,
  DispatchMigrationInput,
  DiscordWebhookResult,
  ListMigrationsInput,
  MigrationDispatchInfo,
  MigrationDispatchResult,
  MigrationPackage,
  SendDiscordAnnouncementInput,
  VesselRecord,
  RegisterVesselInput,
} from './types.js';

interface AgentMeshResolvedConfig {
  storagePath?: string;
  defaultMigrationEndpointPath: string;
  migrationAuthToken?: string;
  defaultDiscordWebhookUrl?: string;
  defaultForumWebhookUrl?: string;
}

function normalizeEndpointPath(pathValue: string): string {
  return pathValue.startsWith('/') ? pathValue : `/${pathValue}`;
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

function responseSnippet(input: string, maxLength = 300): string {
  if (input.length <= maxLength) {
    return input;
  }
  return `${input.slice(0, maxLength)}...`;
}

function stableJsonString(value: unknown): string {
  if (value === null) {
    return 'null';
  }

  if (typeof value === 'undefined') {
    return 'null';
  }

  if (
    typeof value === 'number' ||
    typeof value === 'boolean' ||
    typeof value === 'string'
  ) {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJsonString(item)).join(',')}]`;
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, nestedValue]) => typeof nestedValue !== 'undefined')
      .sort(([a], [b]) => a.localeCompare(b));

    const serialized = entries
      .map(
        ([key, nestedValue]) =>
          `${JSON.stringify(key)}:${stableJsonString(nestedValue)}`,
      )
      .join(',');
    return `{${serialized}}`;
  }

  return JSON.stringify(String(value));
}

function buildMigrationContent(
  migration: MigrationPackage,
  targetVessel: VesselRecord,
): string {
  return [
    'MindBridge Agent Migration',
    `Agent: ${migration.agentId}`,
    `Source vessel: ${migration.sourceVesselId}`,
    `Target vessel: ${migration.targetVesselId}`,
    `Target URL: ${targetVessel.baseUrl}`,
    `Migration ID: ${migration.migrationId}`,
    `Status: ${migration.status}`,
  ].join('\n');
}

export class AgentMeshOrchestrator {
  private readonly store: AgentMeshStore;
  private readonly config: AgentMeshResolvedConfig;

  constructor(config?: AgentMeshConfig) {
    this.config = {
      storagePath: config?.storagePath,
      defaultMigrationEndpointPath: normalizeEndpointPath(
        config?.defaultMigrationEndpointPath ?? '/migrations/ingest',
      ),
      migrationAuthToken: config?.migrationAuthToken,
      defaultDiscordWebhookUrl: config?.defaultDiscordWebhookUrl,
      defaultForumWebhookUrl: config?.defaultForumWebhookUrl,
    };

    this.store = new AgentMeshStore(this.config.storagePath);
  }

  public async initialize(): Promise<void> {
    await this.store.initialize();
  }

  public async registerVessel(input: RegisterVesselInput): Promise<VesselRecord> {
    return this.store.upsertVessel({
      vesselId: input.vesselId,
      baseUrl: normalizeBaseUrl(input.baseUrl),
      migrationEndpointPath: normalizeEndpointPath(
        input.migrationEndpointPath || this.config.defaultMigrationEndpointPath,
      ),
      capabilities: Array.from(new Set(input.capabilities)),
      protocols: Array.from(new Set(input.protocols)),
      discordWebhookUrl: input.discordWebhookUrl ?? undefined,
      forumWebhookUrl: input.forumWebhookUrl ?? undefined,
      metadata: input.metadata,
    });
  }

  public listVessels(): VesselRecord[] {
    return this.store.listVessels();
  }

  public async createMigrationPackage(
    input: CreateMigrationPackageInput,
  ): Promise<MigrationPackage> {
    if (!this.store.getVessel(input.sourceVesselId)) {
      throw new Error(`Source vessel "${input.sourceVesselId}" is not registered`);
    }

    if (!this.store.getVessel(input.targetVesselId)) {
      throw new Error(`Target vessel "${input.targetVesselId}" is not registered`);
    }

    const now = new Date();
    const expiresAt = new Date(now.getTime() + input.ttlSeconds * 1000);
    const checksum = createHash('sha256')
      .update(stableJsonString(input.state))
      .digest('hex');

    const migration: MigrationPackage = {
      migrationId: randomUUID(),
      agentId: input.agentId,
      sourceVesselId: input.sourceVesselId,
      targetVesselId: input.targetVesselId,
      state: input.state,
      memoryRefs: input.memoryRefs,
      checksum,
      status: 'prepared',
      createdAt: now.toISOString(),
      updatedAt: now.toISOString(),
      expiresAt: expiresAt.toISOString(),
    };

    return this.store.createMigration(migration);
  }

  public listMigrations(input: ListMigrationsInput): MigrationPackage[] {
    return this.store.listMigrations(input.status, input.limit);
  }

  public async dispatchMigration(
    input: DispatchMigrationInput,
  ): Promise<MigrationDispatchResult> {
    const migration = this.store.getMigration(input.migrationId);
    if (!migration) {
      throw new Error(`Migration "${input.migrationId}" does not exist`);
    }

    const targetVessel = this.store.getVessel(migration.targetVesselId);
    if (!targetVessel) {
      throw new Error(`Target vessel "${migration.targetVesselId}" is not registered`);
    }

    const targetUrl = new URL(
      targetVessel.migrationEndpointPath || this.config.defaultMigrationEndpointPath,
      targetVessel.baseUrl,
    ).toString();

    if (new Date(migration.expiresAt).getTime() < Date.now()) {
      const expired = await this.store.updateMigration(migration.migrationId, {
        status: 'failed',
        lastError: 'Migration package expired before dispatch',
      });

      if (!expired) {
        throw new Error('Failed to mark expired migration');
      }

      return {
        migrationId: expired.migrationId,
        status: expired.status,
        dryRun: input.dryRun,
        targetUrl,
        expiresAt: expired.expiresAt,
        announcements: [],
      };
    }

    if (input.dryRun) {
      return {
        migrationId: migration.migrationId,
        status: migration.status,
        dryRun: true,
        targetUrl,
        expiresAt: migration.expiresAt,
        announcements: [],
      };
    }

    const payload: Record<string, unknown> = {
      migrationId: migration.migrationId,
      agentId: migration.agentId,
      sourceVesselId: migration.sourceVesselId,
      targetVesselId: migration.targetVesselId,
      checksum: migration.checksum,
      memoryRefs: migration.memoryRefs,
      createdAt: migration.createdAt,
      expiresAt: migration.expiresAt,
    };

    if (input.includeState) {
      payload.state = migration.state;
    }

    await this.store.updateMigration(migration.migrationId, {
      status: 'dispatched',
      lastError: undefined,
    });

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.config.migrationAuthToken) {
      headers.Authorization = `Bearer ${this.config.migrationAuthToken}`;
    }

    let dispatchInfo: MigrationDispatchInfo;

    try {
      const response = await fetch(targetUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      const rawResponse = await response.text();
      dispatchInfo = {
        dispatchedAt: new Date().toISOString(),
        targetUrl,
        responseStatus: response.status,
        responseSnippet: responseSnippet(rawResponse || response.statusText),
      };

      if (!response.ok) {
        const failed = await this.store.updateMigration(migration.migrationId, {
          status: 'failed',
          dispatch: dispatchInfo,
          lastError: `Target vessel returned ${response.status}`,
        });

        if (!failed) {
          throw new Error('Failed to persist failed migration status');
        }

        return {
          migrationId: failed.migrationId,
          status: failed.status,
          dryRun: false,
          targetUrl,
          expiresAt: failed.expiresAt,
          announcements: [],
        };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown dispatch error';

      const failed = await this.store.updateMigration(migration.migrationId, {
        status: 'failed',
        lastError: message,
      });

      if (!failed) {
        throw new Error('Failed to persist migration dispatch error');
      }

      return {
        migrationId: failed.migrationId,
        status: failed.status,
        dryRun: false,
        targetUrl,
        expiresAt: failed.expiresAt,
        announcements: [],
      };
    }

    const completed = await this.store.updateMigration(migration.migrationId, {
      status: 'completed',
      dispatch: dispatchInfo,
      lastError: undefined,
    });

    if (!completed) {
      throw new Error('Failed to persist completed migration status');
    }

    const announcements = await this.sendMigrationAnnouncements(
      completed,
      targetVessel,
      input,
    );

    return {
      migrationId: completed.migrationId,
      status: completed.status,
      dryRun: false,
      targetUrl,
      expiresAt: completed.expiresAt,
      announcements,
    };
  }

  public async announceEvent(
    input: SendDiscordAnnouncementInput,
  ): Promise<DiscordWebhookResult[]> {
    const messagePrefix = [
      input.agentId ? `Agent: ${input.agentId}` : '',
      input.migrationId ? `Migration: ${input.migrationId}` : '',
    ]
      .filter(Boolean)
      .join('\n');

    const content = messagePrefix
      ? `${messagePrefix}\n${input.content}`
      : input.content;

    const webhookTargets = [
      input.webhookUrl ?? this.config.defaultDiscordWebhookUrl,
      input.forumWebhookUrl ?? this.config.defaultForumWebhookUrl,
    ].filter((url): url is string => typeof url === 'string' && url.length > 0);

    const uniqueTargets = Array.from(new Set(webhookTargets));
    if (uniqueTargets.length === 0) {
      throw new Error(
        'No webhook target provided. Pass webhookUrl/forumWebhookUrl or configure defaults.',
      );
    }

    const results: DiscordWebhookResult[] = [];

    for (const webhookUrl of uniqueTargets) {
      const isForum = webhookUrl === (input.forumWebhookUrl ?? this.config.defaultForumWebhookUrl);
      results.push(
        await sendDiscordWebhook({
          webhookUrl,
          content,
          threadName: isForum ? input.threadName : undefined,
          username: input.username,
          avatarUrl: input.avatarUrl,
        }),
      );
    }

    return results;
  }

  private async sendMigrationAnnouncements(
    migration: MigrationPackage,
    targetVessel: VesselRecord,
    input: DispatchMigrationInput,
  ): Promise<DiscordWebhookResult[]> {
    const content = buildMigrationContent(migration, targetVessel);
    const standardWebhook =
      input.discordWebhookUrl ??
      targetVessel.discordWebhookUrl ??
      this.config.defaultDiscordWebhookUrl;
    const forumWebhook =
      input.forumWebhookUrl ??
      targetVessel.forumWebhookUrl ??
      this.config.defaultForumWebhookUrl;

    const urls = [standardWebhook, forumWebhook].filter(
      (url): url is string => typeof url === 'string' && url.length > 0,
    );

    const uniqueUrls = Array.from(new Set(urls));
    const results: DiscordWebhookResult[] = [];

    for (const webhookUrl of uniqueUrls) {
      const isForum = webhookUrl === forumWebhook;
      results.push(
        await sendDiscordWebhook({
          webhookUrl,
          content,
          threadName: isForum
            ? input.threadName ??
              `agent-${migration.agentId}-migration-${migration.migrationId.slice(0, 8)}`
            : undefined,
          username: 'MindBridge Mesh',
        }),
      );
    }

    return results;
  }
}
