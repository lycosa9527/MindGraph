/**
 * en UI messages — merged namespace bundles.
 */
import common from './common'
import mindmate from './mindmate'
import canvas from './canvas'
import workshop from './workshop'
import admin from './admin'
import knowledge from './knowledge'
import community from './community'
import sidebar from './sidebar'
import auth from './auth'
import notification from './notification'

export default {
  ...common,
  ...mindmate,
  ...canvas,
  ...workshop,
  ...admin,
  ...knowledge,
  ...community,
  ...sidebar,
  ...auth,
  ...notification,
} as const
