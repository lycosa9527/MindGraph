/**
 * Minimal Java Object Serialization stream reader for IHMC `.cmap` blobs.
 * Parses TC_* records and builds handles; reconstructed instances include `annotations`
 * for classes with SC_WRITE_METHOD (e.g. `java.util.Hashtable`) so IHMC proposition data
 * is recoverable alongside `nlk.base.GraphicalConcept` layouts.
 *
 * Reference: Java Object Serialization Specification (stream protocol).
 */

const TC_NULL = 0x70
const TC_REFERENCE = 0x71
const TC_CLASSDESC = 0x72
const TC_OBJECT = 0x73
const TC_STRING = 0x74
const TC_ARRAY = 0x75
const TC_CLASS = 0x76
const TC_BLOCKDATA = 0x77
const TC_ENDBLOCKDATA = 0x78
const TC_RESET = 0x79
const TC_BLOCKDATALONG = 0x7a
const TC_EXCEPTION = 0x7b
const TC_LONGSTRING = 0x7c
const TC_PROXYCLASSDESC = 0x7d
const TC_ENUM = 0x7e

const BASE_WIRE_HANDLE = 0x7e0000

const SKIP_CUSTOM_MAX_STEPS = 500_000

const SC_WRITE_METHOD = 0x01
const SC_EXTERNALIZABLE = 0x04
const SC_BLOCK_DATA = 0x08

export class JavaParseError extends Error {
  constructor(
    message: string,
    public readonly offset: number
  ) {
    super(message)
    this.name = 'JavaParseError'
  }
}

type FieldDesc =
  | { kind: 'primitive'; code: string; name: string }
  | { kind: 'object'; code: string; typeName: string; name: string }

export interface ClassDescParsed {
  kind: 'class'
  name: string
  serialVersionUid: bigint
  flags: number
  fields: FieldDesc[]
  super: ClassDescParsed | null
}

export interface InstanceParsed {
  kind: 'instance'
  classDesc: ClassDescParsed
  /** Superclass-first field order, aligned with flattened field descriptors */
  values: unknown[]
  /**
   * Custom data from writeObject blocks (paired key/value payloads for Hashtable, etc.).
   * One flattened list per superclass level that has SC_WRITE_METHOD, in stream order.
   */
  annotations: unknown[]
}

export interface ParseResult {
  handles: unknown[]
}

interface ParseCtx {
  buf: Uint8Array
  view: DataView
  handles: unknown[]
}

function assignHandle(ctx: ParseCtx, obj: unknown): number {
  ctx.handles.push(obj)
  return BASE_WIRE_HANDLE + ctx.handles.length - 1
}

function readMagicHeader(view: DataView, posRef: { pos: number }): void {
  if (view.byteLength - posRef.pos < 4) {
    throw new JavaParseError('Truncated stream header', posRef.pos)
  }
  const magic = view.getUint16(posRef.pos, false)
  const version = view.getUint16(posRef.pos + 2, false)
  posRef.pos += 4
  if (magic !== 0xaced || version !== 5) {
    throw new JavaParseError('Not a Java serialization stream', posRef.pos - 4)
  }
}

function readU8(view: DataView, buf: Uint8Array, posRef: { pos: number }): number {
  if (posRef.pos >= view.byteLength) throw new JavaParseError('EOF reading u8', posRef.pos)
  const v = buf[posRef.pos]
  posRef.pos += 1
  return v
}

function readU16(view: DataView, buf: Uint8Array, posRef: { pos: number }): number {
  if (posRef.pos + 2 > view.byteLength) throw new JavaParseError('EOF reading u16', posRef.pos)
  const v = view.getUint16(posRef.pos, false)
  posRef.pos += 2
  return v
}

function readI32(view: DataView, buf: Uint8Array, posRef: { pos: number }): number {
  if (posRef.pos + 4 > view.byteLength) throw new JavaParseError('EOF reading i32', posRef.pos)
  const v = view.getInt32(posRef.pos, false)
  posRef.pos += 4
  return v
}

function readI64(view: DataView, buf: Uint8Array, posRef: { pos: number }): bigint {
  if (posRef.pos + 8 > view.byteLength) throw new JavaParseError('EOF reading i64', posRef.pos)
  const hi = view.getInt32(posRef.pos, false)
  const lo = view.getUint32(posRef.pos + 4, false)
  posRef.pos += 8
  return (BigInt(hi) << 32n) | BigInt(lo)
}

/**
 * Decode JVM "modified UTF-8" (java.io.DataInput.readUTF), not standard UTF-8.
 * Using TextDecoder('utf-8') mis-counts bytes vs chars and desynchronizes the stream.
 */
function decodeJvmModifiedUtf8(bytearr: Uint8Array, byteOffsetInStream: number): string {
  const utflen = bytearr.length
  let count = 0
  const chararr: number[] = []
  const chunkSize = 8192
  const parts: string[] = []
  const flush = (): void => {
    if (chararr.length === 0) return
    for (let i = 0; i < chararr.length; i += chunkSize) {
      const slice = chararr.slice(i, i + chunkSize)
      parts.push(String.fromCharCode(...slice))
    }
    chararr.length = 0
  }
  while (count < utflen) {
    const cb = bytearr[count]
    if (cb === undefined) {
      throw new JavaParseError('Truncated JVM modified UTF-8', byteOffsetInStream + count)
    }
    const c = cb & 0xff
    const hi = c >> 4
    if (hi <= 7) {
      count += 1
      chararr.push(c)
    } else if (hi === 12 || hi === 13) {
      count += 2
      if (count > utflen) {
        throw new JavaParseError(
          'Truncated JVM modified UTF-8 (2-byte)',
          byteOffsetInStream + count
        )
      }
      const b2 = bytearr[count - 1]
      if (b2 === undefined) {
        throw new JavaParseError('Truncated JVM modified UTF-8', byteOffsetInStream + count)
      }
      const char2 = b2 & 0xff
      if ((char2 & 0xc0) !== 0x80) {
        throw new JavaParseError('Bad JVM UTF-8 continuation', byteOffsetInStream + count)
      }
      chararr.push(((c & 0x1f) << 6) | (char2 & 0x3f))
    } else if (hi === 14) {
      count += 3
      if (count > utflen) {
        throw new JavaParseError(
          'Truncated JVM modified UTF-8 (3-byte)',
          byteOffsetInStream + count
        )
      }
      const b2 = bytearr[count - 2]
      const b3 = bytearr[count - 1]
      if (b2 === undefined || b3 === undefined) {
        throw new JavaParseError('Truncated JVM modified UTF-8', byteOffsetInStream + count)
      }
      const char2 = b2 & 0xff
      const char3 = b3 & 0xff
      if ((char2 & 0xc0) !== 0x80 || (char3 & 0xc0) !== 0x80) {
        throw new JavaParseError('Bad JVM UTF-8 continuation', byteOffsetInStream + count)
      }
      chararr.push(((c & 0x0f) << 12) | ((char2 & 0x3f) << 6) | (char3 & 0x3f))
    } else {
      throw new JavaParseError(
        `Invalid JVM modified UTF-8 lead byte 0x${c.toString(16)}`,
        byteOffsetInStream + count
      )
    }
    if (chararr.length >= chunkSize) flush()
  }
  flush()
  return parts.join('')
}

function readModifiedUtf8(
  view: DataView,
  buf: Uint8Array,
  posRef: { pos: number },
  len: number
): string {
  if (posRef.pos + len > view.byteLength) throw new JavaParseError('EOF reading utf', posRef.pos)
  const slice = buf.subarray(posRef.pos, posRef.pos + len)
  const start = posRef.pos
  posRef.pos += len
  return decodeJvmModifiedUtf8(slice, start)
}

function readUtfLikeBody(view: DataView, buf: Uint8Array, posRef: { pos: number }): string {
  const len = readU16(view, buf, posRef)
  return readModifiedUtf8(view, buf, posRef, len)
}

function resolveHandle(handles: unknown[], wireHandle: number): unknown {
  const idx = wireHandle - BASE_WIRE_HANDLE
  if (idx < 0 || idx >= handles.length) {
    throw new JavaParseError(`Bad wire handle ${wireHandle}`, wireHandle)
  }
  return handles[idx]
}

function flattenFieldDescriptors(desc: ClassDescParsed | null): FieldDesc[] {
  if (!desc) return []
  return [...flattenFieldDescriptors(desc.super), ...desc.fields]
}

export function instanceFieldMap(inst: InstanceParsed): Map<string, unknown> {
  const descriptors = flattenFieldDescriptors(inst.classDesc)
  const map = new Map<string, unknown>()
  for (let i = 0; i < descriptors.length; i += 1) {
    map.set(descriptors[i].name, inst.values[i])
  }
  return map
}

export function readContentElement(posRef: { pos: number }, ctx: ParseCtx): unknown {
  const tc = readU8(ctx.view, ctx.buf, posRef)
  switch (tc) {
    case TC_NULL:
      return null
    case TC_REFERENCE: {
      const wire = readI32(ctx.view, ctx.buf, posRef)
      return resolveHandle(ctx.handles, wire)
    }
    case TC_STRING:
    case TC_LONGSTRING:
      return readNewString(tc, posRef, ctx)
    case TC_CLASS:
      readUtfLikeBody(ctx.view, ctx.buf, posRef)
      assignHandle(ctx, { kind: 'java-class-marker' })
      return ctx.handles[ctx.handles.length - 1]
    case TC_ARRAY:
      return readNewArray(posRef, ctx)
    case TC_ENUM: {
      const cd = readClassDesc(posRef, ctx)
      const nameVal = readContentElement(posRef, ctx)
      const inst: InstanceParsed = {
        kind: 'instance',
        classDesc: cd ?? {
          kind: 'class',
          name: 'java.lang.Enum',
          serialVersionUid: 0n,
          flags: 0,
          fields: [],
          super: null,
        },
        values: [nameVal],
        annotations: [],
      }
      assignHandle(ctx, inst)
      return inst
    }
    case TC_OBJECT: {
      const classDesc = readClassDesc(posRef, ctx)
      if (!classDesc) throw new JavaParseError('OBJECT missing class desc', posRef.pos)
      const inst: InstanceParsed = {
        kind: 'instance',
        classDesc,
        values: [],
        annotations: [],
      }
      assignHandle(ctx, inst)
      inst.values.push(...readObjectData(classDesc, posRef, ctx, inst))
      return inst
    }
    case TC_CLASSDESC:
      throw new JavaParseError('Unexpected naked TC_CLASSDESC', posRef.pos - 1)
    case TC_RESET:
      ctx.handles.length = 0
      return undefined
    case TC_BLOCKDATA: {
      const ln = readU8(ctx.view, ctx.buf, posRef)
      posRef.pos += ln
      return undefined
    }
    case TC_BLOCKDATALONG: {
      const ln = readI32(ctx.view, ctx.buf, posRef)
      if (ln < 0 || posRef.pos + ln > ctx.buf.length) {
        throw new JavaParseError('Bad BLOCKDATALONG length', posRef.pos)
      }
      posRef.pos += ln
      return undefined
    }
    case TC_ENDBLOCKDATA:
      return undefined
    case TC_EXCEPTION:
      throw new JavaParseError('TC_EXCEPTION unsupported', posRef.pos - 1)
    default:
      throw new JavaParseError(`Unsupported TC ${tc}`, posRef.pos - 1)
  }
}

function skipAnnotation(posRef: { pos: number }, ctx: ParseCtx): void {
  while (true) {
    if (posRef.pos >= ctx.buf.length) throw new JavaParseError('EOF in annotations', posRef.pos)
    const peek = ctx.buf[posRef.pos]
    if (peek === TC_ENDBLOCKDATA) {
      posRef.pos += 1
      return
    }
    readContentElement(posRef, ctx)
  }
}

/**
 * Field type signature after name (ObjectStreamClass.readNonProxy): TC_STRING,
 * TC_LONGSTRING, TC_REFERENCE, or TC_NULL — same as ObjectInputStream.readTypeString().
 */
function readTypeString(posRef: { pos: number }, ctx: ParseCtx): string {
  const val = readContentElement(posRef, ctx)
  if (typeof val === 'string') return val
  throw new JavaParseError('Expected string field signature', posRef.pos)
}

function readFieldDescriptor(posRef: { pos: number }, ctx: ParseCtx): FieldDesc {
  const codeByte = readU8(ctx.view, ctx.buf, posRef)
  const code = String.fromCharCode(codeByte)
  const name = readUtfLikeBody(ctx.view, ctx.buf, posRef)
  if (code === 'L' || code === '[') {
    const typeName = readTypeString(posRef, ctx)
    return { kind: 'object', code, typeName, name }
  }
  return { kind: 'primitive', code, name }
}

function readNewClassDesc(posRef: { pos: number }, ctx: ParseCtx): ClassDescParsed {
  const name = readUtfLikeBody(ctx.view, ctx.buf, posRef)
  const serialVersionUid = readI64(ctx.view, ctx.buf, posRef)
  const desc: ClassDescParsed = {
    kind: 'class',
    name,
    serialVersionUid,
    flags: 0,
    fields: [],
    super: null,
  }
  assignHandle(ctx, desc)
  desc.flags = readU8(ctx.view, ctx.buf, posRef)
  const fieldCount = readU16(ctx.view, ctx.buf, posRef)
  desc.fields = []
  for (let i = 0; i < fieldCount; i += 1) {
    desc.fields.push(readFieldDescriptor(posRef, ctx))
  }
  skipAnnotation(posRef, ctx)
  desc.super = readClassDesc(posRef, ctx)
  return desc
}

/** Dynamic proxy class descriptor (IHMC streams sometimes include these). */
function readNewProxyDesc(posRef: { pos: number }, ctx: ParseCtx): ClassDescParsed {
  const numIfaces = readI32(ctx.view, ctx.buf, posRef)
  if (numIfaces < 0 || numIfaces > 65535) {
    throw new JavaParseError('Bad proxy interface count', posRef.pos)
  }
  for (let i = 0; i < numIfaces; i += 1) {
    readUtfLikeBody(ctx.view, ctx.buf, posRef)
  }
  skipCustomData(posRef, ctx)
  const superDesc = readClassDesc(posRef, ctx)
  const desc: ClassDescParsed = {
    kind: 'class',
    name: 'java.lang.reflect.Proxy',
    serialVersionUid: 0n,
    flags: 0,
    fields: [],
    super: superDesc,
  }
  assignHandle(ctx, desc)
  return desc
}

function readClassDesc(posRef: { pos: number }, ctx: ParseCtx): ClassDescParsed | null {
  const tc = readU8(ctx.view, ctx.buf, posRef)
  if (tc === TC_NULL) return null
  if (tc === TC_REFERENCE) {
    const h = readI32(ctx.view, ctx.buf, posRef)
    const d = resolveHandle(ctx.handles, h)
    if (!d || typeof d !== 'object' || (d as ClassDescParsed).kind !== 'class') {
      throw new JavaParseError('Reference did not point at ClassDesc', posRef.pos)
    }
    return d as ClassDescParsed
  }
  if (tc === TC_CLASSDESC) {
    return readNewClassDesc(posRef, ctx)
  }
  if (tc === TC_PROXYCLASSDESC) {
    return readNewProxyDesc(posRef, ctx)
  }
  throw new JavaParseError(`Unexpected class desc TC ${tc}`, posRef.pos - 1)
}

function readPrimitiveField(
  code: string,
  posRef: { pos: number },
  ctx: ParseCtx
): number | bigint | boolean {
  switch (code) {
    case 'B':
      return readU8(ctx.view, ctx.buf, posRef)
    case 'C':
      return readU16(ctx.view, ctx.buf, posRef)
    case 'D': {
      if (posRef.pos + 8 > ctx.buf.length) throw new JavaParseError('EOF double', posRef.pos)
      const v = ctx.view.getFloat64(posRef.pos, false)
      posRef.pos += 8
      return v
    }
    case 'F': {
      if (posRef.pos + 4 > ctx.buf.length) throw new JavaParseError('EOF float', posRef.pos)
      const v = ctx.view.getFloat32(posRef.pos, false)
      posRef.pos += 4
      return v
    }
    case 'I':
      return readI32(ctx.view, ctx.buf, posRef)
    case 'J':
      return readI64(ctx.view, ctx.buf, posRef)
    case 'S':
      return readU16(ctx.view, ctx.buf, posRef)
    case 'Z':
      return readU8(ctx.view, ctx.buf, posRef) !== 0
    default:
      throw new JavaParseError(`Unknown primitive ${code}`, posRef.pos)
  }
}

function readFieldValue(field: FieldDesc, posRef: { pos: number }, ctx: ParseCtx): unknown {
  if (field.kind === 'primitive') {
    return readPrimitiveField(field.code, posRef, ctx)
  }
  return readContentElement(posRef, ctx)
}

function readCustomDataTail(
  posRef: { pos: number },
  ctx: ParseCtx,
  annotationSink: InstanceParsed | undefined,
  classDesc: ClassDescParsed
): void {
  const needsCustom =
    (classDesc.flags & SC_WRITE_METHOD) !== 0 ||
    ((classDesc.flags & SC_EXTERNALIZABLE) !== 0 && (classDesc.flags & SC_BLOCK_DATA) !== 0)
  if (!needsCustom) {
    return
  }
  if (annotationSink && (classDesc.flags & SC_WRITE_METHOD) !== 0) {
    readAnnotationsInto(posRef, ctx, annotationSink.annotations)
    return
  }
  skipCustomData(posRef, ctx)
}

function readAnnotationsInto(posRef: { pos: number }, ctx: ParseCtx, out: unknown[]): void {
  let steps = 0
  while (steps < SKIP_CUSTOM_MAX_STEPS) {
    steps += 1
    if (posRef.pos >= ctx.buf.length) {
      return
    }
    const peek = ctx.buf[posRef.pos]
    if (peek === TC_ENDBLOCKDATA) {
      posRef.pos += 1
      return
    }
    const el = readContentElement(posRef, ctx)
    if (el !== undefined) {
      out.push(el)
    }
  }
  throw new JavaParseError('readAnnotationsInto exceeded step budget', posRef.pos)
}

function readObjectData(
  desc: ClassDescParsed | null,
  posRef: { pos: number },
  ctx: ParseCtx,
  annotationSink?: InstanceParsed
): unknown[] {
  if (!desc) return []
  const values: unknown[] = []
  values.push(...readObjectData(desc.super, posRef, ctx, annotationSink))
  for (const f of desc.fields) {
    values.push(readFieldValue(f, posRef, ctx))
  }
  readCustomDataTail(posRef, ctx, annotationSink, desc)
  return values
}

function skipCustomData(posRef: { pos: number }, ctx: ParseCtx): void {
  let steps = 0
  while (steps < SKIP_CUSTOM_MAX_STEPS) {
    steps += 1
    if (posRef.pos >= ctx.buf.length) return
    const peek = ctx.buf[posRef.pos]
    if (peek === TC_ENDBLOCKDATA) {
      posRef.pos += 1
      return
    }
    readContentElement(posRef, ctx)
  }
  throw new JavaParseError('skipCustomData exceeded step budget', posRef.pos)
}

function readNewString(tc: number, posRef: { pos: number }, ctx: ParseCtx): string {
  let len: number
  if (tc === TC_STRING) {
    len = readU16(ctx.view, ctx.buf, posRef)
  } else if (tc === TC_LONGSTRING) {
    const blen = readI64(ctx.view, ctx.buf, posRef)
    if (blen < 0n || blen > 10_000_000n) {
      throw new JavaParseError('Bad long string length', posRef.pos)
    }
    len = Number(blen)
  } else {
    throw new JavaParseError('Not a string opcode', posRef.pos)
  }
  const s = readModifiedUtf8(ctx.view, ctx.buf, posRef, len)
  assignHandle(ctx, s)
  return s
}

function readNewArray(posRef: { pos: number }, ctx: ParseCtx): unknown[] {
  const desc = readClassDesc(posRef, ctx)
  const arr: unknown[] = []
  assignHandle(ctx, arr)
  const len = readI32(ctx.view, ctx.buf, posRef)
  if (len < 0 || len > 1_000_000) throw new JavaParseError('Bad array length', posRef.pos)
  if (!desc) throw new JavaParseError('Array missing component type', posRef.pos)
  const rootName = desc.name
  if (rootName.startsWith('[')) {
    const comp = rootName.charCodeAt(1)
    const code = String.fromCharCode(comp)
    if (code === 'B') {
      if (posRef.pos + len > ctx.buf.length) throw new JavaParseError('EOF byte array', posRef.pos)
      const slice = ctx.buf.subarray(posRef.pos, posRef.pos + len)
      posRef.pos += len
      for (let i = 0; i < len; i += 1) {
        arr.push(slice[i])
      }
      return arr
    }
    for (let i = 0; i < len; i += 1) {
      if (code === 'L' || code === '[') {
        arr.push(readContentElement(posRef, ctx))
      } else {
        arr.push(readPrimitiveField(code, posRef, ctx))
      }
    }
    return arr
  }
  for (let i = 0; i < len; i += 1) {
    arr.push(readContentElement(posRef, ctx))
  }
  return arr
}

/**
 * Parse entire serialization stream from magic header through all root records.
 */
export function parseJavaSerializationStream(buffer: Uint8Array): ParseResult {
  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength)
  const posRef = { pos: 0 }
  readMagicHeader(view, posRef)
  const ctx: ParseCtx = {
    buf: buffer,
    view,
    handles: [],
  }
  while (posRef.pos < buffer.length) {
    readContentElement(posRef, ctx)
  }
  return { handles: ctx.handles }
}
