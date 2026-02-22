import { z } from 'zod';

export const MigrationStatusSchema = z.enum([
  'prepared',
  'dispatched',
  'completed',
  'failed',
]);
export type MigrationStatus = z.infer<typeof MigrationStatusSchema>;

export const RegisterVesselSchema = z.object({
  vesselId: z
    .string()
    .min(1)
    .max(64)
    .regex(
      /^[a-zA-Z0-9._-]+$/,
      'vesselId can only contain letters, numbers, dot, underscore, and dash',
    ),
  baseUrl: z.string().url(),
  migrationEndpointPath: z.string().min(1).optional().default('/migrations/ingest'),
  capabilities: z.array(z.string().min(1)).optional().default([]),
  protocols: z.array(z.string().min(1)).optional().default(['mcp-json']),
  discordWebhookUrl: z.string().url().optional().nullable(),
  forumWebhookUrl: z.string().url().optional().nullable(),
  metadata: z.record(z.string()).optional().default({}),
});
export type RegisterVesselInput = z.infer<typeof RegisterVesselSchema>;

export const CreateMigrationPackageSchema = z.object({
  agentId: z.string().min(1).max(128),
  sourceVesselId: z.string().min(1).max(64),
  targetVesselId: z.string().min(1).max(64),
  state: z.record(z.unknown()),
  memoryRefs: z.array(z.string().min(1)).optional().default([]),
  ttlSeconds: z.number().int().min(60).max(86400).optional().default(900),
});
export type CreateMigrationPackageInput = z.infer<typeof CreateMigrationPackageSchema>;

export const DispatchMigrationSchema = z.object({
  migrationId: z.string().min(1),
  includeState: z.boolean().optional().default(true),
  dryRun: z.boolean().optional().default(false),
  discordWebhookUrl: z.string().url().optional().nullable(),
  forumWebhookUrl: z.string().url().optional().nullable(),
  threadName: z.string().min(1).max(100).optional(),
});
export type DispatchMigrationInput = z.infer<typeof DispatchMigrationSchema>;

export const ListMigrationsSchema = z.object({
  status: MigrationStatusSchema.optional(),
  limit: z.number().int().min(1).max(100).optional().default(25),
});
export type ListMigrationsInput = z.infer<typeof ListMigrationsSchema>;

export const SendDiscordAnnouncementSchema = z.object({
  content: z.string().min(1).max(2000),
  webhookUrl: z.string().url().optional().nullable(),
  forumWebhookUrl: z.string().url().optional().nullable(),
  threadName: z.string().min(1).max(100).optional(),
  username: z.string().min(1).max(80).optional(),
  avatarUrl: z.string().url().optional(),
  agentId: z.string().min(1).max(128).optional(),
  migrationId: z.string().min(1).optional(),
});
export type SendDiscordAnnouncementInput = z.infer<
  typeof SendDiscordAnnouncementSchema
>;

export interface VesselRecord {
  vesselId: string;
  baseUrl: string;
  migrationEndpointPath: string;
  capabilities: string[];
  protocols: string[];
  discordWebhookUrl?: string;
  forumWebhookUrl?: string;
  metadata: Record<string, string>;
  createdAt: string;
  updatedAt: string;
}

export interface MigrationDispatchInfo {
  dispatchedAt: string;
  targetUrl: string;
  responseStatus: number;
  responseSnippet: string;
}

export interface MigrationPackage {
  migrationId: string;
  agentId: string;
  sourceVesselId: string;
  targetVesselId: string;
  state: Record<string, unknown>;
  memoryRefs: string[];
  checksum: string;
  status: MigrationStatus;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
  dispatch?: MigrationDispatchInfo;
  lastError?: string;
}

export interface PersistedAgentMeshState {
  vessels: VesselRecord[];
  migrations: MigrationPackage[];
}

export interface MigrationDispatchResult {
  migrationId: string;
  status: MigrationStatus;
  dryRun: boolean;
  targetUrl: string;
  expiresAt: string;
  announcements: DiscordWebhookResult[];
}

export interface DiscordWebhookResult {
  webhookUrl: string;
  ok: boolean;
  status: number;
  responseSnippet: string;
}
