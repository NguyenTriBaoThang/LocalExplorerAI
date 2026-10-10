import { readdir, mkdir, rm, copyFile } from 'node:fs/promises'
import { resolve, relative, sep, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = fileURLToPath(new URL('.', import.meta.url))
const repoRoot = resolve(scriptDir, '..', '..', '..')
const sourceRoot = resolve(repoRoot, 'models_3d')
const generatedRoot = resolve(repoRoot, 'apps', 'web', 'public', 'models_3d', '_generated')
const registeredIds = new Set([
  'nhathoducba', 'dinhdoclap', 'chobenthanh', 'nhahatthanhpho',
  'bitexco', 'landmark81', 'hoian', 'vungtauchrist',
])

function toSlug(value) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
    .toLowerCase()
    .slice(0, 64)
}

async function findGlbs(directory) {
  const found = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory() && !entry.name.startsWith('.')) {
      found.push(...await findGlbs(path))
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.glb')) {
      found.push(path)
    }
  }
  return found.sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' }))
}

let folders = []
try {
  folders = (await readdir(sourceRoot, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.') && !entry.name.startsWith('_'))
    .sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }))
} catch (error) {
  if (error.code !== 'ENOENT') throw error
}

// This directory is generated exclusively by this script. Existing hand-managed
// static GLBs in public/models_3d are left untouched.
await rm(generatedRoot, { recursive: true, force: true })
let copied = 0
const usedIds = new Set()

for (const folder of folders) {
  const sourceFolder = resolve(sourceRoot, folder.name)
  const glbs = await findGlbs(sourceFolder)
  for (const sourceGlb of glbs) {
    const fileStem = basename(sourceGlb).replace(/\.glb$/i, '')
    const id = toSlug(glbs.length === 1 ? folder.name : `${folder.name}-${fileStem}`)
    if (!id || usedIds.has(id) || registeredIds.has(id)) {
      console.warn(`[3D models] Skipping invalid or duplicate model id: ${folder.name}/${basename(sourceGlb)}`)
      continue
    }

    usedIds.add(id)
    const targetFolder = resolve(generatedRoot, id)
    await mkdir(targetFolder, { recursive: true })
    await copyFile(sourceGlb, resolve(targetFolder, 'model.glb'))
    copied += 1

    // A single-model folder may provide model.json; multi-model folders use
    // one sidecar per GLB, e.g. temple.glb + temple.json.
    const descriptor = glbs.length === 1
      ? resolve(sourceFolder, 'model.json')
      : sourceGlb.replace(/\.glb$/i, '.json')
    try {
      await copyFile(descriptor, resolve(targetFolder, 'model.json'))
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
    const originalRelativePath = relative(sourceFolder, sourceGlb).split(sep).join('/')
    console.log(`[3D models] ${folder.name} -> /models_3d/_generated/${id}/model.glb (${originalRelativePath})`)
  }
}

console.log(`[3D models] Prepared ${copied} drop-in model pack(s).`)
