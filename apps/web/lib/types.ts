/**
 * Response types for the mining governance API.
 *
 * IMPORTANT: the API serialises `Decimal` as a JSON *string* (e.g. "158.6000")
 * to avoid float precision loss on money and area. Those fields are typed
 * `string` here on purpose - use `toNumber()` from lib/format before doing
 * arithmetic on them.
 */

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type LeaseType =
  | "prospecting_licence"
  | "mining_lease"
  | "quarry_lease"
  | "composite_licence";

export type LeaseStatus =
  | "pending"
  | "active"
  | "pending_renewal"
  | "suspended"
  | "expired"
  | "surrendered"
  | "revoked";

  export type AppRole = "admin" | "inspector" | "operator";

export type LicenceStatus =
  | "pending"
  | "valid"
  | "expiring_soon"
  | "expired"
  | "revoked";

export type LicenceType =
  | "environmental_clearance"
  | "forest_clearance"
  | "consent_to_operate"
  | "mining_plan_approval"
  | "ground_water_ntoc"
  | "explosive_licence"
  | "drone_survey_approval"
  | "lease_deed";

export type ObligationStatus =
  | "pending"
  | "in_progress"
  | "submitted"
  | "overdue"
  | "waived"
  | "not_applicable";

export type ObligationCategory =
  | "return_filing"
  | "payment"
  | "inspection"
  | "safety"
  | "environment"
  | "social"
  | "reporting";

export type MineralCategory = "major" | "minor";

export type RoyaltyBasis = "ad_valorem" | "specific" | "exempt";

export type HolderEntityType =
  | "company"
  | "individual"
  | "cooperative"
  | "joint_venture"
  | "government_undertaking";

export interface LatLon {
  lat: number;
  lon: number;
}

export type GeoJSONGeometry =
  | { type: "Point"; coordinates: number[] }
  | { type: "Polygon"; coordinates: number[][][] }
  | { type: "MultiPolygon"; coordinates: number[][][][] };

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Mineral {
  id: string;
  code: string;
  name: string;
  category: MineralCategory;
  royalty_basis: RoyaltyBasis;
  royalty_rate: string;
  royalty_unit: string | null;
  description: string | null;
  is_active: boolean;
}

export interface Holder {
  id: string;
  name: string;
  entity_type: HolderEntityType;
  registration_number: string | null;
  tax_identifier: string | null;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  address_line: string | null;
  district: string | null;
  state: string | null;
  country: string;
  is_operator: boolean;
}

/** Slim projection returned by the lease list and map endpoints. */
export interface LeaseListItem {
  id: string;
  lease_number: string;
  name: string;
  lease_type: LeaseType;
  status: LeaseStatus;
  district: string;
  state: string;
  area_hectares: string | null;
  effective_from: string;
  effective_to: string | null;
  holder_name: string | null;
  mineral_name: string | null;
  centroid: LatLon | null;
  compliance_score: number | null;
  risk_level: RiskLevel | null;
  overdue_obligations: number;
  expiring_licences: number;
  expired_licences: number;
}

/**
 * A lease as a GeoJSON feature, from `GET /leases/geojson`.
 * Properties carry the compliance posture so the map colours itself in one pass.
 */
export interface LeaseFeature {
  type: "Feature";
  id: string;
  geometry: GeoJSONGeometry;
  properties: {
    id: string;
    lease_number: string;
    name: string;
    status: LeaseStatus;
    lease_type: LeaseType;
    district: string;
    state: string;
    area_hectares: number | null;
    effective_to: string | null;
    holder_name: string | null;
    mineral_name: string | null;
    compliance_score: number;
    risk_level: RiskLevel;
    overdue_obligations: number;
    expired_licences: number;
  };
}

export interface LeaseFeatureCollection {
  type: "FeatureCollection";
  features: LeaseFeature[];
}

/** Full lease record. */
export interface Lease extends Omit<LeaseListItem, "holder_name" | "mineral_name"> {
  holder_id: string;
  mineral_id: string;
  village: string | null;
  country: string;
  grant_date: string | null;
  royalty_basis: RoyaltyBasis | null;
  royalty_rate: string | null;
  royalty_unit: string | null;
  annual_production_tonnes: string | null;
  notes: string | null;
  boundary: GeoJSONGeometry | null;
  surveyed_area_hectares: number | null;
  holder: Holder | null;
  mineral: Mineral | null;
  created_at: string;
  updated_at: string;
}

export interface ComplianceComponent {
  name: string;
  weight: number;
  applicable: boolean;
  earned: number;
  ratio: number | null;
  detail: string;
}

export interface ComplianceScore {
  lease_id: string;
  lease_number: string;
  score: number;
  risk_level: RiskLevel;
  components: ComplianceComponent[];
  total_licences: number;
  valid_licences: number;
  expiring_licences: number;
  expired_licences: number;
  open_obligations: number;
  overdue_obligations: number;
  submitted_obligations: number;
  notes: string[];
}

export interface Licence {
  id: string;
  lease_id?: string;
  licence_type: LicenceType;
  status: LicenceStatus;
  authority: string;
  reference_number: string | null;
  issued_date: string | null;
  valid_from: string | null;
  valid_to: string | null;
  is_mandatory: boolean;
  is_expired: boolean;
  days_until_expiry: number | null;
  document_path: string | null;
  notes: string | null;
}

export type DocumentType = "licence" | "obligation" | "evidence" | "general";
export type DocumentStatus = "pending_review" | "accepted" | "needs_attention" | "rejected";

export interface LeaseDocument {
  id: string;
  lease_id: string;
  title: string;
  file_name: string;
  content_type: string;
  file_path: string;
  document_type: DocumentType;
  source: string;
  status: DocumentStatus;
  notes: string | null;
  extracted_summary: string | null;
  extracted_reference_number: string | null;
  extracted_authority: string | null;
  extracted_expiry_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReminderPreview {
  obligation_id: string;
  lease_id: string;
  site_name: string;
  site_number: string;
  title: string;
  due_date: string;
  days_until_due: number;
  kind: "overdue" | "upcoming";
  message: string;
}

export interface ReminderDelivery {
  id: string;
  obligation_id: string;
  recipient_email: string | null;
  provider: string;
  status: string;
  provider_message_id: string | null;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface CalendarEntry {
  id: string;
  lease_id: string;
  obligation_id: string;
  period_start: string | null;
  period_end: string | null;
  due_date: string;
  status: ObligationStatus;
  submitted_at: string | null;
  submitted_by: string | null;
  evidence_path: string | null;
  notes: string | null;
  waiver_reason: string | null;
  code: string | null;
  title: string | null;
  category: ObligationCategory | null;
  legal_reference: string | null;
  requires_payment: boolean | null;
  penalty_note: string | null;
  lease_number: string | null;
  lease_name: string | null;
  district: string | null;
  state: string | null;
  days_until_due: number | null;
}

export interface TimelineEntry {
  id: string;
  due_date: string;
  status: ObligationStatus;
  days_until_due: number;
  code: string | null;
  title: string | null;
  category: ObligationCategory | null;
  requires_payment: boolean | null;
  period_start: string | null;
  period_end: string | null;
}

export interface ObligationRule {
  id: string;
  code: string;
  title: string;
  description: string | null;
  category: ObligationCategory;
  legal_reference: string | null;
  jurisdiction: string | null;
  recurrence: string;
  due_days_after_period_end: number;
  grace_days: number;
  fiscal_year_end_month: number;
  applies_to_lease_types: LeaseType[];
  applies_to_mineral_categories: MineralCategory[];
  requires_payment: boolean;
  penalty_note: string | null;
  is_active: boolean;
}

export interface DashboardTotals {
  leases_total: number;
  leases_active: number;
  leases_expiring_within_90_days: number;
  total_area_hectares: string;
  obligations_overdue: number;
  obligations_due_within_30_days: number;
  licences_expired: number;
  licences_expiring_soon: number;
  average_compliance_score: number;
}

export interface DashboardSummary {
  as_of: string;
  totals: DashboardTotals;
  risk_buckets: { risk_level: RiskLevel; lease_count: number }[];
  by_state: { state: string; lease_count: number; area_hectares: string }[];
  overdue_by_category: {
    category: ObligationCategory;
    overdue: number;
    due_soon: number;
  }[];
}
