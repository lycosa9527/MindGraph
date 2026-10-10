# `.mg` diagram interchange

`.mg` is an obfuscated JSON diagram spec. The key is derived in the browser from a fixed label.

Source of truth: [`frontend/src/utils/mgInterchange.ts`](../frontend/src/utils/mgInterchange.ts).

Decode from the repo root:

```bash
python scripts/decode_mg_file.py path.mg
```

The CLI accepts **v1.1** and **v2.0** only. The browser importer also accepts legacy **MG1**.

## Wire layout

Key material (all versions): SHA-256 of the UTF-8 label `MindGraph.MG.interchange.v1`, first 32 bytes, AES-256-GCM. IV is 12 bytes. The GCM auth tag is the last 16 bytes of the ciphertext blob.

| Version | Header | Body |
|---------|--------|------|
| v1.1 mono export | ASCII `MG`, major `0x01`, minor `0x01` (4 bytes) | 12-byte IV, then ciphertext including the auth tag |
| v2.0 bilingual export | ASCII `MG`, major `0x02`, minor `0x00` | Same IV and ciphertext layout, same key |
| v1.0 legacy | ASCII `MG1` (3 bytes) | IV, then ciphertext. Import only |

Plain JSON inside a `.mg` file is rejected.

Display labels in the codec: `MG_INTERCHANGE_VERSION_LABEL` (`1.1`) and `MG_V2_VERSION_LABEL` (`2.0`).
