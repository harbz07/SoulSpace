import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import type {
  MigrationPackage,
  MigrationStatus,
  PersistedAgentMeshState,
  VesselRecord,
} from './types.js';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function isNodeErrorWithCode(error: unknown, code: string): boolean {
  return (
    isRecord(error) &&
    'code' in error &&
    typeof error.code === 'string' &&
    error.code === code
  );
}

function isMigrationStatus(value: unknown): value is MigrationStatus {
  return (
    value === 'prepared' ||
    value === 'dispatched' ||
    value === 'completed' ||
    value === 'failed'
  );
}

function isVesselRecord(value: unknown): value is VesselRecord {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.vesselId === 'string' &&
    typeof value.baseUrl === 'string' &&
    typeof value.migrationEndpointPath === 'string' &&
    isStringArray(value.capabilities) &&
    isStringArray(value.protocols) &&
    (typeof value.discordWebhookUrl === 'undefined' ||
      typeof value.discordWebhookUrl === 'string') &&
    (typeof value.forumWebhookUrl === 'undefined' ||
      typeof value.forumWebhookUrl === 'string') &&
    isRecord(value.metadata) &&
    Object.values(value.metadata).every((entry) => typeof entry === 'string') &&
    typeof value.createdAt === 'string' &&
    typeof value.updatedAt === 'string'
  );
}

function isMigrationPackage(value: unknown): value is MigrationPackage {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.migrationId === 'string' &&
    typeof value.agentId === 'string' &&
    typeof value.sourceVesselId === 'string' &&
    typeof value.targetVesselId === 'string' &&
    isRecord(value.state) &&
    isStringArray(value.memoryRefs) &&
    typeof value.checksum === 'string' &&
    isMigrationStatus(value.status) &&
    typeof value.createdAt === 'string' &&
    typeof value.updatedAt === 'string' &&
    typeof value.expiresAt === 'string' &&
    (typeof value.lastError === 'undefined' || typeof value.lastError === 'string')
  );
}

function parsePersistedState(raw: string): PersistedAgentMeshState {
  const parsed = JSON.parse(raw) as unknown;

  if (!isRecord(parsed)) {
    return { vessels: [], migrations: [] };
  }

  const vessels = Array.isArray(parsed.vessels)
    ? parsed.vessels.filter(isVesselRecord)
    : [];
  const migrations = Array.isArray(parsed.migrations)
    ? parsed.migrations.filter(isMigrationPackage)
    : [];

  return { vessels, migrations };
}

export class AgentMeshStore {
  private readonly storagePath?: string;
  private readonly vessels = new Map<string, VesselRecord>();
  private readonly migrations = new Map<string, MigrationPackage>();
  private saveQueue: Promise<void> = Promise.resolve();

  constructor(storagePath?: string) {
    this.storagePath = storagePath;
  }

  public async initialize(): Promise<void> {
    if (!this.storagePath) {
      return;
    }

    try {
      const raw = await readFile(this.storagePath, 'utf8');
      const parsed = parsePersistedState(raw);

      for (const vessel of parsed.vessels) {
        this.vessels.set(vessel.vesselId, vessel);
      }

      for (const migration of parsed.migrations) {
        this.migrations.set(migration.migrationId, migration);
      }
    } catch (error) {
      if (isNodeErrorWithCode(error, 'ENOENT')) {
        return;
      }
      throw error;
    }
  }

  public async upsertVessel(
    vessel: Omit<VesselRecord, 'createdAt' | 'updatedAt'>,
  ): Promise<VesselRecord> {
    const now = new Date().toISOString();
    const existing = this.vessels.get(vessel.vesselId);

    const next: VesselRecord = {
      ...vessel,
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
    };

    this.vessels.set(vessel.vesselId, next);
    await this.enqueuePersist();
    return next;
  }

  public getVessel(vesselId: string): VesselRecord | undefined {
    return this.vessels.get(vesselId);
  }

  public listVessels(): VesselRecord[] {
    return Array.from(this.vessels.values()).sort((a, b) =>
      a.vesselId.localeCompare(b.vesselId),
    );
  }

  public async createMigration(migration: MigrationPackage): Promise<MigrationPackage> {
    this.migrations.set(migration.migrationId, migration);
    await this.enqueuePersist();
    return migration;
  }

  public getMigration(migrationId: string): MigrationPackage | undefined {
    return this.migrations.get(migrationId);
  }

  public async updateMigration(
    migrationId: string,
    updates: Partial<Omit<MigrationPackage, 'migrationId' | 'createdAt' | 'updatedAt'>>,
  ): Promise<MigrationPackage | undefined> {
    const current = this.migrations.get(migrationId);
    if (!current) {
      return undefined;
    }

    const next: MigrationPackage = {
      ...current,
      ...updates,
      migrationId: current.migrationId,
      createdAt: current.createdAt,
      updatedAt: new Date().toISOString(),
    };

    this.migrations.set(migrationId, next);
    await this.enqueuePersist();
    return next;
  }

  public listMigrations(status?: MigrationStatus, limit = 25): MigrationPackage[] {
    const filtered = Array.from(this.migrations.values())
      .filter((migration) => (status ? migration.status === status : true))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

    return filtered.slice(0, limit);
  }

  private async enqueuePersist(): Promise<void> {
    const storagePath = this.storagePath;
    if (!storagePath) {
      return;
    }

    const persistTask = async (): Promise<void> => {
      const payload: PersistedAgentMeshState = {
        vessels: this.listVessels(),
        migrations: this.listMigrations(undefined, Number.MAX_SAFE_INTEGER),
      };

      await mkdir(dirname(storagePath), { recursive: true });
      await writeFile(storagePath, JSON.stringify(payload, null, 2), 'utf8');
    };

    this.saveQueue = this.saveQueue.then(persistTask, persistTask);
    await this.saveQueue;
  }
}
