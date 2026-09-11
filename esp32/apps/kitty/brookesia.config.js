/** @type {import('@brookesia/shared-utils').BrookesiaConfig} */
module.exports = {
  cli: {
    sourceRoot: 'src',
    outputPath: 'build',
    releasePath: 'dist',
    signRoot: 'sign',
  },
  convertImages: {
    path: 'res/images',
    colorFormat: 'ARGB8888',
    compress: 'NONE',
  },
  simulator: {
    system: {
      resolution: '360x360',
      startAppId: 'com.mindgraph.kitty',
    },
  },
};
