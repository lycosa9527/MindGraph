/** @type {import('@brookesia/shared-utils').BrookesiaConfig} */
module.exports = {
  cli: {
    sourceRoot: 'src',
    outputPath: 'build',
    releasePath: 'dist',
    signRoot: 'sign',
  },
  // I2: default PNG→LVGL .bin conversion during brookesia build (path relative to sourceRoot).
  convertImages: 'res/images',
  simulator: {
    system: {
      startAppId: 'com.mindgraph.hello',
    },
  },
};
