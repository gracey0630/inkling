# Trusted sources (draft)

Candidate whitelist for the RAG corpus (education answers must cite one of these; "I don't know"
if nothing relevant is retrieved — see CLAUDE.md safety stance). **Not yet logged as a decision —
for team review before it goes in `docs/decisions.md`.** Ties to the timeline task "Draft the
trusted-source whitelist (org + why trusted)."

**Selection criteria:** government health agency or medical society, no commercial incentive
(rules out brand/WebMD-style sites), matches a topic the product needs (cycle basics, birth
control, red-flag conditions).

| Org | Why trusted | Covers | URL |
|---|---|---|---|
| **ACOG** (American College of Obstetricians and Gynecologists) | US medical society for OB-GYNs; patient FAQs written/reviewed by practicing clinicians | Abnormal uterine bleeding, dysmenorrhea (painful periods), adolescent menstruation guidance | `acog.org/womens-health/faqs/abnormal-uterine-bleeding`, `.../dysmenorrhea-painful-periods` — verified by hand (ACOG blocks automated fetches) |
| **NICHD** (NIH) | Federal research institute funding menstrual-health research; treats menstruation as a "fifth vital sign" | Menstrual cycle basics, irregularities, when to see a provider | `nichd.nih.gov/health/topics/menstruation` (reviewed 2017 — dated, but the basics it covers don't change) |
| **MedlinePlus** (National Library of Medicine) | NLM's consumer-health arm; plain-language, physician-reviewed, no ads | Period basics, cycle overview, links out to NICHD/CDC | `medlineplus.gov/menstruation.html` (updated May 2026) |
| **CDC** | Federal public-health authority; maintains the clinical standard (US MEC/SPR) for contraception | Birth-control method overviews, effectiveness, who should avoid which method | `cdc.gov/contraception/index.html` |
| **NHS** (UK) | National health service, independent of US clinical politics; good for cross-checking | Period basics, PMS, delaying periods with the pill, fertility | `nhs.uk/conditions/periods/` (review date lapsed Jan 2026 — still live, flagged as slightly stale) |
| **Office on Women's Health** (HHS) | Federal women's-health office, aimed at a lay audience | Menstrual cycle overview, PMS, period problems | `womenshealth.gov/menstrual-cycle`; birth control at `womenshealth.gov/a-z-topics/birth-control-methods` (not `/birth-control/...` — that one 404s) |

**Gaps:** none of these directly address D25's `Fertility`→`ovulatory` framing concern, or PCOS.
Candidates to add: Endocrine Society (PCOS patient page) or an ACOG PCOS-specific page, once found.
