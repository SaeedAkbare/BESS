# Bollingstedt — single-asset evidence ledger for the BESS model

**Research date:** 2026-11-06  
**Asset:** Bollingstedt / ECO POWER ONE, Schleswig-Holstein, Germany.  
**Policy:** All asset-specific parameter values must refer to **this exact physical facility**. Never combine MW from Bollingstedt, efficiency from some other battery, SOC constraints from a generic manufacturer's datasheet, and O&M from another project while describing the result as a real Bollingstedt model. A bidding-zone *market price series* is a shared market input, **not another battery's technical data**.

This is a sourced research inventory, **not a calibrated or executable digital twin**. No asset dispatch data has yet been downloaded or verified as a usable time series in this repository. No optimization or performance comparison has been run.

## Verified project-specific public figures (operator, current owner, market partner)

| Parameter | Value | Date / basis | Provenance | Use in optimization? |
|---|---|---|---|---|
| Plant | Bollingstedt large BESS (sometimes ECO POWER ONE) | operational since 2025 | ECO STOR (original developer/initial operator), current owner Alpiq | Yes, single reference asset |
| Rated power | **103.5 MW** | plant published rating | ECO STOR; Alpiq | Candidate Pmax, subject to interpretation of AC terminal versus PCC rating |
| Published energy capacity | **238 MWh** | plant published rating | ECO STOR; Alpiq | Nameplate *published* capacity; usable SOC-limited capacity not yet known |
| Battery cell technology | **LFP (lithium iron phosphate)** | project-specific partner data | Entelios, project trading partner | Chemistry for context; no inferred electrochemistry parameters |
| Physical makeup | 64 battery containers / 32 converters/transformer containers | 2025 commissioning materials | ECO STOR and project financing release | Context only |
| Grid connection voltage | **110 kV** | owner / partner project records | ECO STOR; Entelios | Context. **Does not prove** import/export grid-connection MW limits |
| First-year charged AC energy | **121,165 MWh** | **first year of actual operation** | ECO STOR case study, reported ~2026 | For plausibility / operational validation; not a limit per day |
| First-year discharged AC energy | **107,806 MWh** | **same reporting period, same asset** | ECO STOR case study | For plausibility / operational validation |
| Reported overall **AC efficiency** | **about 89%** | first year measured | ECO STOR case study | **Observed aggregate performance**, not automatically ηcharge or ηdischarge. First-year discharge/charge ratio ≈88.98%. Includes real operating conditions; does not alone identify per-leg efficiency or stand-by losses |
| Availability | **95.74%** | realized calendar year **2025** | ECO STOR case study | Descriptive annual KPI, **not** a 2026 per-slot outage schedule |
| Expected 2026 availability | **97–98%** | management's forecast, **not measured** | ECO STOR case study | Never label as observed |
| Wholesale operational ramp rule | **15-minute ramps** rather than customary 2.5-minute ramp | real site/operator discussion | ECO STOR case study | Important real *operating constraint*. Does **not** publish a numerical MW/min ramp limit; cannot naively derive a linear `abs(ΔP) ≤ R` without more data |
| Market participation | day-ahead, intraday and ancillary-services | reported operational activity | ECO STOR; Entelios | Project is mult-market, while proposed study is **day-ahead-only simplification** |
| Owner changed to Alpiq | reported on **2026-08-25** | Alpiq release | Alpiq; ECO STOR | Relevant to provenance, not battery physics |
| Public operational dashboard | `https://speicherbetrieb.eco-stor.de/` | publicly launched 2026-06-24; actual asset operation and dynamic grid constraints | ECO STOR press release | **High-priority validation data**; dashboard accessible as a URL, BUT CSV/API exports, granular coverage and schema have **not been independently retrieved/tested here** |

**Source precision caveat:** Entelios markets the same Bollingstedt asset as **238.5 MWh**, while ECO STOR and the current owner Alpiq publish **238 MWh**. This is a documented **same-asset, different-source discrepancy** (likely a reporting convention/rounding, not verified). For the initial nameplate parameter select **238 MWh from developer/current owner**, disclose discrepancy, and do not call 238 MWh usable stored energy until the DC/AC definition and SOC window are verified.

The published approximate nameplate duration is `238 / 103.5 ≈ 2.30 h` (**derived**, not a separate certified site measurement).

## Not yet publicly verified FOR BOLLINGSTEDT — leave unknown

| Required modeling quantity | Status | Why not filled |
|---|---|---|
| Minimum SOC / maximum SOC | **UNKNOWN** | No public project-specific BMS/dispatch operating window verified |
| Initial SOC on each historical backtest day | **UNKNOWN** | Must derive from verified measurements or apply **clearly disclosed experiment policy**, not pretend measured |
| End-of-day SOC policy | **UNKNOWN** | Actual trading/operating policies and cross-day commitments not published |
| Separate charging efficiency `ηc` | **UNKNOWN** | Aggregate measured AC efficiency cannot uniquely identify ηc |
| Separate discharging efficiency `ηd` | **UNKNOWN** | Cannot uniquely separate from measured aggregate efficiency and auxiliaries |
| AC/DC definition and usable storage energy | **UNKNOWN** | Public rated MWh may not equal usable internal-energy span |
| Site fixed O&M (EUR/year) | **UNKNOWN** | No project-specific contract/cost statement verified |
| Variable O&M (EUR/MWh) | **UNKNOWN** | No project-specific service-contract metric verified |
| Cycle-dependent degradation cost and warranty | **UNKNOWN** | No project-specific warranty, replacement budget or cycle/throughput limits verified |
| Battery-side auxiliary consumption | **UNKNOWN** | AC metering and standby consumption not quantified in cited site materials |
| Grid connection symmetric/asymmetric MW constraints | **UNKNOWN** | 110-kV voltage is known; dynamic available MW grid envelope varies with conditions |
| Exact quantitative ramp rate | **UNKNOWN** | Operator says 15-minute ramps, not exact MW/min limits |
| Full-quarter-hour availability/curtailment | **UNKNOWN** | Annual 2025 KPI is not a slot-level outage series |
| Measured per-market settlements and fees | **UNKNOWN** | Day-ahead-only benchmark does not reproduce real combined DA/ID/FCR/aFRR revenues |

**Important correction to earlier generic suggestion:** Do **not** use 85% round-trip efficiency from a different NREL reference to describe Bollingstedt: ECO STOR itself publishes around **89% first-year AC efficiency** for **this battery**. If a solver requires two per-leg efficiencies *before better evidence*, one could impose the **explicit symmetry assumption** `ηc=ηd=sqrt(0.89)≈0.9434`, derived from the **same plant's aggregate** 89%, but **these would still be modeling assumptions, not measured Bollingstedt parameters**. This simplification ignores possible auxiliary/standby and state changes. Better test a calibrated uncertainty range rather than quietly hard-code it as factual.

Likewise, **do not source an arbitrary SOC window, O&M € rate, degradation € rate, or ramp MW/min from some unrelated installed asset**. If needed to explore the math, use a transparent toy/sensitivity run flagged **ILLUSTRATIVE, NOT REAL OPERATING POLICY**, separate from asset-specific results, and seek site-specific evidence before validating economics.

## Practical experiment design using ONLY this asset

1. **Keep the real technical figures with explicit origin/date**: P=103.5 MW, published E=238 MWh, measured first-year aggregate AC efficiency≈89%, 2025 availability=95.74%, LFP, wholesale 15-minute ramp statement, and published operational data dashboard.
2. **Price data**: obtain authentic 15-minute **DE-LU day-ahead market prices** from a market source. These prices are shared by all assets in the same bidding zone; they are *not* another battery's specifications. Do not confuse day-ahead price-time series with Bollingstedt's reported *actual* multi-market revenues.
3. **Data audit**: assess whether public dashboard exports provide actual Bollingstedt net power, grid-permitted dynamic limits, timestamps, and 2026 operation; establish documented definitions, missingness and terms of reuse before download/validation. The dashboard is a **source prospect**, not yet an extracted CSV/API dataset.
4. **Avoid impossible exact replication**: a simplified **DA-only** price-taking optimizer will not recreate actual Bollingstedt dispatch because the real plant participates in ancillary and intraday markets and is subject to FCA dynamic grid and ramp constraints.
5. **Reproducibility**: log table of every numerical parameter: value, unit, provenance, measurement period, meter boundary, VERIFIED/DERIVED/ASSUMED/UNKNOWN, URL. For cross-source conflicts, keep both reported values until reconciled.
6. **Additional data request**: project technical specification, actual usable energy and SOC limits, separate AC/energy efficiency, auxiliary-power measurement definition, dynamic connection/ramp envelope, operation/maintenance and throughput-warranty disclosures. No assertion that these are currently public.

## Primary and close-to-primary citations

1. ECO STOR, official Bollingstedt asset page: https://www.eco-stor.de/de/unsere%20speicher/Projekt%20Bollingstedt
2. ECO STOR, **Bollingstedt first-year case study** — measured 121,165 MWh in, 107,806 MWh out, ~89% AC efficiency, 2025 availability 95.74%; real 15-minute ramp and dynamic grid constraints: https://www.eco-stor.de/case_study_bollingstedt
3. Alpiq, current owner's Bollingstedt asset page: https://www.alpiq.com/energy/assets/battery-energy-storage-systems/bess-bollingstedt
4. Alpiq, 2026-08-25 acquisition announcement: https://www.alpiq.com/cz/newsroom/media-releases/alpiq-adds-major-german-battery-storage-system-to-its-portfolio
5. Entelios, Bollingstedt project reference (238.5 MWh, LFP, markets, 110 kV): https://www.entelios.de/en/referenzen/eco-store/
6. ECO STOR, public operational dashboard launch, 2026-06-24: https://www.eco-stor.de/de/unternehmen/news/260624_ECO_STOR_praesentiert_erstes_Speicherbetriebs-Dashboard_fuer_Batteriegrossspeicher
7. Operator's public operational dashboard landing page: https://speicherbetrieb.eco-stor.de/

**No files of actual time-series measurements, licensed downloaded data, or trained/optimized results were added with this evidence note.**
