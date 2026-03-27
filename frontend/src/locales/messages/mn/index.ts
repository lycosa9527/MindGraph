/**
 * mn UI messages — merged namespace bundles.
 */
import admin from './admin'
import auth from './auth'
import canvas from './canvas'
import common from './common'
import community from './community'
import knowledge from './knowledge'
import mindmate from './mindmate'
import notification from './notification'
import sidebar from './sidebar'
import workshop from './workshop'

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
