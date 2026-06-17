import { frameworkSections } from './data'
import type {
  FrameworkSection,
  RecommendationSummary,
  Requirement,
  Supplier,
  SupplierMetrics,
  Weights,
} from './types'

const landedCostKeys = [
  'unitCost',
  'freightCost',
  'tariffsDuty',
  'insurance',
  'customsBrokerage',
  'packaging',
  'warehousing',
]

const ownershipCostKeys = [
  'qualityFailureCost',
  'expediteCost',
  'inventoryHoldingCost',
  'supplierSwitchingCost',
]

const leadTimeKeys = [
  'productionLeadTime',
  'rawMaterialsLeadTime',
  'supplierPlanningTime',
  'qualityInspectionTime',
  'exportClearanceTime',
  'transitTime',
  'customsClearanceTime',
  'receivingPutawayTime',
  'bufferTime',
]

const sectionById = new Map(frameworkSections.map((section) => [section.id, section]))

export const formatCurrency = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value)

export const formatNumber = (value: number) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(value)

export const formatDays = (value: number) => `${formatNumber(value)} days`

export const getNumericValue = (supplier: Supplier, key: string) => {
  const value = supplier.values[key]

  if (typeof value === 'number') {
    return value
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const sumValues = (supplier: Supplier, keys: string[]) =>
  keys.reduce((total, key) => total + getNumericValue(supplier, key), 0)

const averageSection = (supplier: Supplier, section: FrameworkSection) => {
  const numericFields = section.fields.filter(
    (field) => field.kind === 'score' || field.kind === 'risk',
  )

  if (numericFields.length === 0) {
    return 0
  }

  return (
    numericFields.reduce((total, field) => total + getNumericValue(supplier, field.key), 0) /
    numericFields.length
  )
}

const averageContractScore = (supplier: Supplier) => {
  const contractSection = sectionById.get('contract')

  if (!contractSection) {
    return 0
  }

  const scoredFields = contractSection.fields.filter(
    (field) => field.kind === 'score' || field.kind === 'risk',
  )

  if (scoredFields.length === 0) {
    return 0
  }

  return (
    scoredFields.reduce((total, field) => {
      const value = getNumericValue(supplier, field.key)
      return total + (field.kind === 'risk' ? 6 - value : value)
    }, 0) / scoredFields.length
  )
}

const scoreToHundred = (score: number) => Math.max(0, Math.min(100, ((score - 1) / 4) * 100))

const riskToHundred = (risk: number) => Math.max(0, Math.min(100, ((5 - risk) / 4) * 100))

const lowerIsBetter = (value: number, allValues: number[]) => {
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)

  if (max === min) {
    return 88
  }

  return Math.round(100 - ((value - min) / (max - min)) * 70)
}

export const calculateMetrics = (
  suppliers: Supplier[],
  weights: Weights,
  quantity: number,
): SupplierMetrics[] => {
  const baseMetrics = suppliers.map((supplier) => {
    const totalLandedCost = sumValues(supplier, landedCostKeys)
    const totalCostOfOwnership = totalLandedCost + sumValues(supplier, ownershipCostKeys)
    const totalLeadTime = sumValues(supplier, leadTimeKeys)
    const capabilityAverage = averageSection(supplier, sectionById.get('capability')!)
    const qualityRiskAverage = averageSection(supplier, sectionById.get('qualityRisk')!)
    const geopoliticalRiskAverage = averageSection(supplier, sectionById.get('geopoliticalRisk')!)
    const logisticsRiskAverage = averageSection(supplier, sectionById.get('logistics')!)
    const contractScoreAverage = averageContractScore(supplier)

    return {
      supplierId: supplier.id,
      supplierName: supplier.name,
      totalLandedCost,
      totalCostOfOwnership,
      totalOrderCost: totalLandedCost * quantity,
      totalOrderTco: totalCostOfOwnership * quantity,
      totalLeadTime,
      capabilityAverage,
      qualityRiskAverage,
      geopoliticalRiskAverage,
      logisticsRiskAverage,
      contractScoreAverage,
    }
  })

  const landedCosts = baseMetrics.map((metric) => metric.totalLandedCost)
  const ownershipCosts = baseMetrics.map((metric) => metric.totalCostOfOwnership)
  const leadTimes = baseMetrics.map((metric) => metric.totalLeadTime)
  const totalWeight = Math.max(
    1,
    Object.values(weights).reduce((total, weight) => total + weight, 0),
  )

  return baseMetrics.map((metric) => {
    const landedCostScore = lowerIsBetter(metric.totalLandedCost, landedCosts)
    const ownershipCostScore = lowerIsBetter(metric.totalCostOfOwnership, ownershipCosts)
    const leadTimeScore = lowerIsBetter(metric.totalLeadTime, leadTimes)
    const capabilityScore = scoreToHundred(metric.capabilityAverage)
    const qualityScore = riskToHundred(metric.qualityRiskAverage)
    const geopoliticalScore = riskToHundred(metric.geopoliticalRiskAverage)
    const logisticsScore = riskToHundred(metric.logisticsRiskAverage)
    const contractScore = scoreToHundred(metric.contractScoreAverage)

    const finalScore =
      (landedCostScore * weights.landedCost +
        ownershipCostScore * weights.tco +
        leadTimeScore * weights.leadTime +
        capabilityScore * weights.capability +
        qualityScore * weights.qualityRisk +
        geopoliticalScore * weights.geopoliticalRisk +
        logisticsScore * weights.logistics +
        contractScore * weights.contract) /
      totalWeight

    return {
      ...metric,
      dimensionScores: {
        cost: Math.round((landedCostScore + ownershipCostScore) / 2),
        leadTime: leadTimeScore,
        capability: Math.round(capabilityScore),
        quality: Math.round(qualityScore),
        geopolitical: Math.round(geopoliticalScore),
        logistics: Math.round(logisticsScore),
        contract: Math.round(contractScore),
      },
      finalScore: Math.round(finalScore),
    }
  })
}

export const buildRecommendationSummary = (
  metrics: SupplierMetrics[],
): RecommendationSummary => {
  const byScore = [...metrics].sort((a, b) => b.finalScore - a.finalScore)
  const byCost = [...metrics].sort((a, b) => a.totalLandedCost - b.totalLandedCost)
  const byLeadTime = [...metrics].sort((a, b) => a.totalLeadTime - b.totalLeadTime)
  const byRisk = [...metrics].sort((a, b) => {
    const aRisk = a.qualityRiskAverage + a.geopoliticalRiskAverage + a.logisticsRiskAverage
    const bRisk = b.qualityRiskAverage + b.geopoliticalRiskAverage + b.logisticsRiskAverage
    return bRisk - aRisk
  })

  return {
    bestOverall: byScore[0],
    lowestCost: byCost[0],
    fastestLeadTime: byLeadTime[0],
    highestRisk: byRisk[0],
    backupSupplier: byScore.find((metric) => metric.supplierId !== byScore[0]?.supplierId),
  }
}

export const analyzeRequirement = (requirement: Requirement) => {
  const missing: string[] = []
  const risks: string[] = []
  const questions: string[] = []

  if (!requirement.productSpecs.trim()) missing.push('Product specs')
  if (!requirement.qualityRequirements.trim()) missing.push('Quality requirements')
  if (!requirement.complianceRequirements.trim()) missing.push('Compliance requirements')
  if (!requirement.approvedMaterials.trim()) missing.push('Approved materials')
  if (!requirement.technicalDrawings.trim()) missing.push('Technical drawings or notes')
  if (!requirement.packagingRequirements.trim()) missing.push('Packaging requirements')
  if (!requirement.deliveryLocation.trim()) missing.push('Delivery location')
  if (requirement.targetCost <= 0) missing.push('Target cost')
  if (requirement.requiredLeadTime <= 0) missing.push('Required lead time')

  if (requirement.criticality === 'High' || requirement.criticality === 'Critical') {
    risks.push('Critical parts need dual sourcing, documented qualification, and a backup plan.')
    questions.push('What backup capacity can you reserve if demand spikes or quality holds occur?')
  }

  if (requirement.requiredLeadTime > 0 && requirement.requiredLeadTime < 45) {
    risks.push('The required lead time is tight for global sourcing and may require nearshore options.')
    questions.push('Which lead-time steps can be contractually committed, and where is buffer hidden?')
  }

  if (!requirement.complianceRequirements.toLowerCase().includes('rohs')) {
    risks.push('Compliance scope may be incomplete for regulated product categories.')
  }

  if (requirement.forecastedDemand > requirement.quantity * 3) {
    risks.push('Forecast demand materially exceeds the first order quantity, so scaling ability matters.')
  }

  questions.push('Can the supplier provide recent audit evidence and traceability records?')
  questions.push('Which cost elements are quoted, estimated, or excluded from the commercial offer?')
  questions.push('What payment terms, warranty terms, and IP protections are negotiable?')

  const riskTier =
    requirement.criticality === 'Critical' || risks.length >= 4
      ? 'Critical'
      : requirement.criticality === 'High' || risks.length >= 2
        ? 'Medium-risk'
        : 'Low-risk'

  const strategy =
    riskTier === 'Critical'
      ? 'Run parallel RFQs in two regions, require audit evidence before award, and reserve backup capacity.'
      : riskTier === 'Medium-risk'
        ? 'Shortlist 3-5 suppliers, validate missing data manually, and compare landed cost against lead-time risk.'
        : 'Use a focused RFQ with two verified suppliers and keep a light backup option.'

  return {
    missing,
    risks,
    questions,
    strategy,
    riskTier,
  }
}

export const buildInsights = (
  requirement: Requirement,
  suppliers: Supplier[],
  metrics: SupplierMetrics[],
) => {
  const summary = buildRecommendationSummary(metrics)
  const insights: string[] = []

  if (
    summary.lowestCost &&
    summary.lowestCost.geopoliticalRiskAverage >= 3 &&
    summary.lowestCost.supplierId !== summary.bestOverall?.supplierId
  ) {
    insights.push('This supplier has low unit cost but high geopolitical risk.')
  }

  if (
    summary.fastestLeadTime &&
    summary.fastestLeadTime.dimensionScores.cost < 70 &&
    summary.fastestLeadTime.supplierId !== summary.lowestCost?.supplierId
  ) {
    insights.push('This supplier has the shortest lead time but weaker cost performance.')
  }

  suppliers
    .filter(
      (supplier) =>
        supplier.confidenceLevel === 'Needs Manual Review' ||
        supplier.confidenceLevel === 'Unavailable Online' ||
        supplier.certifications.toLowerCase().includes('pending'),
    )
    .forEach((supplier) => {
      insights.push(
        `${supplier.name} needs manual review because quality certification data is missing or incomplete.`,
      )
    })

  if (requirement.criticality === 'High' || requirement.criticality === 'Critical') {
    insights.push('A backup supplier is recommended because this part is marked critical.')
  }

  metrics
    .filter((metric) => metric.totalLeadTime > requirement.requiredLeadTime)
    .forEach((metric) => {
      insights.push(
        `${metric.supplierName} exceeds the required lead time, reducing flexibility and increasing planning risk.`,
      )
    })

  insights.push('A quote is not the deal. Contract terms should be reviewed before supplier selection.')
  insights.push('Supplier capability matters more than supplier promises.')

  return [...new Set(insights)].slice(0, 8)
}

export const generateMemo = (
  requirement: Requirement,
  suppliers: Supplier[],
  metrics: SupplierMetrics[],
) => {
  const summary = buildRecommendationSummary(metrics)
  const sortedMetrics = [...metrics].sort((a, b) => b.finalScore - a.finalScore)
  const supplierNames = suppliers.map((supplier) => supplier.name).join(', ')
  const manualItems = suppliers
    .filter((supplier) => supplier.confidenceLevel !== 'Verified')
    .map((supplier) => `${supplier.name}: ${supplier.confidenceLevel}`)

  return [
    `Global Sourcing Copilot Recommendation Memo`,
    ``,
    `Product being sourced: ${requirement.productName || 'Not specified'} (${requirement.productCategory || 'category not specified'})`,
    `Supplier options reviewed: ${supplierNames || 'No suppliers added'}`,
    ``,
    `Best supplier recommendation: ${summary.bestOverall?.supplierName ?? 'No recommendation available'} with a score of ${summary.bestOverall?.finalScore ?? 0}/100.`,
    `Backup supplier recommendation: ${summary.backupSupplier?.supplierName ?? 'Add another qualified supplier before award'}.`,
    ``,
    `Cost summary: Lowest landed cost is ${summary.lowestCost?.supplierName ?? 'n/a'} at ${
      summary.lowestCost ? formatCurrency(summary.lowestCost.totalLandedCost) : 'n/a'
    } per unit. Best overall supplier TCO is ${
      summary.bestOverall ? formatCurrency(summary.bestOverall.totalCostOfOwnership) : 'n/a'
    } per unit.`,
    `Lead time summary: Fastest option is ${summary.fastestLeadTime?.supplierName ?? 'n/a'} at ${
      summary.fastestLeadTime ? formatDays(summary.fastestLeadTime.totalLeadTime) : 'n/a'
    }.`,
    `Major risks: Highest combined risk is ${summary.highestRisk?.supplierName ?? 'n/a'}; review quality, geopolitical, and logistics assumptions before award.`,
    `Manual review items: ${manualItems.length ? manualItems.join('; ') : 'No non-verified suppliers flagged.'}`,
    ``,
    `Negotiation suggestions: Clarify included cost elements, lock lead-time commitments, request audit and traceability evidence, negotiate payment terms, document warranty and liability coverage, and reserve capacity for the forecast demand.`,
    ``,
    `Final recommendation reasoning: ${
      summary.bestOverall?.supplierName ?? 'The selected supplier'
    } balances landed cost, total cost of ownership, lead time, supplier capability, and risk better than the other options. Use ${summary.backupSupplier?.supplierName ?? 'a qualified backup'} as a contingency supplier until production quality and commercial terms are fully validated.`,
    ``,
    `Score ranking: ${sortedMetrics
      .map((metric, index) => `${index + 1}. ${metric.supplierName} (${metric.finalScore}/100)`)
      .join(' | ')}`,
  ].join('\n')
}

export const exportComparisonCsv = (
  suppliers: Supplier[],
  metrics: SupplierMetrics[],
  filename = 'supplier-comparison.csv',
) => {
  const fields = frameworkSections.flatMap((section) => section.fields)
  const headers = [
    'Supplier',
    'Country',
    'Region',
    'Confidence Level',
    'Total Landed Cost',
    'Total Cost of Ownership',
    'Total Lead Time',
    'Final Score',
    ...fields.map((field) => field.label),
  ]

  const rows = suppliers.map((supplier) => {
    const metric = metrics.find((item) => item.supplierId === supplier.id)
    return [
      supplier.name,
      supplier.country,
      supplier.region,
      supplier.confidenceLevel,
      metric?.totalLandedCost ?? '',
      metric?.totalCostOfOwnership ?? '',
      metric?.totalLeadTime ?? '',
      metric?.finalScore ?? '',
      ...fields.map((field) => supplier.values[field.key] ?? ''),
    ]
  })

  downloadTextFile(
    [headers, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(','))
      .join('\n'),
    filename,
    'text/csv',
  )
}

export const exportMemoText = (memo: string, filename = 'sourcing-recommendation.txt') => {
  downloadTextFile(memo, filename, 'text/plain')
}

const downloadTextFile = (content: string, filename: string, type: string) => {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
