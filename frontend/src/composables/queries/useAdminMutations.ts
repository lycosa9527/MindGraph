/**
 * Admin Mutation Composables
 *
 * Vue Query mutations for admin panel write operations with cache invalidation.
 */
import { useMutation, useQueryClient } from '@tanstack/vue-query'

import {
  addAdminOrganizationManager,
  analyzeAdminDatabaseDump,
  cleanupAdminDatabaseOrphans,
  createAdminApiKey,
  createAdminMindbotConfig,
  createAdminOrganization,
  createAdminSchoolUser,
  createAdminSchoolUsersBatch,
  deleteAdminApiKey,
  deleteAdminLibraryDocument,
  deleteAdminMindbotConfig,
  deleteAdminOrganization,
  deleteAdminSchoolUser,
  deleteAdminUser,
  exportAdminDatabase,
  generateAdminLibraryDocumentCover,
  importAdminDatabaseDump,
  mergeAdminDatabaseDump,
  moveAdminMindbotConfig,
  probeAdminMindmateDifyHealthDraft,
  probeAdminOrganizationMindmateDifyHealth,
  registerAdminLibraryBook,
  registerAdminLibraryBooksBatch,
  reloadAdminEnvRuntime,
  removeAdminOrganizationManager,
  renameAdminLibraryPages,
  repairAdminLibrary,
  recomputeAdminTeacherUsage,
  rotateAdminMindbotCallbackToken,
  scanAdminDatabase,
  scanAdminLibrary,
  updateAdminEnvSettings,
  updateAdminFeatureOrgAccess,
  updateAdminLibraryDocumentVisibility,
  updateAdminMindbotConfig,
  updateAdminOrganization,
  updateAdminSchoolUser,
  updateAdminTeacherUsageConfig,
  updateAdminUser,
  updateAdminUserRole,
  uploadAdminOrganizationMindmateAvatar,
  type AdminTeacherUsageConfig,
} from './adminApi'
import { adminKeys } from './adminKeys'

function invalidateOrganizations(queryClient: ReturnType<typeof useQueryClient>): void {
  queryClient.invalidateQueries({ queryKey: adminKeys.organizations() })
}

function invalidateStats(queryClient: ReturnType<typeof useQueryClient>): void {
  queryClient.invalidateQueries({ queryKey: adminKeys.stats() })
  queryClient.invalidateQueries({ queryKey: adminKeys.all })
}

function invalidateUsers(queryClient: ReturnType<typeof useQueryClient>): void {
  queryClient.invalidateQueries({ queryKey: [...adminKeys.all, 'users'] })
  queryClient.invalidateQueries({ queryKey: [...adminKeys.all, 'school-users'] })
}

function invalidateRoles(queryClient: ReturnType<typeof useQueryClient>): void {
  queryClient.invalidateQueries({ queryKey: adminKeys.roles.all() })
}

// ============================================================================
// Organizations
// ============================================================================

export function useCreateAdminOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createAdminOrganization,
    onSuccess: () => {
      invalidateOrganizations(queryClient)
      invalidateStats(queryClient)
    },
  })
}

function organizationUpdateAffectsTierOrQuotas(body: Record<string, unknown>): boolean {
  return 'school_tier' in body || 'expires_at' in body
}

export function useUpdateAdminOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      orgId,
      body,
    }: {
      orgId: number
      body: Record<string, unknown>
    }) => updateAdminOrganization(orgId, body),
    onSuccess: (_data, { orgId, body }) => {
      invalidateOrganizations(queryClient)
      queryClient.invalidateQueries({ queryKey: adminKeys.organization(orgId) })
      invalidateStats(queryClient)
      if (organizationUpdateAffectsTierOrQuotas(body)) {
        invalidateUsers(queryClient)
        queryClient.invalidateQueries({ queryKey: adminKeys.schoolStats(orgId) })
      }
    },
  })
}

export function useDeleteAdminOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, deleteUsers }: { orgId: number; deleteUsers?: boolean }) =>
      deleteAdminOrganization(orgId, deleteUsers),
    onSuccess: () => {
      invalidateOrganizations(queryClient)
      invalidateStats(queryClient)
      invalidateUsers(queryClient)
    },
  })
}

export function useAddAdminOrganizationManager() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, userId }: { orgId: number; userId: number }) =>
      addAdminOrganizationManager(orgId, userId),
    onSuccess: (_data, { orgId }) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.organizationManagers(orgId) })
      invalidateRoles(queryClient)
    },
  })
}

export function useRemoveAdminOrganizationManager() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, userId }: { orgId: number; userId: number }) =>
      removeAdminOrganizationManager(orgId, userId),
    onSuccess: (_data, { orgId }) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.organizationManagers(orgId) })
      invalidateRoles(queryClient)
    },
  })
}

export function useUploadAdminOrganizationMindmateAvatar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, formData }: { orgId: number; formData: FormData }) =>
      uploadAdminOrganizationMindmateAvatar(orgId, formData),
    onSuccess: (_data, { orgId }) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.organization(orgId) })
      queryClient.invalidateQueries({
        queryKey: adminKeys.organizationMindmateDifyHealth(orgId),
      })
    },
  })
}

export function useProbeAdminMindmateDifyHealthDraft() {
  return useMutation({
    mutationFn: probeAdminMindmateDifyHealthDraft,
  })
}

export function useProbeAdminOrganizationMindmateDifyHealth() {
  return useMutation({
    mutationFn: ({
      orgId,
      body = {},
    }: {
      orgId: number
      body?: Record<string, string>
    }) => probeAdminOrganizationMindmateDifyHealth(orgId, body),
  })
}

// ============================================================================
// Users
// ============================================================================

export function useUpdateAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      body,
    }: {
      userId: number
      body: Record<string, unknown>
    }) => updateAdminUser(userId, body),
    onSuccess: (_data, { userId }) => {
      invalidateUsers(queryClient)
      queryClient.invalidateQueries({ queryKey: adminKeys.user(userId) })
      invalidateStats(queryClient)
    },
  })
}

export function useDeleteAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: number) => deleteAdminUser(userId),
    onSuccess: () => {
      invalidateUsers(queryClient)
      invalidateStats(queryClient)
    },
  })
}

export function useUpdateAdminUserRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      updateAdminUserRole(userId, role),
    onSuccess: () => {
      invalidateUsers(queryClient)
      invalidateRoles(queryClient)
    },
  })
}

export function useCreateAdminSchoolUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      organizationId,
      body,
    }: {
      organizationId: number
      body: Record<string, unknown>
    }) => createAdminSchoolUser(body, organizationId),
    onSuccess: () => {
      invalidateUsers(queryClient)
      invalidateStats(queryClient)
    },
  })
}

export function useCreateAdminSchoolUsersBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      organizationId,
      body,
    }: {
      organizationId: number
      body: Record<string, unknown>
    }) => createAdminSchoolUsersBatch(body, organizationId),
    onSuccess: () => {
      invalidateUsers(queryClient)
      invalidateStats(queryClient)
    },
  })
}

export function useUpdateAdminSchoolUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      organizationId,
      body,
    }: {
      userId: number
      organizationId: number
      body: Record<string, unknown>
    }) => updateAdminSchoolUser(userId, organizationId, body),
    onSuccess: (_data, { userId, organizationId }) => {
      invalidateUsers(queryClient)
      queryClient.invalidateQueries({ queryKey: adminKeys.user(userId, organizationId) })
    },
  })
}

export function useDeleteAdminSchoolUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      organizationId,
    }: {
      userId: number
      organizationId: number
    }) => deleteAdminSchoolUser(userId, organizationId),
    onSuccess: () => {
      invalidateUsers(queryClient)
      invalidateStats(queryClient)
    },
  })
}

// ============================================================================
// API keys
// ============================================================================

export function useCreateAdminApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createAdminApiKey,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.apiKeys() })
    },
  })
}

export function useDeleteAdminApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteAdminApiKey,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.apiKeys() })
    },
  })
}

// ============================================================================
// MindBot
// ============================================================================

export function useCreateAdminMindbotConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createAdminMindbotConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.mindbot.all() })
    },
  })
}

export function useUpdateAdminMindbotConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      configId,
      body,
    }: {
      configId: number
      body: Record<string, unknown>
    }) => updateAdminMindbotConfig(configId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.mindbot.all() })
    },
  })
}

export function useDeleteAdminMindbotConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteAdminMindbotConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.mindbot.all() })
    },
  })
}

export function useMoveAdminMindbotConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      configId,
      body,
    }: {
      configId: number
      body: Record<string, unknown>
    }) => moveAdminMindbotConfig(configId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.mindbot.all() })
    },
  })
}

export function useRotateAdminMindbotCallbackToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: rotateAdminMindbotCallbackToken,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.mindbot.all() })
    },
  })
}

// ============================================================================
// Features / env
// ============================================================================

export function useUpdateAdminFeatureOrgAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateAdminFeatureOrgAccess,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...adminKeys.all, 'feature-org-access'] })
    },
  })
}

export function useUpdateAdminEnvSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateAdminEnvSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...adminKeys.all, 'config-features'] })
    },
  })
}

export function useReloadAdminEnvRuntime() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: reloadAdminEnvRuntime,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...adminKeys.all, 'config-features'] })
    },
  })
}

// ============================================================================
// Database
// ============================================================================

export function useScanAdminDatabase() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: scanAdminDatabase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.all() })
    },
  })
}

export function useExportAdminDatabase() {
  return useMutation({
    mutationFn: exportAdminDatabase,
  })
}

export function useImportAdminDatabaseDump() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: importAdminDatabaseDump,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.all() })
    },
  })
}

export function useAnalyzeAdminDatabaseDump() {
  return useMutation({
    mutationFn: analyzeAdminDatabaseDump,
  })
}

export function useMergeAdminDatabaseDump() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: mergeAdminDatabaseDump,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.all() })
      invalidateStats(queryClient)
    },
  })
}

export function useCleanupAdminDatabaseOrphans() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cleanupAdminDatabaseOrphans,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.all() })
    },
  })
}

// ============================================================================
// Teacher usage
// ============================================================================

export function useUpdateAdminTeacherUsageConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AdminTeacherUsageConfig) => updateAdminTeacherUsageConfig(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.teacherUsage.all() })
    },
  })
}

export function useRecomputeAdminTeacherUsage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: AdminTeacherUsageConfig) => {
      await updateAdminTeacherUsageConfig(body)
      return recomputeAdminTeacherUsage()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.teacherUsage.all() })
    },
  })
}

// ============================================================================
// Library
// ============================================================================

export function useScanAdminLibrary() {
  return useMutation({
    mutationFn: scanAdminLibrary,
  })
}

export function useRegisterAdminLibraryBook() {
  return useMutation({
    mutationFn: registerAdminLibraryBook,
  })
}

export function useRegisterAdminLibraryBooksBatch() {
  return useMutation({
    mutationFn: registerAdminLibraryBooksBatch,
  })
}

export function useRepairAdminLibrary() {
  return useMutation({
    mutationFn: repairAdminLibrary,
  })
}

export function useUpdateAdminLibraryDocumentVisibility() {
  return useMutation({
    mutationFn: ({
      docId,
      body,
    }: {
      docId: number
      body: Record<string, unknown>
    }) => updateAdminLibraryDocumentVisibility(docId, body),
  })
}

export function useGenerateAdminLibraryDocumentCover() {
  return useMutation({
    mutationFn: generateAdminLibraryDocumentCover,
  })
}

export function useDeleteAdminLibraryDocument() {
  return useMutation({
    mutationFn: ({
      docId,
      deleteFiles,
    }: {
      docId: number
      deleteFiles?: boolean
    }) => deleteAdminLibraryDocument(docId, deleteFiles),
  })
}

export function useRenameAdminLibraryPages() {
  return useMutation({
    mutationFn: renameAdminLibraryPages,
  })
}
