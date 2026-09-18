/**
 * az UI messages — merged namespace bundles.
 * TRANSLATED — do not overwrite values with English. Add missing keys only (fill new keys from en).
 */

import admin from './admin.ts'
import auth from './auth.ts'
import canvas from './canvas.ts'
import common from './common.ts'
import community from './community.ts'
import showcase from './showcase.ts'
import zhihui from './zhihui.ts'
import knowledge from './knowledge.ts'
import learningSpace from './learningSpace.ts'
import mindmate from './mindmate.ts'
import notification from './notification.ts'
import sidebar from './sidebar.ts'
import { thinkingCoinsMessages as thinkingCoins } from './thinkingCoins.ts'
import maite from './maite.ts'
import workshop from './workshop.ts'
import training from './training.ts'

export default {
  ...common,
  ...mindmate,
  ...canvas,
  ...maite,
  ...workshop,
  ...training,
  ...admin,
  ...knowledge,
  ...learningSpace,
  ...community,
  ...showcase,
  ...zhihui,
  ...sidebar,
  ...auth,
  ...notification,
  ...thinkingCoins,
} as const
