export const BB_REFERENCE_PRESETS = [
  {
    id: 'base_42',
    label: 'Base 42d',
    description: 'Configuración estándar de referencia BB.',
    values: {
      produccion_dias_hasta_faena: 42,
      produccion_tolerancia_cruce_dias: 3,
      produccion_mortalidad_min: 0.045,
      produccion_mortalidad_max: 0.075,
      produccion_mortalidad_paso: 0.005,
    },
  },
  {
    id: 'ciclo_corto_40',
    label: 'Ciclo Corto 40d',
    description: 'Útil cuando la cohorte llega antes a la ventana de faena.',
    values: {
      produccion_dias_hasta_faena: 40,
      produccion_tolerancia_cruce_dias: 2,
      produccion_mortalidad_min: 0.035,
      produccion_mortalidad_max: 0.065,
      produccion_mortalidad_paso: 0.005,
    },
  },
  {
    id: 'ciclo_extendido_44',
    label: 'Ciclo Extendido 44d',
    description: 'Útil cuando la cohorte madura más tarde o se quiere mirar un rango más conservador.',
    values: {
      produccion_dias_hasta_faena: 44,
      produccion_tolerancia_cruce_dias: 3,
      produccion_mortalidad_min: 0.05,
      produccion_mortalidad_max: 0.08,
      produccion_mortalidad_paso: 0.005,
    },
  },
]

const FLOAT_TOLERANCE = 0.0005

function roundValue(value, decimals = 6) {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return Number(value.toFixed(decimals))
}

function inferStepFromCoberturas(coberturas = []) {
  const tasas = coberturas
    .map((item) => Number(item?.tasa))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)

  if (tasas.length < 2) return null

  const diffs = []
  for (let index = 1; index < tasas.length; index += 1) {
    const diff = roundValue((tasas[index] - tasas[index - 1]) / 100)
    if (diff && diff > 0) diffs.push(diff)
  }

  if (diffs.length === 0) return null
  return Math.min(...diffs)
}

function valuesMatch(left, right) {
  if (left == null || right == null) return false
  if (typeof left === 'number' && typeof right === 'number') {
    return Math.abs(left - right) <= FLOAT_TOLERANCE
  }
  return left === right
}

export function getBBReferenceConfigFromParams(params) {
  if (!params) return null
  return {
    produccion_dias_hasta_faena: params.produccion_dias_hasta_faena,
    produccion_tolerancia_cruce_dias: params.produccion_tolerancia_cruce_dias,
    produccion_mortalidad_min: roundValue(params.produccion_mortalidad_min),
    produccion_mortalidad_max: roundValue(params.produccion_mortalidad_max),
    produccion_mortalidad_paso: roundValue(params.produccion_mortalidad_paso),
  }
}

export function getBBReferenceConfigFromCoverage(source) {
  if (!source) return null

  const coberturas = source.coberturas || []
  const tasas = coberturas
    .map((item) => Number(item?.tasa))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)

  return {
    produccion_dias_hasta_faena: source.dias_hasta_faena_referencia ?? null,
    produccion_tolerancia_cruce_dias: source.tolerancia_cruce_dias ?? null,
    produccion_mortalidad_min: tasas.length > 0 ? roundValue(tasas[0] / 100) : null,
    produccion_mortalidad_max: tasas.length > 0 ? roundValue(tasas[tasas.length - 1] / 100) : null,
    produccion_mortalidad_paso: inferStepFromCoberturas(coberturas),
  }
}

export function getMatchingBBReferencePreset(config) {
  if (!config) return null

  return BB_REFERENCE_PRESETS.find((preset) =>
    Object.entries(preset.values).every(([key, value]) => valuesMatch(config[key], value)),
  ) || null
}

export function getBBReferencePresetMeta(config) {
  if (!config) {
    return {
      id: 'none',
      label: 'Sin datos',
      description: 'No se pudo resolver la configuración BB actual.',
      isCustom: true,
    }
  }

  const preset = getMatchingBBReferencePreset(config)
  if (preset) {
    return {
      id: preset.id,
      label: preset.label,
      description: preset.description,
      isCustom: false,
    }
  }

  return {
    id: 'custom',
    label: 'Personalizado',
    description: 'Configuración BB ajustada manualmente.',
    isCustom: true,
  }
}

export function formatBBReferenceSummary(config) {
  if (!config) return 'Sin referencia BB disponible'

  const dias = config.produccion_dias_hasta_faena != null
    ? `${config.produccion_dias_hasta_faena}d`
    : '-'
  const tolerancia = config.produccion_tolerancia_cruce_dias != null
    ? `±${config.produccion_tolerancia_cruce_dias}d`
    : '±-'
  const mortalidadMin = config.produccion_mortalidad_min != null
    ? `${roundValue(config.produccion_mortalidad_min * 100, 1)}%`
    : '-'
  const mortalidadMax = config.produccion_mortalidad_max != null
    ? `${roundValue(config.produccion_mortalidad_max * 100, 1)}%`
    : '-'
  const paso = config.produccion_mortalidad_paso != null
    ? `paso ${roundValue(config.produccion_mortalidad_paso * 100, 1)}%`
    : 'paso -'

  return `${dias} · ${tolerancia} · ${mortalidadMin}–${mortalidadMax} · ${paso}`
}