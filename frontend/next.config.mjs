import fs from 'node:fs'
import path from 'node:path'

const pyprojectPath = path.resolve(process.cwd(), '..', 'pyproject.toml')
const pyproject = fs.readFileSync(pyprojectPath, 'utf8')

function readTomlString(section, key) {
  let activeSection = ''

  for (const sourceLine of pyproject.split(/\r?\n/)) {
    const line = sourceLine.trim()
    const sectionMatch = /^\[([^\]]+)]$/.exec(line)
    if (sectionMatch) {
      activeSection = sectionMatch[1]
      continue
    }
    if (activeSection !== section || line.startsWith('#')) continue

    const valueMatch = new RegExp(`^${key}\\s*=\\s*"([^"]+)"`).exec(line)
    if (valueMatch) return valueMatch[1]
  }

  throw new Error(`Campo ${section}.${key} não encontrado em ${pyprojectPath}`)
}

const appVersion = readTomlString('project', 'version')
const releaseStage = readTomlString('tool.eurecachat', 'release-stage')

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  env: {
    NEXT_PUBLIC_APP_VERSION: appVersion,
    NEXT_PUBLIC_RELEASE_STAGE: releaseStage,
  },
  trailingSlash: true,
  turbopack: {
    root: process.cwd(),
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
