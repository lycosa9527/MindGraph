<script setup lang="ts">

/**

 * Invite users tab — org invitation code (school_admin / superadmin) or platform trial placeholder.

 */

import { computed, onMounted, ref, watch } from 'vue'



import { DocumentCopy, Loading } from '@element-plus/icons-vue'



import {

  GLOBAL_ORG_SENTINEL,

  useAdminOrgContext,

} from '@/composables/admin/useAdminOrgContext'

import { useAdminAccess } from '@/composables/admin/useAdminAccess'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'

import { useAuthStore } from '@/stores'

import { apiRequest } from '@/utils/apiClient'



const { t } = useLanguage()

const notify = useNotifications()

const { publicSiteUrl } = usePublicSiteUrl()

const authStore = useAuthStore()

const { can, effectiveOrgId, isReadOnly } = useAdminAccess()

const { selectedOrgId, routeOrgId } = useAdminOrgContext()



const isLoading = ref(false)

const invitationCode = ref('')

const orgName = ref('')

const organizations = ref<{ id: number; name: string; code: string }[]>([])



const isPlatformTrialOnly = computed(

  () =>

    !can('scope.org') &&

    !authStore.isSuperAdmin &&

    can('tab.invites.view')

)



const showSuperadminOrgPicker = computed(

  () => authStore.isSuperAdmin && routeOrgId.value == null

)



const showOrgInvites = computed(

  () => can('scope.org') || (authStore.isSuperAdmin && routeOrgId.value != null)

)



const orgId = computed((): number | null => {

  if (can('scope.org')) {

    return effectiveOrgId.value

  }

  if (authStore.isSuperAdmin) {

    return routeOrgId.value

  }

  return null

})



async function loadOrganizations(): Promise<void> {

  if (!authStore.isSuperAdmin) {

    return

  }

  const res = await apiRequest('/api/auth/admin/organizations')

  if (!res.ok) {

    return

  }

  const data = await res.json()

  organizations.value = data.map((o: { id: number; name: string; code: string }) => ({

    id: o.id,

    name: o.name,

    code: o.code,

  }))

}



async function loadOrgInvitation(): Promise<void> {

  const id = orgId.value

  if (id == null) {

    return

  }

  isLoading.value = true

  try {

    const res = await apiRequest(`/api/auth/admin/stats/school?organization_id=${id}`)

    if (!res.ok) {

      return

    }

    const data = await res.json()

    orgName.value = data.organization?.name ?? ''

    invitationCode.value = (data.organization?.invitation_code ?? '').trim()

  } finally {

    isLoading.value = false

  }

}



async function copyInvite(): Promise<void> {

  if (!invitationCode.value) {

    return

  }

  const text = t('admin.schoolInviteCopyPayload', {

    siteUrl: publicSiteUrl.value,

    code: invitationCode.value,

  })

  try {

    await navigator.clipboard.writeText(text)

    notify.success(t('notification.copied'))

  } catch {

    notify.error(t('notification.copyFailed'))

  }

}



watch(orgId, () => {

  if (showOrgInvites.value) {

    void loadOrgInvitation()

  }

})



onMounted(() => {

  void loadOrganizations()

  if (showOrgInvites.value) {

    void loadOrgInvitation()

  }

})

</script>



<template>

  <div class="max-w-2xl">

    <template v-if="showOrgInvites">

      <div v-if="isLoading" class="py-12 text-center">

        <el-icon class="is-loading" :size="32"><Loading /></el-icon>

      </div>

      <template v-else-if="orgId != null">

        <h2 class="text-lg font-semibold mb-2">{{ t('admin.inviteUsers') }}</h2>

        <p v-if="orgName" class="text-sm text-gray-500 mb-4">{{ orgName }}</p>

        <el-card shadow="hover">

          <p class="text-sm text-gray-500 mb-2">{{ t('admin.invitationCode') }}</p>

          <p class="text-2xl font-mono font-bold mb-4">{{ invitationCode || '—' }}</p>

          <el-button

            v-if="!isReadOnly"

            type="primary"

            round

            :disabled="!invitationCode"

            @click="copyInvite"

          >

            <el-icon class="el-icon--left"><DocumentCopy /></el-icon>

            {{ t('admin.copyShareMessage') }}

          </el-button>

        </el-card>

      </template>

      <p v-else class="text-gray-500">{{ t('admin.schoolDashboardNoOrg') }}</p>

    </template>



    <template v-else-if="showSuperadminOrgPicker">

      <h2 class="text-lg font-semibold mb-2">{{ t('admin.inviteUsers') }}</h2>

      <p class="text-sm text-gray-500 mb-4">{{ t('admin.inviteUsersSelectSchool') }}</p>

      <el-select

        v-if="organizations.length > 0"

        v-model="selectedOrgId"

        filterable

        :placeholder="t('admin.selectSchool')"

        style="width: 280px"

      >

        <el-option

          v-for="org in organizations"

          :key="org.id"

          :label="org.name"

          :value="org.id"

        />

      </el-select>

    </template>



    <template v-else-if="isPlatformTrialOnly">

      <h2 class="text-lg font-semibold mb-2">{{ t('admin.inviteUsers') }}</h2>

      <el-alert

        type="info"

        :closable="false"

        show-icon

        :title="t('admin.inviteUsersComingSoonTitle')"

        :description="t('admin.inviteUsersComingSoon')"

      />

    </template>

  </div>

</template>

