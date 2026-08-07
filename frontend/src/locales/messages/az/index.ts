/**
 * az UI messages — merged namespace bundles.
 */
import admin from './admin.ts'
import auth from './auth.ts'
import canvas from './canvas.ts'
import common from './common.ts'
import community from './community.ts'
import showcase from './showcase.ts'
import zhihui from './zhihui.ts'
import knowledge from './knowledge.ts'
import mindmate from './mindmate.ts'
import notification from './notification.ts'
import sidebar from './sidebar.ts'
import { thinkingCoinsMessages as thinkingCoins } from './thinkingCoins.ts'
import maite from './maite.ts'
import workshop from './workshop.ts'

export default {
  ...common,
  ...mindmate,
  ...canvas,
  ...maite,
  ...workshop,
  ...admin,
  ...knowledge,
  ...community,
  ...showcase,
  ...zhihui,
  ...sidebar,
  ...auth,
  ...notification,
  ...thinkingCoins,
} as const
