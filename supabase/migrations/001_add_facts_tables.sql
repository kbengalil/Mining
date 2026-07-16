-- Add structured fact extraction tables for the 6 core document types.
-- Run in the Supabase SQL editor.

create table ni_43101_facts (
    id uuid primary key default gen_random_uuid(),
    company_name text not null,
    document_label text not null,
    extracted_at timestamptz not null default now(),
    study_type text,
    resource_tonnage text,
    resource_grade text,
    resource_classification text,
    npv text,
    npv_discount_rate text,
    irr text,
    capex_initial text,
    opex_per_tonne text,
    strip_ratio text,
    metallurgical_recovery text,
    mine_life_years text,
    qp_name text,
    report_date text,
    metal_price_assumption text,
    unique (company_name, document_label)
);

create table financial_facts (
    id uuid primary key default gen_random_uuid(),
    company_name text not null,
    document_label text not null,
    extracted_at timestamptz not null default now(),
    cash_and_equivalents text,
    total_debt text,
    working_capital text,
    shares_basic text,
    shares_diluted text,
    mineral_property_book_value text,
    going_concern boolean,
    auditor text,
    fiscal_year_end text,
    annual_revenue text,
    royalty_obligations text,
    streaming_agreements text,
    unique (company_name, document_label)
);

create table mda_facts (
    id uuid primary key default gen_random_uuid(),
    company_name text not null,
    document_label text not null,
    extracted_at timestamptz not null default now(),
    aisc text,
    cash_cost text,
    production_guidance text,
    quarterly_cash_burn text,
    cash_runway_months text,
    key_risks text,
    liquidity_outlook text,
    unique (company_name, document_label)
);

create table press_release_facts (
    id uuid primary key default gen_random_uuid(),
    company_name text not null,
    document_label text not null,
    extracted_at timestamptz not null default now(),
    drill_intercept_best text,
    grade_thickness_score numeric,
    financing_type text,
    financing_amount text,
    dilution_shares_issued text,
    permits_received text,
    management_changes text,
    ma_activity text,
    resource_update text,
    unique (company_name, document_label)
);

create table presentation_facts (
    id uuid primary key default gen_random_uuid(),
    company_name text not null,
    document_label text not null,
    extracted_at timestamptz not null default now(),
    primary_commodity text,
    development_stage text,
    upcoming_catalysts text,
    jurisdiction text,
    insider_ownership_pct text,
    market_cap text,
    enterprise_value text,
    unique (company_name, document_label)
);

create table proxy_facts (
    id uuid primary key default gen_random_uuid(),
    company_name text not null,
    document_label text not null,
    extracted_at timestamptz not null default now(),
    ceo_total_compensation text,
    ceo_base_salary text,
    ceo_shares_owned text,
    board_size integer,
    independent_directors_count integer,
    related_party_transactions boolean,
    say_on_pay_vote_pct text,
    total_insider_ownership_pct text,
    unique (company_name, document_label)
);
