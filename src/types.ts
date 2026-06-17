export type CriticalityLevel = 'Low' | 'Medium' | 'High' | 'Critical'

export type ConfidenceLevel =
  | 'Verified'
  | 'Estimated'
  | 'AI Suggested'
  | 'Needs Manual Review'
  | 'Unavailable Online'

export type FieldKind =
  | 'currency'
  | 'days'
  | 'number'
  | 'score'
  | 'risk'
  | 'text'

export type FieldValue = number | string

export type Requirement = {
  productName: string
  productCategory: string
  productSpecs: string
  quantity: number
  qualityRequirements: string
  complianceRequirements: string
  targetCost: number
  requiredLeadTime: number
  forecastedDemand: number
  approvedMaterials: string
  technicalDrawings: string
  packagingRequirements: string
  deliveryLocation: string
  criticality: CriticalityLevel
}

export type FieldDefinition = {
  key: string
  label: string
  kind: FieldKind
}

export type FrameworkSection = {
  id:
    | 'cost'
    | 'leadTime'
    | 'capability'
    | 'qualityRisk'
    | 'geopoliticalRisk'
    | 'logistics'
    | 'contract'
  label: string
  description: string
  fields: FieldDefinition[]
}

export type Supplier = {
  id: string
  name: string
  country: string
  region: string
  website: string
  productMatch: string
  certifications: string
  annualCapacity: number
  customerNotes: string
  confidenceLevel: ConfidenceLevel
  values: Record<string, FieldValue>
}

export type Weights = {
  landedCost: number
  tco: number
  leadTime: number
  capability: number
  qualityRisk: number
  geopoliticalRisk: number
  logistics: number
  contract: number
}

export type SupplierMetrics = {
  supplierId: string
  supplierName: string
  totalLandedCost: number
  totalCostOfOwnership: number
  totalOrderCost: number
  totalOrderTco: number
  totalLeadTime: number
  capabilityAverage: number
  qualityRiskAverage: number
  geopoliticalRiskAverage: number
  logisticsRiskAverage: number
  contractScoreAverage: number
  dimensionScores: {
    cost: number
    leadTime: number
    capability: number
    quality: number
    geopolitical: number
    logistics: number
    contract: number
  }
  finalScore: number
}

export type RecommendationSummary = {
  bestOverall?: SupplierMetrics
  lowestCost?: SupplierMetrics
  fastestLeadTime?: SupplierMetrics
  highestRisk?: SupplierMetrics
  backupSupplier?: SupplierMetrics
}
