# Image Conversion Inputs

This directory is the default input directory for the `pack-gui-images` pipeline step.

Put image conversion sources here when the app needs LVGL image binaries in
`build/res/images/`:

- `<id>.bin`: copied directly to `build/res/images/<id>.bin`
- `<id>.c`: converted to `build/res/images/<id>.bin`
- encoded source images such as `<id>.png`, `<id>.jpg`, `<id>.jpeg`, `<id>.webp`: converted to `build/res/images/<id>.bin`

To convert images from this directory, configure `brookesia.config.js` with:

```js
convertImages: {
  path: '../assets/images';
}
```

The path is resolved relative to `cli.sourceRoot`, so `../assets/images` points back
to the project-level `assets/images` directory when `sourceRoot` is `src`.

For source directories under `src/`, or for custom conversion options, use:

```js
convertImages: {
  path: 'res/images',
  colorFormat: 'ARGB8888',
  compress: 'NONE',
}
```

GUI resource descriptors such as `index.json` should stay under `src/res/images/`.
