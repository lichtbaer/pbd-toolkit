# Ordnerstruktur der Synthetischen Datensammlung
# Directory Structure of Synthetic Data Collection

Erstellt am: 03.01.2026 13:40:12

---

## Vollständige Verzeichnisbaum / Complete Directory Tree

```
synthetic_data_collection/
├── COLLECTION_STATS.json
├── DATASET_INVENTORY.csv
├── README.md
├── business_data
│   ├── concepts
│   │   └── _annotations
│   ├── construction
│   │   └── _annotations
│   ├── emails
│   │   └── _annotations
│   ├── finance
│   │   └── _annotations
│   ├── patents
│   │   └── _annotations
│   └── presentations
│       ├── Board_Meeting_Digital_Transformation_Strategy.pptx
│       ├── Customer_Contract_Review_Risk_Assessment.pptx
│       ├── Employee_Compensation_Review_2024.pptx
│       ├── M&A_Due_Diligence_TechInnovate_Acquisition.pptx
│       ├── Q2_2024_Sales_Strategy_Financial_Forecast.pptx
│       └── _annotations
│           ├── PRES001_Q2_2024_Sales_Strategy_Financial_Forecast.json
│           ├── PRES002_Employee_Compensation_Review_2024.json
│           ├── PRES003_Customer_Contract_Review_Risk_Assessment.json
│           ├── PRES004_M&A_Due_Diligence_TechInnovate_Acquisition.json
│           └── PRES005_Board_Meeting_Digital_Transformation_Strategy.json
├── legal_data
│   ├── case_files
│   │   └── _annotations
│   ├── contracts
│   │   ├── _annotations
│   │   │   ├── LEG001_service_agreement_confidentiality.json
│   │   │   ├── LEG002_nda_mutual.json
│   │   │   ├── LEG003_consumer_terms_conditions.json
│   │   │   ├── LEG004_settlement_agreement_dispute.json
│   │   │   └── LEG005_data_processing_agreement_dpa.json
│   │   ├── consumer_terms_conditions.md
│   │   ├── data_processing_agreement_dpa.md
│   │   ├── nda_mutual.md
│   │   ├── service_agreement_confidentiality.md
│   │   └── settlement_agreement_dispute.md
│   └── correspondence
│       └── _annotations
├── medical_data
│   ├── dicom_datasets
│   │   └── _annotations
│   ├── prescriptions
│   │   ├── _annotations
│   │   │   ├── MED001_prescription_diabetes_treatment.json
│   │   │   ├── MED002_prescription_psychiatric_medication.json
│   │   │   ├── MED003_sick_leave_certificate.json
│   │   │   ├── MED004_prescription_dermatology.json
│   │   │   └── MED005_prescription_oncology_chemotherapy.json
│   │   ├── prescription_dermatology.md
│   │   ├── prescription_diabetes_treatment.md
│   │   ├── prescription_oncology_chemotherapy.md
│   │   ├── prescription_psychiatric_medication.md
│   │   └── sick_leave_certificate.md
│   └── research_requests
│       └── _annotations
├── personnel_data
│   ├── contracts
│   │   └── _annotations
│   ├── hiring_letters
│   │   ├── _annotations
│   │   │   ├── HR001_job_offer_letter_senior_developer.json
│   │   │   ├── HR002_employment_contract_manager.json
│   │   │   ├── HR003_termination_letter_redundancy.json
│   │   │   ├── HR004_promotion_announcement_internal.json
│   │   │   └── HR005_performance_review_annual.json
│   │   ├── employment_contract_manager.md
│   │   ├── job_offer_letter_senior_developer.md
│   │   ├── performance_review_annual.md
│   │   ├── promotion_announcement_internal.md
│   │   └── termination_letter_redundancy.md
│   └── personal_files
│       └── _annotations
└── private_data
    ├── documents
    │   ├── _annotations
    │   │   ├── DOC001_utility_bill_january_2024.json
    │   │   ├── DOC002_hospital_discharge_letter.json
    │   │   ├── DOC003_personal_loan_agreement.json
    │   │   ├── DOC004_resignation_letter_formal.json
    │   │   └── DOC005_rental_lease_agreement.json
    │   ├── hospital_discharge_letter.md
    │   ├── personal_loan_agreement.md
    │   ├── rental_lease_agreement.md
    │   ├── resignation_letter_formal.md
    │   └── utility_bill_january_2024.md
    ├── emails
    │   └── _annotations
    ├── lists
    │   └── _annotations
    └── photos
        ├── _annotations
        │   ├── PH001_holiday_beach_family_2024.json
        │   ├── PH002_birthday_celebration_indoor.json
        │   ├── PH003_travel_passport_documents.json
        │   ├── PH004_family_wedding_ceremony.json
        │   └── PH005_children_playground_afternoon.json
        ├── birthday_celebration_indoor.jpg
        ├── children_playground_afternoon.jpg
        ├── family_wedding_ceremony.jpg
        ├── holiday_beach_family_2024.jpg
        └── travel_passport_documents.jpg

```

---

## Detaillierte Übersicht / Detailed Overview

### synthetic_data_collection/
**Hauptverzeichnis mit Dokumentation**

├── **README.md** - Umfassende Dokumentation des Datensatzes
├── **COLLECTION_STATS.json** - Statistische Übersicht aller Datensätze
├── **DATASET_INVENTORY.csv** - Detaillierte Inventur in tabellarischer Form

---

### private_data/ (10 Dateien + 10 Annotationen)

#### private_data/photos/ (5 Bilder + 5 Annotationen)
- **holiday_beach_family_2024.jpg** + PH001_holiday_beach_family_2024.json
  * Urlaubsfoto mit erkennbaren Familienangehörigen
  * Art. 9: Biometric (Gesichter)
  * GDPR-Risiko: **HIGH**
  * Personen: 4

- **birthday_celebration_indoor.jpg** + PH002_birthday_celebration_indoor.json
  * Geburtstagsfeier Foto mit mehreren Gästen
  * GDPR-Risiko: **MEDIUM**
  * Personen: 8

- **travel_passport_documents.jpg** + PH003_travel_passport_documents.json
  * Reisedokumente inklusive Reisepass
  * Art. 9: Biometric (Passfoto)
  * GDPR-Risiko: **HIGH**
  * Personen: 1

- **family_wedding_ceremony.jpg** + PH004_family_wedding_ceremony.json
  * Hochzeitsfoto mit Braut, Bräutigam und Familie
  * Art. 9: Biometric
  * GDPR-Risiko: **HIGH**
  * Personen: 12

- **children_playground_afternoon.jpg** + PH005_children_playground_afternoon.json
  * Kinderfotos auf Spielplatz (Minderjährige)
  * Art. 9: Biometric
  * GDPR-Risiko: **HIGH** (besondere Schutzbedürftigkeit)
  * Personen: 6

#### private_data/documents/ (5 Markdown + 5 Annotationen)
- **utility_bill_january_2024.md** + DOC001_utility_bill_january_2024.json
  * Stromrechnung mit Kundendaten und Verbrauch
  * Personen: 1 | GDPR-Risiko: HIGH

- **hospital_discharge_letter.md** + DOC002_hospital_discharge_letter.json
  * Krankenhaus-Entlassungsbrief mit Diagnose
  * Art. 9: **HEALTH** | GDPR-Risiko: HIGH

- **personal_loan_agreement.md** + DOC003_personal_loan_agreement.json
  * Kreditvertrag mit finanziellen Details
  * Personen: 1 | GDPR-Risiko: HIGH

- **resignation_letter_formal.md** + DOC004_resignation_letter_formal.md
  * Kündigungsbrief mit Gehalt und Boni
  * Personen: 1 | GDPR-Risiko: MEDIUM

- **rental_lease_agreement.md** + DOC005_rental_lease_agreement.json
  * Mietvertrag mit Mieter, Vermieter und Garantiegeber
  * Personen: 3 | GDPR-Risiko: HIGH

---

### business_data/ (5 Präsentationen + 5 Annotationen)

#### business_data/presentations/ (5 PPTX + 5 Annotationen)
- **Q2_2024_Sales_Strategy_Financial_Forecast.pptx** + PRES001_Q2_2024_Sales_Strategy_Financial_Forecast.json
  * Verkaufs- und Finanzprognosen mit Mitarbeiterdaten
  * Personen: 1 | GDPR-Risiko: MEDIUM

- **Employee_Compensation_Review_2024.pptx** + PRES002_Employee_Compensation_Review_2024.json
  * Gehälterübersicht mit Mitarbeiterdaten (SEHR SENSIBEL)
  * Personen: 30 | GDPR-Risiko: **HIGH**

- **Customer_Contract_Review_Risk_Assessment.pptx** + PRES003_Customer_Contract_Review_Risk_Assessment.json
  * Kundenvertrag-Analyse mit At-Risk-Accounts
  * Personen: 4 | GDPR-Risiko: MEDIUM

- **M&A_Due_Diligence_TechInnovate_Acquisition.pptx** + PRES004_M&A_Due_Diligence_TechInnovate_Acquisition.json
  * M&A-Daten mit Zielunternehmen-Information (VERTRAULICH)
  * Personen: 85 | GDPR-Risiko: **HIGH**

- **Board_Meeting_Digital_Transformation_Strategy.pptx** + PRES005_Board_Meeting_Digital_Transformation_Strategy.json
  * Strategische Planung (generisch, keine sensiblen Daten)
  * Personen: 0 | GDPR-Risiko: LOW

---

### medical_data/ (5 Rezepte + 5 Annotationen)

#### medical_data/prescriptions/ (5 Markdown + 5 Annotationen)
- **prescription_diabetes_treatment.md** + MED001_prescription_diabetes_treatment.json
  * Rezept für Diabetesbehandlung
  * Art. 9: **HEALTH** | GDPR-Risiko: **HIGH**
  * Ärztliche Schweigepflicht!

- **prescription_psychiatric_medication.md** + MED002_prescription_psychiatric_medication.json
  * Rezept für psychotrope Medikation (EXTREM SENSIBEL)
  * Art. 9: **HEALTH** | GDPR-Risiko: **HIGH**
  * Psychiatrische Daten mit Diskriminierungsrisiko

- **sick_leave_certificate.md** + MED003_sick_leave_certificate.json
  * Krankschreibung mit Diagnose und Arbeitgeber-Link
  * Art. 9: **HEALTH** | GDPR-Risiko: **HIGH**
  * Verbindung: Medizin + Arbeit

- **prescription_dermatology.md** + MED004_prescription_dermatology.md
  * Dermatologie-Rezept für Wundbehandlung
  * Art. 9: **HEALTH** | GDPR-Risiko: HIGH

- **prescription_oncology_chemotherapy.md** + MED005_prescription_oncology_chemotherapy.json
  * Chemotherapie-Rezept für Krebs (HOCHSENSITIV)
  * Art. 9: **HEALTH** | GDPR-Risiko: **HIGH**
  * Potenzielle Lebensbedrohliche Diagnose

---

### personnel_data/ (5 HR-Dokumente + 5 Annotationen)

#### personnel_data/hiring_letters/ (5 Markdown + 5 Annotationen)
- **job_offer_letter_senior_developer.md** + HR001_job_offer_letter_senior_developer.json
  * Arbeitsangebot mit Gehalt und Benefits
  * Personen: 1 | GDPR-Risiko: MEDIUM

- **employment_contract_manager.md** + HR002_employment_contract_manager.json
  * Arbeitsvertrag mit vollständigen Bedingungen
  * Personen: 1 | GDPR-Risiko: **HIGH**

- **termination_letter_redundancy.md** + HR003_termination_letter_redundancy.json
  * Kündigungsschreiben mit Abfindung (KONFIDENTIELL)
  * Personen: 1 | GDPR-Risiko: **HIGH**

- **promotion_announcement_internal.md** + HR004_promotion_announcement_internal.json
  * Interne Beförderungsmitteilung (VERTRAUENSMITTEILUNG)
  * Personen: 2 | GDPR-Risiko: **HIGH**

- **performance_review_annual.md** + HR005_performance_review_annual.json
  * Jährliche Leistungsbewertung mit Benotung
  * Personen: 1 | GDPR-Risiko: **HIGH**

---

### legal_data/ (5 Verträge + 5 Annotationen)

#### legal_data/contracts/ (5 Markdown + 5 Annotationen)
- **service_agreement_confidentiality.md** + LEG001_service_agreement_confidentiality.json
  * Dienstleistungsvertrag mit Geheimhaltung
  * Personen: 2 | GDPR-Risiko: **HIGH**
  * Geschäftsvertrauliche Informationen

- **nda_mutual.md** + LEG002_nda_mutual.json
  * Gegenseitige NDA in Pharmaindustrie
  * Personen: 2 | GDPR-Risiko: **HIGH**
  * Potenzielle Gesundheitsdaten (Pharmabranche)

- **consumer_terms_conditions.md** + LEG003_consumer_terms_conditions.json
  * Allgemeine Geschäftsbedingungen (E-Commerce)
  * Personen: 0 | GDPR-Risiko: LOW
  * Öffentlich verfügbar

- **settlement_agreement_dispute.md** + LEG004_settlement_agreement_dispute.json
  * Vergleichsvereinbarung mit finanziellen Bedingungen
  * Personen: 2 | GDPR-Risiko: **HIGH**
  * Streng vertraulich (unter NDA)

- **data_processing_agreement_dpa.md** + LEG005_data_processing_agreement_dpa.json
  * GDPR Art. 28 Auftragsverarbeitungsvertrag
  * Personen: 2 | GDPR-Risiko: **HIGH**
  * Umfasst bis zu 500.000 betroffene Personen

---

## Verwendungs-Richtlinien / Usage Guidelines

### ✓ Geeignet für:
- Benchmarking von PII-Extraktions-Systemen
- Training von Klassifizierungs-Modellen
- Privacy-Impact-Assessment-Automatisierung
- GDPR-Compliance-Überprüfung
- Data Discovery und Classification Tools
- Anonymisierungs- und Pseudonymisierungs-Tests
- Datenminimierungs-Forschung

### ✗ NICHT geeignet für:
- Öffentliche Datensätze / Public Datasets
- Geschäftliche Zwecke ohne Genehmigung
- Direkte Schulung von kommerziellen Systemen ohne Lizenz

### ⚠️ Sicherheit und Datenschutz:
- Alle Daten sind synthetisch und fiktiv
- Keine echten Personen oder Fälle
- Trotzdem: Behandle wie echte sensible Daten
- Verschlüsselung bei Übertragung empfohlen
- Zugriff sollte auf Forschungsteam beschränkt sein

---

**Versionsinformation:**
- Schema Version: 1.0
- Datensätze: 30 (mit Potential auf 100+)
- Dokumentation: Complete
- Letztes Update: 03.01.2026

