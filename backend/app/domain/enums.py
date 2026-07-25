from enum import StrEnum


class AssetType(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    CASH = "cash"
    OPTION = "option"
    MUTUAL_FUND = "mutual_fund"
    FIXED_INCOME = "fixed_income"
    UNKNOWN = "unknown"


class PositionChangeKind(StrEnum):
    OPENED = "opened"
    INCREASED = "increased"
    DECREASED = "decreased"
    CLOSED = "closed"
    UNCHANGED = "unchanged"


class RejectionReason(StrEnum):
    UNSUPPORTED_ASSET_TYPE = "unsupported_asset_type"
    MISSING_IDENTITY = "missing_identity"
    UNRESOLVED_SECURITY = "unresolved_security"
    NEGATIVE_QUANTITY = "negative_quantity"
    INVALID_TIMESTAMP = "invalid_timestamp"
    EMPTY_HEADLINE = "empty_headline"
    CONFLICTING_IDENTITY = "conflicting_identity"


class EventProvider(StrEnum):
    SEC = "sec"
    ALPACA = "alpaca"
    FINNHUB = "finnhub"
    OPENBB = "openbb"
    BENZINGA = "benzinga"
    FMP = "fmp"
    INTRINIO = "intrinio"
    YFINANCE = "yfinance"
    COMPANY = "company"
    DEMO = "demo"


class EventType(StrEnum):
    SEC_FILING = "sec_filing"
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    MERGER_ACQUISITION = "merger_acquisition"
    LEADERSHIP = "leadership"
    DIVIDEND = "dividend"
    BUYBACK = "buyback"
    REGULATORY_LEGAL = "regulatory_legal"
    CYBERSECURITY = "cybersecurity"
    PRODUCT_OPERATIONAL = "product_operational"
    ANALYST_ACTION = "analyst_action"
    INSIDER_ACTIVITY = "insider_activity"
    GENERAL_NEWS = "general_news"


class DedupeReason(StrEnum):
    ACCESSION_NUMBER = "accession_number"
    PROVIDER_EVENT_ID = "provider_event_id"
    CANONICAL_URL = "canonical_url"
    STRONG_FINGERPRINT = "strong_fingerprint"
    SEMANTIC_CANDIDATE = "semantic_candidate"


class ImpactLevel(StrEnum):
    URGENT = "urgent"
    IMPORTANT = "important"
    NOTABLE = "notable"
    INFORMATIONAL = "informational"


class ImpactReasonCode(StrEnum):
    MATERIAL_EVENT = "material_event"
    DIRECT_EXPOSURE = "direct_exposure"
    INDIRECT_EXPOSURE = "indirect_exposure"
    AUTHORITATIVE_SOURCE = "authoritative_source"
    LOW_MATCH_CONFIDENCE = "low_match_confidence"
    RECENT_EVENT = "recent_event"
    REPEATED_STORY = "repeated_story"
    NO_CURRENT_EXPOSURE = "no_current_exposure"


class SyncTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CONNECTION = "connection"


class SyncRunStatus(StrEnum):
    REQUESTED = "requested"
    LOCKED = "locked"
    BROKERAGE_FETCHED = "brokerage_fetched"
    PORTFOLIO_PERSISTED = "portfolio_persisted"
    EVENTS_FETCHED = "events_fetched"
    EVENTS_PERSISTED = "events_persisted"
    ASSESSMENTS_PERSISTED = "assessments_persisted"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
