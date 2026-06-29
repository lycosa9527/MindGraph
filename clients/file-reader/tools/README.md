# ffmpeg for onefile builds

SmartEdu video merge embeds **ffmpeg essentials** inside `mindgraph-file-reader.exe`.

`build_windows.ps1` downloads the essentials build automatically when missing, or replaces a
full ffmpeg build (>150 MB) with essentials to keep the onefile bundle smaller.

Manual override: place `ffmpeg.exe` here before building. Prefer the
[ffmpeg-release-essentials.zip](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip)
build over the full build.

## wx_key.dll (Weixin 4.1.10.31+)

Weixin **4.1.10.31 and newer** no longer keep the SQLCipher passphrase in plaintext
heap memory. Passive RAM scan cannot work; the app uses [wx_key.dll](https://github.com/ycccccccy/wx_key)
to hook `Weixin.exe` when a database is opened.

`build_windows.ps1` downloads `wx_key.dll` v2.1.8 into this folder automatically when
missing. You can also copy it manually from the [wx_key release zip](https://github.com/ycccccccy/wx_key/releases).

Do not place the DLL in a folder path that contains Chinese characters (upstream requirement).
