/**
 * da UI messages — merged namespace bundles.
 */
import admin from './admin.ts'
import auth from './auth.ts'
import canvas from './canvas.ts'
import common from './common.ts'
import community from './community.ts'
import knowledge from './knowledge.ts'
import learningSpace from './learningSpace.ts'
import maite from './maite.ts'
import mindmate from './mindmate.ts'
import notification from './notification.ts'
import showcase from './showcase.ts'
import sidebar from './sidebar.ts'
import { thinkingCoinsMessages as thinkingCoins } from './thinkingCoins.ts'
import training from './training.ts'
import workshop from './workshop.ts'
import zhihui from './zhihui.ts'

export default {
  ...common,
  ...mindmate,
  ...maite,
  ...canvas,
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
