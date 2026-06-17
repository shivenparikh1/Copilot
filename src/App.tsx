import {
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle2,
  ClipboardList,
  Download,
  Factory,
  FileText,
  Globe2,
  PackageCheck,
  Plus,
  Save,
  Search,
  Settings2,
  ShieldAlert,
  Sparkles,
  TableProperties,
  Truck,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  confidenceLevels,
  criticalityLevels,
  defaultWeights,
  frameworkSections,
  sampleRequirement,
  sampleSuppliers,
} from './data'
import {
  analyzeRequirement,
  buildInsights,
  buildRecommendationSummary,
  calculateMetrics,
  exportComparisonCsv,
  exportMemoText,
  formatCurrency,
  formatDays,
  formatNumber,
  generateMemo,
} from './calculations'
import type {
  ConfidenceLevel,
  CriticalityLevel,
  FieldDefinition,
  FieldValue,
  FrameworkSection,
  Requirement,
  Supplier,
  Weights,
} from './types'

const chartColors = ['#0f766e', '#2563eb', '#f59e0b', '#dc2626', '#7c3aed']

const navigation = [
  { id: 'intake', label: 'Product Intake', icon: ClipboardList },
  { id: 'suppliers', label: 'Supplier Discovery', icon: Search },
  { id: 'framework', label: 'Framework Table', icon: TableProperties },
  { id: 'scoring', label: 'Scoring Model', icon: Settings2 },
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { id: 'insights', label: 'AI Insights', icon: Brain },
  { id: 'memo', label: 'Recommendation', icon: FileText },
]

type SupplierDraft = Omit<Supplier, 'id' | 'values'>

const blankSupplierDraft: SupplierDraft = {
  name: '',
  country: '',
  region: '',
  website: '',
  productMatch: '',
  certifications: '',
  annualCapacity: 0,
  customerNotes: '',
  confidenceLevel: 'Needs Manual Review',
}

function useStoredState<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    const stored = window.localStorage.getItem(key)

    if (!stored) {
      return initialValue
    }

    try {
      return JSON.parse(stored) as T
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value))
  }, [key, value])

  return [value, setValue] as const
}

const createDefaultValues = () =>
  frameworkSections.reduce<Record<string, FieldValue>>((values, section) => {
    section.fields.forEach((field) => {
      if (field.kind === 'text') {
        values[field.key] = ''
      } else if (field.kind === 'score' || field.kind === 'risk') {
        values[field.key] = 3
      } else {
        values[field.key] = 0
      }
    })

    return values
  }, {})

const shortName = (name: string) =>
  name
    .split(' ')
    .filter((word) => word.length > 2)
    .slice(0, 2)
    .join(' ')

const confidenceClasses: Record<ConfidenceLevel, string> = {
  Verified: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  Estimated: 'bg-sky-50 text-sky-700 ring-sky-200',
  'AI Suggested': 'bg-violet-50 text-violet-700 ring-violet-200',
  'Needs Manual Review': 'bg-amber-50 text-amber-700 ring-amber-200',
  'Unavailable Online': 'bg-slate-100 text-slate-600 ring-slate-200',
}

const riskTone = (value: number) => {
  if (value <= 2) {
    return 'bg-emerald-100 text-emerald-800'
  }

  if (value <= 3.2) {
    return 'bg-amber-100 text-amber-800'
  }

  return 'bg-red-100 text-red-800'
}

const scoreTone = (score: number) => {
  if (score >= 80) {
    return 'text-emerald-700 bg-emerald-50 ring-emerald-200'
  }

  if (score >= 65) {
    return 'text-amber-700 bg-amber-50 ring-amber-200'
  }

  return 'text-red-700 bg-red-50 ring-red-200'
}

const fieldInputType = (field: FieldDefinition) => (field.kind === 'text' ? 'text' : 'number')

const fieldStep = (field: FieldDefinition) =>
  field.kind === 'currency' ? '0.01' : field.kind === 'score' || field.kind === 'risk' ? '1' : '1'

const formatFieldValue = (value: FieldValue | undefined) =>
  typeof value === 'number' ? String(value) : value ?? ''

function SectionShell({
  id,
  title,
  subtitle,
  icon: Icon,
  children,
}: {
  id: string
  title: string
  subtitle: string
  icon: typeof ClipboardList
  children: React.ReactNode
}) {
  return (
    <section
      id={id}
      className="min-w-0 scroll-mt-5 rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-900 text-white">
            <Icon size={20} strokeWidth={2} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
            <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
          </div>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function TextInput({
  label,
  value,
  onChange,
  type = 'text',
  textarea = false,
}: {
  label: string
  value: string | number
  onChange: (value: string) => void
  type?: 'text' | 'number' | 'url'
  textarea?: boolean
}) {
  const baseClass =
    'mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100'

  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      {textarea ? (
        <textarea
          className={`${baseClass} min-h-24 resize-y`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <input
          className={baseClass}
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  )
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
      <p className="mt-1 text-sm text-slate-500">{detail}</p>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
      {message}
    </div>
  )
}

function App() {
  const [requirement, setRequirement] = useStoredState<Requirement>(
    'gsc-requirement',
    sampleRequirement,
  )
  const [suppliers, setSuppliers] = useStoredState<Supplier[]>('gsc-suppliers', sampleSuppliers)
  const [weights, setWeights] = useStoredState<Weights>('gsc-weights', defaultWeights)
  const [selectedFramework, setSelectedFramework] =
    useState<FrameworkSection['id']>('cost')
  const [supplierDraft, setSupplierDraft] = useState<SupplierDraft>(blankSupplierDraft)

  const metrics = useMemo(
    () => calculateMetrics(suppliers, weights, requirement.quantity || 0),
    [requirement.quantity, suppliers, weights],
  )
  const recommendation = useMemo(() => buildRecommendationSummary(metrics), [metrics])
  const review = useMemo(() => analyzeRequirement(requirement), [requirement])
  const insights = useMemo(
    () => buildInsights(requirement, suppliers, metrics),
    [metrics, requirement, suppliers],
  )
  const memo = useMemo(
    () => generateMemo(requirement, suppliers, metrics),
    [metrics, requirement, suppliers],
  )
  const activeFramework = frameworkSections.find((section) => section.id === selectedFramework)!
  const weightTotal = Object.values(weights).reduce((total, weight) => total + weight, 0)

  const costChartData = metrics.map((metric) => ({
    name: shortName(metric.supplierName),
    landed: Number(metric.totalLandedCost.toFixed(2)),
    tco: Number(metric.totalCostOfOwnership.toFixed(2)),
  }))

  const leadTimeData = metrics.map((metric) => ({
    name: shortName(metric.supplierName),
    days: metric.totalLeadTime,
  }))

  const radarData = [
    ['Cost', 'cost'],
    ['Lead Time', 'leadTime'],
    ['Capability', 'capability'],
    ['Quality', 'quality'],
    ['Geopolitical', 'geopolitical'],
    ['Logistics', 'logistics'],
    ['Contract', 'contract'],
  ].map(([dimension, key]) => ({
    dimension,
    ...metrics.reduce<Record<string, number>>((row, metric) => {
      row[shortName(metric.supplierName)] =
        metric.dimensionScores[key as keyof typeof metric.dimensionScores]
      return row
    }, {}),
  }))

  const updateRequirement = <K extends keyof Requirement>(
    key: K,
    value: Requirement[K],
  ) => {
    setRequirement((current) => ({ ...current, [key]: value }))
  }

  const updateSupplier = <K extends keyof Supplier>(id: string, key: K, value: Supplier[K]) => {
    setSuppliers((current) =>
      current.map((supplier) => (supplier.id === id ? { ...supplier, [key]: value } : supplier)),
    )
  }

  const updateSupplierValue = (
    supplierId: string,
    field: FieldDefinition,
    nextValue: string,
  ) => {
    setSuppliers((current) =>
      current.map((supplier) => {
        if (supplier.id !== supplierId) {
          return supplier
        }

        const normalized =
          field.kind === 'text'
            ? nextValue
            : Number.isFinite(Number(nextValue))
              ? Number(nextValue)
              : 0

        return {
          ...supplier,
          values: {
            ...supplier.values,
            [field.key]: normalized,
          },
        }
      }),
    )
  }

  const updateWeight = (key: keyof Weights, nextValue: string) => {
    const numericValue = Number(nextValue)
    setWeights((current) => ({
      ...current,
      [key]: Number.isFinite(numericValue) ? numericValue : 0,
    }))
  }

  const addSupplier = () => {
    if (!supplierDraft.name.trim()) {
      return
    }

    setSuppliers((current) => [
      ...current,
      {
        ...supplierDraft,
        id: `supplier-${Date.now()}`,
        values: createDefaultValues(),
      },
    ])
    setSupplierDraft(blankSupplierDraft)
  }

  const addSuggestedSupplier = () => {
    const category = requirement.productCategory || 'target product'
    const template = sampleSuppliers[suppliers.length % sampleSuppliers.length]

    setSuppliers((current) => [
      ...current,
      {
        ...template,
        id: `ai-suggested-${Date.now()}`,
        name: `${category} Sample Supplier ${current.length + 1}`,
        country: 'Manual verification needed',
        region: 'AI suggested region',
        website: 'Unavailable online',
        productMatch: `Sample match for ${category}. Verify capability before outreach.`,
        certifications: 'Unavailable Online',
        annualCapacity: Math.max(50000, Number(requirement.forecastedDemand) || 50000),
        customerNotes:
          'AI suggested placeholder generated from product category. Treat as sample data only.',
        confidenceLevel: 'AI Suggested',
        values: {
          ...template.values,
          unitCost: Number(requirement.targetCost || 8.5),
          certificationRisk: 4,
          auditResultRisk: 4,
          documentationAbility: 2,
          contractPaymentTerms: 'Unknown; request in RFQ',
        },
      },
    ])
  }

  const removeSupplier = (supplierId: string) => {
    setSuppliers((current) => current.filter((supplier) => supplier.id !== supplierId))
  }

  return (
    <div className="min-h-screen overflow-x-clip bg-slate-100 text-slate-900">
        <aside className="border-b border-slate-200 bg-slate-950 text-white lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:h-screen lg:w-72 lg:border-b-0 lg:border-r lg:border-slate-800">
          <div className="flex h-full flex-col p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-teal-400 text-slate-950">
                <Globe2 size={23} strokeWidth={2.2} />
              </span>
              <div>
                <p className="text-base font-semibold">Global Sourcing Copilot</p>
                <p className="text-xs text-slate-400">AI-assisted sourcing workspace</p>
              </div>
            </div>

            <nav className="mt-5 flex gap-2 overflow-x-auto pb-1 lg:mt-8 lg:grid lg:gap-1 lg:overflow-visible lg:pb-0">
              {navigation.map((item) => {
                const Icon = item.icon

                return (
                  <a
                    key={item.id}
                    className="flex shrink-0 items-center gap-2 rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-slate-800 hover:text-white lg:gap-3 lg:border-0 lg:bg-transparent lg:py-2.5 lg:text-sm lg:hover:bg-slate-900"
                    href={`#${item.id}`}
                  >
                    <Icon size={18} />
                    {item.label}
                  </a>
                )
              })}
            </nav>

            <div className="mt-8 hidden rounded-lg border border-slate-800 bg-slate-900 p-4 lg:block">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Human review guardrail
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Supplier records can be verified, estimated, AI suggested, manually reviewed, or
                unavailable online. The recommendation never assumes perfect data.
              </p>
            </div>

            <div className="mt-auto hidden pt-8 text-xs text-slate-500 lg:block">
              Local MVP using browser storage. No backend or live AI API connected.
            </div>
          </div>
        </aside>

        <main className="min-w-0 lg:ml-72">
          <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-4 py-4 backdrop-blur sm:px-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <h1 className="text-2xl font-semibold text-slate-950">
                  Sourcing decision workspace
                </h1>
                <p className="mt-1 text-sm text-slate-500">
                  Define requirements, compare suppliers, calculate landed cost, score risk, and
                  generate a recommendation memo.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                  type="button"
                  title="Export supplier comparison CSV"
                  onClick={() => exportComparisonCsv(suppliers, metrics)}
                >
                  <Download size={16} />
                  CSV
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-teal-300 hover:text-teal-700"
                  type="button"
                  title="Export recommendation memo"
                  onClick={() => exportMemoText(memo)}
                >
                  <Save size={16} />
                  Memo
                </button>
              </div>
            </div>
          </header>

          <div className="grid gap-4 px-4 py-5 sm:grid-cols-2 sm:px-6 2xl:grid-cols-4">
            <MetricCard
              label="Best overall"
              value={recommendation.bestOverall?.supplierName ?? 'No supplier'}
              detail={`${recommendation.bestOverall?.finalScore ?? 0}/100 score`}
            />
            <MetricCard
              label="Lowest landed cost"
              value={
                recommendation.lowestCost
                  ? formatCurrency(recommendation.lowestCost.totalLandedCost)
                  : 'n/a'
              }
              detail={recommendation.lowestCost?.supplierName ?? 'Add suppliers'}
            />
            <MetricCard
              label="Fastest lead time"
              value={
                recommendation.fastestLeadTime
                  ? formatDays(recommendation.fastestLeadTime.totalLeadTime)
                  : 'n/a'
              }
              detail={recommendation.fastestLeadTime?.supplierName ?? 'Add suppliers'}
            />
            <MetricCard
              label="Active suppliers"
              value={String(suppliers.length)}
              detail={`${review.riskTier} requirement profile`}
            />
          </div>

          <div className="grid gap-5 px-4 pb-8 sm:px-6">
            <SectionShell
              id="intake"
              title="Product Requirement Intake"
              subtitle="Capture the product, quality, compliance, demand, and delivery constraints that drive sourcing decisions."
              icon={ClipboardList}
            >
              <div className="grid gap-5 2xl:grid-cols-[1.2fr_0.8fr]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextInput
                    label="Product name"
                    value={requirement.productName}
                    onChange={(value) => updateRequirement('productName', value)}
                  />
                  <TextInput
                    label="Product category"
                    value={requirement.productCategory}
                    onChange={(value) => updateRequirement('productCategory', value)}
                  />
                  <TextInput
                    label="Quantity"
                    type="number"
                    value={requirement.quantity}
                    onChange={(value) => updateRequirement('quantity', Number(value))}
                  />
                  <TextInput
                    label="Target cost"
                    type="number"
                    value={requirement.targetCost}
                    onChange={(value) => updateRequirement('targetCost', Number(value))}
                  />
                  <TextInput
                    label="Required lead time"
                    type="number"
                    value={requirement.requiredLeadTime}
                    onChange={(value) => updateRequirement('requiredLeadTime', Number(value))}
                  />
                  <TextInput
                    label="Forecasted demand"
                    type="number"
                    value={requirement.forecastedDemand}
                    onChange={(value) => updateRequirement('forecastedDemand', Number(value))}
                  />
                  <label className="block text-sm font-medium text-slate-700">
                    Criticality level
                    <select
                      className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                      value={requirement.criticality}
                      onChange={(event) =>
                        updateRequirement('criticality', event.target.value as CriticalityLevel)
                      }
                    >
                      {criticalityLevels.map((level) => (
                        <option key={level}>{level}</option>
                      ))}
                    </select>
                  </label>
                  <TextInput
                    label="Delivery location"
                    value={requirement.deliveryLocation}
                    onChange={(value) => updateRequirement('deliveryLocation', value)}
                  />
                  <div className="sm:col-span-2">
                    <TextInput
                      label="Product specs"
                      textarea
                      value={requirement.productSpecs}
                      onChange={(value) => updateRequirement('productSpecs', value)}
                    />
                  </div>
                  <TextInput
                    label="Quality requirements"
                    textarea
                    value={requirement.qualityRequirements}
                    onChange={(value) => updateRequirement('qualityRequirements', value)}
                  />
                  <TextInput
                    label="Compliance requirements"
                    textarea
                    value={requirement.complianceRequirements}
                    onChange={(value) => updateRequirement('complianceRequirements', value)}
                  />
                  <TextInput
                    label="Approved materials"
                    textarea
                    value={requirement.approvedMaterials}
                    onChange={(value) => updateRequirement('approvedMaterials', value)}
                  />
                  <TextInput
                    label="Technical drawings link or notes"
                    textarea
                    value={requirement.technicalDrawings}
                    onChange={(value) => updateRequirement('technicalDrawings', value)}
                  />
                  <div className="sm:col-span-2">
                    <TextInput
                      label="Packaging requirements"
                      textarea
                      value={requirement.packagingRequirements}
                      onChange={(value) => updateRequirement('packagingRequirements', value)}
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-teal-100 bg-teal-50 p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-700 text-white">
                      <Brain size={18} />
                    </span>
                    <div>
                      <h3 className="text-base font-semibold text-slate-950">
                        AI Requirement Review
                      </h3>
                      <p className="mt-1 text-sm text-teal-800">
                        Rule-based placeholder analysis. Validate all assumptions with suppliers.
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4">
                    <ReviewBlock
                      title="Missing information"
                      items={review.missing}
                      fallback="No major missing fields detected."
                    />
                    <ReviewBlock
                      title="Potential sourcing risks"
                      items={review.risks}
                      fallback="No material risks detected from the current intake."
                    />
                    <ReviewBlock
                      title="Questions to ask suppliers"
                      items={review.questions}
                      fallback="Add product details to generate supplier questions."
                    />
                    <div className="rounded-md bg-white p-3 ring-1 ring-teal-100">
                      <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
                        Suggested sourcing strategy
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{review.strategy}</p>
                    </div>
                    <div className="flex items-center justify-between rounded-md bg-white p-3 ring-1 ring-teal-100">
                      <span className="text-sm font-semibold text-slate-700">Part risk rating</span>
                      <span className={`rounded-full px-3 py-1 text-sm font-semibold ${riskTone(review.risks.length + (requirement.criticality === 'Critical' ? 2 : 0))}`}>
                        {review.riskTier}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </SectionShell>

            <SectionShell
              id="suppliers"
              title="Supplier Discovery"
              subtitle="Add real suppliers manually or create clearly labeled sample suggestions for category exploration."
              icon={Factory}
            >
              <div className="grid gap-5 2xl:grid-cols-[1fr_360px]">
                <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {suppliers.map((supplier) => (
                    <article
                      key={supplier.id}
                      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-base font-semibold text-slate-950">
                            {supplier.name}
                          </h3>
                          <p className="mt-1 text-sm text-slate-500">
                            {supplier.country} · {supplier.region}
                          </p>
                        </div>
                        <span
                          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${confidenceClasses[supplier.confidenceLevel]}`}
                        >
                          {supplier.confidenceLevel}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">
                        {supplier.productMatch}
                      </p>
                      <dl className="mt-4 grid gap-3 text-sm">
                        <div>
                          <dt className="font-medium text-slate-500">Certifications</dt>
                          <dd className="mt-1 text-slate-800">{supplier.certifications}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-slate-500">Estimated annual capacity</dt>
                          <dd className="mt-1 text-slate-800">
                            {formatNumber(supplier.annualCapacity)} units
                          </dd>
                        </div>
                        <div>
                          <dt className="font-medium text-slate-500">Current customer notes</dt>
                          <dd className="mt-1 text-slate-800">{supplier.customerNotes}</dd>
                        </div>
                      </dl>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <a
                          className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-teal-300 hover:text-teal-700"
                          href={supplier.website}
                          target="_blank"
                        >
                          <Globe2 size={15} />
                          Website
                        </a>
                        <button
                          className="inline-flex items-center gap-2 rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-50"
                          type="button"
                          onClick={() => removeSupplier(supplier.id)}
                        >
                          Remove
                        </button>
                      </div>
                    </article>
                  ))}
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <h3 className="text-base font-semibold text-slate-950">Add supplier</h3>
                  <div className="mt-4 grid gap-3">
                    <TextInput
                      label="Supplier name"
                      value={supplierDraft.name}
                      onChange={(value) => setSupplierDraft((draft) => ({ ...draft, name: value }))}
                    />
                    <TextInput
                      label="Country"
                      value={supplierDraft.country}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({ ...draft, country: value }))
                      }
                    />
                    <TextInput
                      label="Region"
                      value={supplierDraft.region}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({ ...draft, region: value }))
                      }
                    />
                    <TextInput
                      label="Website"
                      type="url"
                      value={supplierDraft.website}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({ ...draft, website: value }))
                      }
                    />
                    <TextInput
                      label="Product match"
                      value={supplierDraft.productMatch}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({ ...draft, productMatch: value }))
                      }
                    />
                    <TextInput
                      label="Certifications"
                      value={supplierDraft.certifications}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({ ...draft, certifications: value }))
                      }
                    />
                    <TextInput
                      label="Estimated annual capacity"
                      type="number"
                      value={supplierDraft.annualCapacity}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({
                          ...draft,
                          annualCapacity: Number(value),
                        }))
                      }
                    />
                    <label className="block text-sm font-medium text-slate-700">
                      Confidence level
                      <select
                        className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                        value={supplierDraft.confidenceLevel}
                        onChange={(event) =>
                          setSupplierDraft((draft) => ({
                            ...draft,
                            confidenceLevel: event.target.value as ConfidenceLevel,
                          }))
                        }
                      >
                        {confidenceLevels.map((level) => (
                          <option key={level}>{level}</option>
                        ))}
                      </select>
                    </label>
                    <TextInput
                      label="Current customer notes"
                      textarea
                      value={supplierDraft.customerNotes}
                      onChange={(value) =>
                        setSupplierDraft((draft) => ({ ...draft, customerNotes: value }))
                      }
                    />
                    <button
                      className="inline-flex items-center justify-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                      type="button"
                      onClick={addSupplier}
                    >
                      <Plus size={16} />
                      Add supplier
                    </button>
                    <button
                      className="inline-flex items-center justify-center gap-2 rounded-md border border-violet-200 bg-white px-3 py-2 text-sm font-semibold text-violet-700 transition hover:bg-violet-50"
                      type="button"
                      onClick={addSuggestedSupplier}
                    >
                      <Sparkles size={16} />
                      AI Suggested Supplier
                    </button>
                    <p className="text-xs leading-5 text-slate-500">
                      Sample suggestions are placeholders based on product category and require
                      manual verification before supplier outreach.
                    </p>
                  </div>
                </div>
              </div>
            </SectionShell>

            <SectionShell
              id="framework"
              title="Global Sourcing Framework Table"
              subtitle="Edit supplier assumptions by category. Scores use 1-5 scales; risk scores treat 1 as low risk and 5 as high risk."
              icon={TableProperties}
            >
              <div className="flex flex-wrap gap-2">
                {frameworkSections.map((section) => (
                  <button
                    key={section.id}
                    className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
                      selectedFramework === section.id
                        ? 'bg-slate-900 text-white'
                        : 'border border-slate-200 bg-white text-slate-700 hover:border-teal-300 hover:text-teal-700'
                    }`}
                    type="button"
                    onClick={() => setSelectedFramework(section.id)}
                  >
                    {section.label}
                  </button>
                ))}
              </div>

              <p className="mt-4 text-sm text-slate-500">{activeFramework.description}</p>

              <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-[980px] w-full border-collapse bg-white text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="sticky left-0 z-10 w-64 border-b border-slate-200 bg-slate-50 px-3 py-3">
                        Supplier
                      </th>
                      {activeFramework.fields.map((field) => (
                        <th
                          key={field.key}
                          className="min-w-40 border-b border-slate-200 px-3 py-3"
                        >
                          {field.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {suppliers.map((supplier) => (
                      <tr key={supplier.id} className="border-b border-slate-100 last:border-b-0">
                        <th className="sticky left-0 z-10 bg-white px-3 py-3 font-semibold text-slate-900">
                          <input
                            className="w-full rounded-md border border-transparent bg-transparent px-2 py-1 text-sm font-semibold outline-none transition focus:border-teal-400 focus:bg-white focus:ring-2 focus:ring-teal-100"
                            value={supplier.name}
                            onChange={(event) =>
                              updateSupplier(supplier.id, 'name', event.target.value)
                            }
                          />
                          <select
                            className="mt-2 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium text-slate-600 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100"
                            value={supplier.confidenceLevel}
                            onChange={(event) =>
                              updateSupplier(
                                supplier.id,
                                'confidenceLevel',
                                event.target.value as ConfidenceLevel,
                              )
                            }
                          >
                            {confidenceLevels.map((level) => (
                              <option key={level}>{level}</option>
                            ))}
                          </select>
                        </th>
                        {activeFramework.fields.map((field) => (
                          <td key={field.key} className="px-3 py-3 align-top">
                            <input
                              className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-2 text-sm text-slate-800 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                              min={field.kind === 'score' || field.kind === 'risk' ? 1 : undefined}
                              max={field.kind === 'score' || field.kind === 'risk' ? 5 : undefined}
                              step={fieldStep(field)}
                              type={fieldInputType(field)}
                              value={formatFieldValue(supplier.values[field.key])}
                              onChange={(event) =>
                                updateSupplierValue(supplier.id, field, event.target.value)
                              }
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionShell>

            <SectionShell
              id="scoring"
              title="Cost, Lead Time, and Supplier Scoring"
              subtitle="Default weights match the sourcing framework and can be edited for scenario analysis."
              icon={Settings2}
            >
              <div className="grid gap-5 2xl:grid-cols-[340px_1fr]">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-base font-semibold text-slate-950">Weights</h3>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        weightTotal === 100
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      Total {weightTotal}%
                    </span>
                  </div>
                  <div className="mt-4 grid gap-3">
                    {Object.entries(weights).map(([key, value]) => (
                      <label
                        key={key}
                        className="grid grid-cols-[1fr_76px] items-center gap-3 text-sm font-medium text-slate-700"
                      >
                        <span>{weightLabel(key as keyof Weights)}</span>
                        <input
                          className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-right text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                          type="number"
                          value={value}
                          onChange={(event) => updateWeight(key as keyof Weights, event.target.value)}
                        />
                      </label>
                    ))}
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="min-w-[920px] w-full border-collapse bg-white text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-3 text-left">Supplier</th>
                        <th className="px-3 py-3 text-right">Landed / unit</th>
                        <th className="px-3 py-3 text-right">TCO / unit</th>
                        <th className="px-3 py-3 text-right">Order landed</th>
                        <th className="px-3 py-3 text-right">Order TCO</th>
                        <th className="px-3 py-3 text-right">Lead time</th>
                        <th className="px-3 py-3 text-right">Final score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.map((metric) => (
                        <tr key={metric.supplierId} className="border-b border-slate-100 last:border-0">
                          <td className="px-3 py-3 font-semibold text-slate-950">
                            {metric.supplierName}
                          </td>
                          <td className="px-3 py-3 text-right">
                            {formatCurrency(metric.totalLandedCost)}
                          </td>
                          <td className="px-3 py-3 text-right">
                            {formatCurrency(metric.totalCostOfOwnership)}
                          </td>
                          <td className="px-3 py-3 text-right">
                            {formatCurrency(metric.totalOrderCost)}
                          </td>
                          <td className="px-3 py-3 text-right">
                            {formatCurrency(metric.totalOrderTco)}
                          </td>
                          <td className="px-3 py-3 text-right">{formatDays(metric.totalLeadTime)}</td>
                          <td className="px-3 py-3 text-right">
                            <span
                              className={`inline-flex min-w-16 justify-center rounded-full px-2.5 py-1 text-sm font-semibold ring-1 ${scoreTone(metric.finalScore)}`}
                            >
                              {metric.finalScore}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </SectionShell>

            <SectionShell
              id="dashboard"
              title="Dashboard"
              subtitle="Scorecards, cost comparisons, lead time view, heatmap, radar analysis, and sourcing recommendation."
              icon={BarChart3}
            >
              {metrics.length === 0 ? (
                <EmptyState message="Add suppliers to populate the dashboard." />
              ) : (
                <div className="grid gap-5">
                    <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
                    <RecommendationTile
                      icon={CheckCircle2}
                      title="Best overall supplier"
                      value={recommendation.bestOverall?.supplierName ?? 'n/a'}
                      detail={`${recommendation.bestOverall?.finalScore ?? 0}/100 weighted score`}
                    />
                    <RecommendationTile
                      icon={PackageCheck}
                      title="Lowest cost supplier"
                      value={recommendation.lowestCost?.supplierName ?? 'n/a'}
                      detail={
                        recommendation.lowestCost
                          ? `${formatCurrency(recommendation.lowestCost.totalLandedCost)} landed`
                          : 'n/a'
                      }
                    />
                    <RecommendationTile
                      icon={Truck}
                      title="Fastest lead time"
                      value={recommendation.fastestLeadTime?.supplierName ?? 'n/a'}
                      detail={
                        recommendation.fastestLeadTime
                          ? formatDays(recommendation.fastestLeadTime.totalLeadTime)
                          : 'n/a'
                      }
                    />
                    <RecommendationTile
                      icon={ShieldAlert}
                      title="Highest risk supplier"
                      value={recommendation.highestRisk?.supplierName ?? 'n/a'}
                      detail="Manual risk review required"
                    />
                  </div>

                  <div className="grid gap-5 2xl:grid-cols-2">
                    <ChartPanel title="Total landed cost vs TCO">
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={costChartData} margin={{ top: 8, right: 18, left: 8, bottom: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="name" tickLine={false} axisLine={false} />
                          <YAxis tickLine={false} axisLine={false} />
                          <RechartsTooltip formatter={(value) => formatCurrency(Number(value))} />
                          <Legend />
                          <Bar dataKey="landed" name="Landed cost" radius={[5, 5, 0, 0]} fill="#0f766e" />
                          <Bar dataKey="tco" name="TCO" radius={[5, 5, 0, 0]} fill="#2563eb" />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartPanel>

                    <ChartPanel title="Lead time comparison">
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={leadTimeData} margin={{ top: 8, right: 18, left: 8, bottom: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="name" tickLine={false} axisLine={false} />
                          <YAxis tickLine={false} axisLine={false} />
                          <RechartsTooltip formatter={(value) => `${value} days`} />
                          <Bar dataKey="days" name="Lead time">
                            {leadTimeData.map((entry, index) => (
                              <Cell
                                key={entry.name}
                                fill={entry.days <= requirement.requiredLeadTime ? chartColors[index % chartColors.length] : '#dc2626'}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartPanel>
                  </div>

                  <div className="grid gap-5 2xl:grid-cols-[0.9fr_1.1fr]">
                    <div className="rounded-lg border border-slate-200 bg-white p-4">
                      <h3 className="text-base font-semibold text-slate-950">Risk heatmap</h3>
                      <div className="mt-4 overflow-x-auto">
                        <table className="min-w-[640px] w-full border-collapse text-sm">
                          <thead className="text-xs uppercase tracking-wide text-slate-500">
                            <tr>
                              <th className="px-2 py-2 text-left">Supplier</th>
                              <th className="px-2 py-2 text-center">Quality</th>
                              <th className="px-2 py-2 text-center">Geopolitical</th>
                              <th className="px-2 py-2 text-center">Logistics</th>
                            </tr>
                          </thead>
                          <tbody>
                            {metrics.map((metric) => (
                              <tr key={metric.supplierId} className="border-t border-slate-100">
                                <td className="px-2 py-3 font-medium text-slate-900">
                                  {metric.supplierName}
                                </td>
                                <HeatmapCell value={metric.qualityRiskAverage} />
                                <HeatmapCell value={metric.geopoliticalRiskAverage} />
                                <HeatmapCell value={metric.logisticsRiskAverage} />
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <ChartPanel title="Radar comparison">
                      <ResponsiveContainer width="100%" height={340}>
                        <RadarChart data={radarData}>
                          <PolarGrid stroke="#cbd5e1" />
                          <PolarAngleAxis dataKey="dimension" tick={{ fill: '#475569', fontSize: 12 }} />
                          <RechartsTooltip />
                          {metrics.map((metric, index) => (
                            <Radar
                              key={metric.supplierId}
                              dataKey={shortName(metric.supplierName)}
                              stroke={chartColors[index % chartColors.length]}
                              fill={chartColors[index % chartColors.length]}
                              fillOpacity={0.12}
                            />
                          ))}
                          <Legend />
                        </RadarChart>
                      </ResponsiveContainer>
                    </ChartPanel>
                  </div>
                </div>
              )}
            </SectionShell>

            <SectionShell
              id="insights"
              title="AI Insight Panels"
              subtitle="Rule-based sourcing observations. These explain what to validate, not what to blindly trust."
              icon={Brain}
            >
              <div className="grid gap-3 md:grid-cols-2">
                {insights.map((insight) => (
                  <div
                    key={insight}
                    className="flex gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                    <p className="text-sm leading-6 text-slate-700">{insight}</p>
                  </div>
                ))}
              </div>
            </SectionShell>

            <SectionShell
              id="memo"
              title="Final Sourcing Recommendation"
              subtitle="Generate a structured memo from the current requirement, supplier data, scoring model, and manual review flags."
              icon={FileText}
            >
              <div className="grid gap-5 2xl:grid-cols-[1fr_360px]">
                <pre className="max-h-[620px] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-950 p-5 text-sm leading-7 text-slate-100">
                  {memo}
                </pre>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <h3 className="text-base font-semibold text-slate-950">Export</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    Export the editable supplier comparison as CSV or the recommendation memo as a
                    text file.
                  </p>
                  <div className="mt-4 grid gap-3">
                    <button
                      className="inline-flex items-center justify-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                      type="button"
                      onClick={() => exportComparisonCsv(suppliers, metrics)}
                    >
                      <Download size={16} />
                      Supplier comparison CSV
                    </button>
                    <button
                      className="inline-flex items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-teal-300 hover:text-teal-700"
                      type="button"
                      onClick={() => exportMemoText(memo)}
                    >
                      <FileText size={16} />
                      Recommendation text file
                    </button>
                  </div>
                </div>
              </div>
            </SectionShell>
          </div>
        </main>
    </div>
  )
}

function ReviewBlock({
  title,
  items,
  fallback,
}: {
  title: string
  items: string[]
  fallback: string
}) {
  return (
    <div className="rounded-md bg-white p-3 ring-1 ring-teal-100">
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">{title}</p>
      <ul className="mt-2 grid gap-2 text-sm leading-5 text-slate-700">
        {(items.length ? items : [fallback]).map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RecommendationTile({
  icon: Icon,
  title,
  value,
  detail,
}: {
  icon: typeof CheckCircle2
  title: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-white text-teal-700 ring-1 ring-slate-200">
          <Icon size={18} />
        </span>
        <p className="text-sm font-semibold text-slate-600">{title}</p>
      </div>
      <p className="mt-4 text-lg font-semibold text-slate-950">{value}</p>
      <p className="mt-1 text-sm text-slate-500">{detail}</p>
    </div>
  )
}

function ChartPanel({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-base font-semibold text-slate-950">{title}</h3>
      <div className="mt-4">{children}</div>
    </div>
  )
}

function HeatmapCell({ value }: { value: number }) {
  return (
    <td className="px-2 py-3 text-center">
      <span className={`inline-flex min-w-12 justify-center rounded-md px-2.5 py-1 text-sm font-semibold ${riskTone(value)}`}>
        {formatNumber(value)}
      </span>
    </td>
  )
}

function weightLabel(key: keyof Weights) {
  const labels: Record<keyof Weights, string> = {
    landedCost: 'Total Landed Cost',
    tco: 'Total Cost of Ownership',
    leadTime: 'Lead Time',
    capability: 'Supplier Capability',
    qualityRisk: 'Quality Risk',
    geopoliticalRisk: 'Geopolitical Risk',
    logistics: 'Logistics Complexity',
    contract: 'Contract Terms',
  }

  return labels[key]
}

export default App
