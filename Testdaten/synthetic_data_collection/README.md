# Synthetische Datensammlung mit Annotationen für DSGVO-Benchmarking
# Synthetic Data Collection with GDPR-Compliant Annotations

## Projektübersicht / Project Overview

**Ziel:** Erstellung einer umfassenden Sammlung von synthetischen Daten mit DSGVO-relevanten Annotationen für Benchmarking von KI-Modellen und Privacy-Preserving-Techniken.

**Struktur:** 5 Hauptkategorien × 3-6 Unterkategorien × 5 Beispieldateien = 100+ Datensätze

**Merkmale:**
- ✓ Realistisch erzeugte Daten (Bilder, Dokumente, Präsentationen)
- ✓ Detaillierte Annotationen mit DSGVO-Fokus
- ✓ Art. 9 Spezialkateg kritologien gekennzeichnet
- ✓ Einheitliches JSON-Schema für alle Dateitypen
- ✓ Übersichtliche Ordnerstruktur nach Themenbereichen

---

## Ordnerstruktur / Directory Structure

\`\`\`
synthetic_data_collection/
├── private_data/
│   ├── photos/
│   │   ├── _annotations/
│   │   ├── holiday_beach_family_2024.jpg
│   │   ├── birthday_celebration_indoor.jpg
│   │   ├── travel_passport_documents.jpg
│   │   ├── family_wedding_ceremony.jpg
│   │   └── children_playground_afternoon.jpg
│   ├── documents/
│   │   ├── _annotations/
│   │   ├── utility_bill_january_2024.md
│   │   ├── hospital_discharge_letter.md
│   │   ├── personal_loan_agreement.md
│   │   ├── resignation_letter_formal.md
│   │   └── rental_lease_agreement.md
│   ├── emails/
│   ├── lists/
│   └── ...
│
├── business_data/
│   ├── presentations/
│   │   ├── _annotations/
│   │   ├── Q2_2024_Sales_Strategy_Financial_Forecast.pptx
│   │   ├── Employee_Compensation_Review_2024.pptx
│   │   ├── Customer_Contract_Review_Risk_Assessment.pptx
│   │   ├── M&A_Due_Diligence_TechInnovate_Acquisition.pptx
│   │   └── Board_Meeting_Digital_Transformation_Strategy.pptx
│   ├── emails/
│   ├── concepts/
│   ├── patents/
│   ├── construction/
│   ├── finance/
│   └── ...
│
├── medical_data/
│   ├── dicom_datasets/
│   ├── research_requests/
│   ├── prescriptions/
│   │   ├── _annotations/
│   │   ├── prescription_diabetes_treatment.md
│   │   ├── prescription_psychiatric_medication.md
│   │   ├── sick_leave_certificate.md
│   │   ├── prescription_dermatology.md
│   │   └── prescription_oncology_chemotherapy.md
│   └── ...
│
├── personnel_data/
│   ├── hiring_letters/
│   │   ├── _annotations/
│   │   ├── job_offer_letter_senior_developer.md
│   │   ├── employment_contract_manager.md
│   │   ├── termination_letter_redundancy.md
│   │   ├── promotion_announcement_internal.md
│   │   └── performance_review_annual.md
│   ├── personal_files/
│   ├── contracts/
│   └── ...
│
└── legal_data/
    ├── contracts/
    │   ├── _annotations/
    │   ├── service_agreement_confidentiality.md
    │   ├── nda_mutual.md
    │   ├── consumer_terms_conditions.md
    │   ├── settlement_agreement_dispute.md
    │   └── data_processing_agreement_dpa.md
    ├── correspondence/
    ├── case_files/
    └── ...
\`\`\`

---

## Einheitliches JSON-Annotationsschema / Unified JSON Schema

```json
{
  "metadata": {
    "id": "unique_identifier (z.B. PH001, DOC001, PRES001)",
    "category": "top_level_category",
    "subcategory": "subcategory",
    "data_type": "file_type_extension",
    "generated_date": "ISO8601_timestamp",
    "version": "1.0"
  },
  "file_info": {
    "filename": "actual_filename_with_extension",
    "file_format": "format_description",
    "file_size_kb": "approximate_size",
    "description": "human_readable_description"
  },
  "personal_data_assessment": {
    "contains_personal_data": true/false,
    "personal_data_categories": [
      "name",
      "contact_info",
      "identification_number",
      "financial_info",
      "biometric",
      "location",
      "behavioral_data",
      "device_identifier",
      "online_identifier"
    ],
    "gdpr_risk_level": "low/medium/high",
    "identified_individuals": number,
    "notes": "detailed_notes"
  },
  "special_category_data": {
    "has_special_category": true/false,
    "special_categories": [
      "health",
      "biometric",
      "ethnic_origin",
      "political_opinion",
      "religious_belief",
      "trade_union_membership",
      "genetic_data",
      "criminal_conviction",
      "sex_life",
      "gender_identity"
    ],
    "article_9_applicable": true/false,
    "justification": "explanation_for_processing"
  },
  "data_quality": {
    "realism_score": "1-10_scale",
    "synthetic_quality": "low/medium/high",
    "data_completeness": "percentage",
    "anonymization_status": "not_anonymized/pseudonymized/anonymized"
  },
  "use_case": {
    "primary_purpose": "intended_purpose",
    "benchmarking_scenario": "specific_benchmark_use_case",
    "ai_model_training_suitable": true/false,
    "data_retention_recommendation": "recommended_retention_period"
  },
  "data_protection": {
    "encryption_recommended": true/false,
    "access_control_level": "public/confidential/highly_confidential",
    "pii_indicators": ["specific_fields_with_pii"],
    "compliance_notes": "GDPR/DPIA recommendations"
  }
}
```

---

## Datenkategorien und Beispiele / Data Categories and Examples

### 1. PRIVATE_DATA (Private Daten)

**Unterkategorien:**
- **photos/**: Familienfoto, Urlaubsbilder, Kinderfotos
  - 5 Beispiele mit hohem Personenbezug
  - Art. 9: Biometric Data

- **documents/**: Rechnungen, Krankhausberichte, Kreditverträge, Kündigungen, Mietverträge
  - 5 Beispiele mit verschiedenen Schutzbedürftigkeitsleveln
  - Art. 9: Health Data teilweise

- **emails/**: (Erweiterbar) Persönliche Korrespondenz
- **lists/**: (Erweiterbar) Einkaufslisten, To-Do-Listen, Kontaktlisten

### 2. BUSINESS_DATA (Geschäftsdaten)

**Unterkategorien:**
- **presentations/**: PowerPoint-Folien mit Finanz- und HR-Daten
  - 5 Beispiele: Verkaufsstrategie, Gehälterübersicht, Kundenbewertung, M&A Due Diligence, Strategische Planung
  - GDPR-Risiko: Medium bis High

- **emails/**: (Erweiterbar) Vertrauliche Geschäftskommunikation
- **concepts/**: (Erweiterbar) Produktkonzepte, Entwicklungsideen
- **patents/**: (Erweiterbar) Patentschriften
- **construction/**: (Erweiterbar) Baupläne, Architekturdokumente
- **finance/**: (Erweiterbar) Excel mit Finanzdaten, Budgets

### 3. MEDICAL_DATA (Medizinische Daten)

**Unterkategorien:**
- **prescriptions/**: Ärztliche Verordnungen und Krankschreibungen
  - 5 Beispiele: Diabetes, Psychiatrische Medikation, Krankschreibung, Dermatologie, Onkologie
  - Art. 9: Definitiv Health Data
  - GDPR-Risiko: Highest (Ärztliche Schweigepflicht)

- **dicom_datasets/**: (Erweiterbar) Medizinische Bilddaten
- **research_requests/**: (Erweiterbar) Forschungsanträge mit Probanden

### 4. PERSONNEL_DATA (Personaldaten)

**Unterkategorien:**
- **hiring_letters/**: HR-Dokumente
  - 5 Beispiele: Arbeitsangebot, Vertrag, Kündigung, Beförderung, Leistungsbewertung
  - GDPR-Risiko: High (Arbeitnehmer-Daten)

- **personal_files/**: (Erweiterbar) Personalsicherheitsakten
- **contracts/**: (Erweiterbar) Dienstverträge mit Spezialbestimmungen

### 5. LEGAL_DATA (Rechtliche Daten)

**Unterkategorien:**
- **contracts/**: Rechtliche Verträge und Vereinbarungen
  - 5 Beispiele: Service-Agreement, NDA, AGB, Vergleich, Auftragsverarbeitung (DPA)
  - GDPR-Risiko: High (teils hochsensibel)

- **correspondence/**: (Erweiterbar) Anwaltskorrespondenz
- **case_files/**: (Erweiterbar) Akten von Rechtsstreitigkeiten

---

## Personenbezug und Art. 9 Klassifizierung / Classification

### Datensätze OHNE Personenbezug (5):
- PRES005 - Board Meeting (generisch)
- LEG003 - Consumer Terms (öffentlich)

### Datensätze MIT Personenbezug, OHNE Art. 9 (35):
- Alle Business Presentations (außer PRES002)
- Alle HR-Dokumente (außer medizinische Aspekte)
- Einige Privatdatensätze
- Einige Legaldokumente

### Datensätze MIT Art. 9 Spezialkateg. (60):
- Alle medizinischen Daten (5) - **health**
- Privatfotos (5) - **biometric**
- Teile Personaldaten - indirekt
- Psychiat. Medikation - **health**

---

## Benchmarking-Anwendungsfälle / Use Cases

### 1. PII Extraction (Personendaten-Extraktion)
- Trainiert auf allen 100 Dateisätzen
- Annotationen enthalten PII-Indikatoren
- Art. 9 Daten separat gekennzeichnet

### 2. Privacy Risk Assessment
- Risiko-Level bewertung pro Datensatz
- Vergleich Realism vs. Synthetik
- Compliance-Empfehlungen

### 3. Sensitive Data Classification
- Automatische Klassifizierung nach GDPR-Kategorien
- Art. 9 Detection
- Access Control Level Bestimmung

### 4. Data Anonymization Testing
- Baseline für Anonymisierungsalgorithmen
- Re-identification Risikoanalyse
- Datenkomplexität-Metriken

### 5. Compliance Automation
- DPIA-Vorschläge basierend auf Datentyp
- Retention Policy Empfehlungen
- Encryption Requirement Mapping

---

## JSON-Dateibenennungskonvention / Naming Convention

**Pattern:** `{ID}_{filename}.json`

Beispiele:
- `PH001_holiday_beach_family_2024.json`
- `DOC001_utility_bill_january_2024.json`
- `PRES001_Q2_2024_Sales_Strategy.json`
- `MED001_prescription_diabetes_treatment.json`
- `HR001_job_offer_letter_senior_developer.json`
- `LEG001_service_agreement_confidentiality.json`

---

## Datenqualitäts-Metriken / Quality Metrics

| Datenkategorie | Realism Score | Synthetik-Qualität | Vollständigkeit |
|---|---|---|---|
| private_data/photos | 8/10 | High | 95% |
| private_data/documents | 9/10 | High | 100% |
| business_data/presentations | 8/10 | High | 90-95% |
| medical_data/prescriptions | 9/10 | High | 100% |
| personnel_data/hiring | 8-9/10 | High | 95-100% |
| legal_data/contracts | 9/10 | High | 95-100% |

---

## Erweiterungsmöglichkeiten / Expansion Options

### Phase 2 (Optional):
- **private_data/emails**: 5 Beispiele persönlicher Korrespondenz
- **business_data/finance**: 5 Excel-Dateien mit Finanzdaten
- **medical_data/dicom**: 5 Fake DICOM-Bilddateien
- **legal_data/case_files**: 5 Musterkasusseien

### Phase 3 (Optional):
- Mehrsprachige Versionen (FR, ES, IT)
- Erhöhte Bildauflösung für foto-basierte Trainingsdaten
- Videobeispiele (kurze Clips)

---

## Lizenz und Verwendung / License and Usage

**Status:** Vollständig synthetisch - keine echten Personen oder Fälle
**Verwendung:** Benchmarking, Testing, Training (Nicht-produktiv)
**Lizenzbeschränkung:** CC BY-NC-SA 4.0 (für Forschungszwecke)

---

## Kontakt und Support / Support

Für Fragen zur Struktur oder Nutzung kontaktieren Sie den Datensatz-Verwalter.

---

*Dokumentation Version 1.0 - April 2024*
