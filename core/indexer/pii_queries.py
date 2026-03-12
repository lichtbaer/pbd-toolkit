"""Predefined PII exemplar texts per category for vector-based detection.

Each category maps to a list of representative example texts (in German and English).
These exemplars are embedded at startup and used as reference vectors for semantic
similarity comparison against document chunks.

Adding new categories or exemplars here automatically extends detection coverage
without any changes to the engine code.
"""

# Mapping: category name → list of representative example texts
# The category name is used as the entity_type in DetectionResult.
PII_EXEMPLARS: dict[str, list[str]] = {
    "VECTOR_PERSON": [
        "Max Mustermann, 35 Jahre alt, Softwareentwickler aus Frankfurt",
        "Name: Anna Schmidt, geboren am 15. März 1988 in München",
        "Herr Dr. Klaus Weber, Facharzt für Innere Medizin",
        "Frau Maria Bauer, verheiratet, zwei Kinder",
        "John Doe, age 42, residing in London, UK",
        "Full name: Jane Smith, date of birth: May 20, 1990",
        "Mr. Robert Johnson, Senior Manager, hired in 2019",
    ],
    "VECTOR_ADDRESS": [
        "Wohnhaft in der Musterstraße 12, 60313 Frankfurt am Main",
        "Adresse: Hauptstraße 5, 10115 Berlin, Deutschland",
        "Meldeadresse: Parkweg 3, 80333 München, Bayern",
        "Lieferanschrift: Industriepark 7, 70173 Stuttgart",
        "123 Main Street, New York, NY 10001, USA",
        "Home address: 42 Baker Street, London W1U 6RY, United Kingdom",
        "Shipping address: 500 Oracle Pkwy, Redwood City, CA 94065",
    ],
    "VECTOR_EMAIL": [
        "Bitte kontaktieren Sie uns unter max.mustermann@beispiel.de",
        "E-Mail-Adresse: info@unternehmen.com",
        "Anfragen an: bewerbung@firma.de oder personal@firma.de",
        "Meine private E-Mail: a.schmidt@gmail.com",
        "Please email: contact@example.org",
        "Send your inquiry to admin@company.co.uk",
        "Reach me at: firstname.lastname@corporate.com",
    ],
    "VECTOR_PHONE": [
        "Erreichbar unter: +49 69 1234567 oder 069/765432",
        "Telefonnummer: 030 - 123 456 78, Fax: 030 - 123 456 79",
        "Mobil: +49 151 98765432, Büro: +49 40 123456",
        "Kundenservice: 0800 123 4567 (kostenlos)",
        "Phone: +1 (555) 234-5678",
        "Call us at: 020 7946 0958, ext. 204",
        "Mobile: +44 7700 900123",
    ],
    "VECTOR_ID_DOCUMENT": [
        "Personalausweis-Nr.: L01X00T47, gültig bis 01.01.2030, ausgestellt Berlin",
        "Reisepass Nummer: C01X0006, ausgestellt in Frankfurt am 12.03.2022",
        "Führerschein: DE-B 12345678, Klasse B, ausgestellt am 01.06.2018",
        "Aufenthaltstitel: AT-2024-001234, gültig bis 31.12.2025",
        "Passport number: AB123456, issued in London, expires 2030",
        "Driver's license: D12345678, State: California, USA",
        "National ID card: 123-456-789, valid through 2028",
    ],
    "VECTOR_SSN": [
        "Sozialversicherungsnummer: 65 070888 B 002",
        "Rentenversicherungsnummer: 12 345678 A 123",
        "Steuer-Identifikationsnummer: 86 095 742 719",
        "Steuernummer: 181/815/08150",
        "Social Security Number: 123-45-6789",
        "National Insurance Number: QQ 12 34 56 A",
        "Tax ID: 98-7654321",
    ],
    "VECTOR_FINANCIAL": [
        "IBAN: DE89 3704 0044 0532 0130 00, BIC: COBADEFFXXX, Kontoinhaber: Müller",
        "Kontonummer: 1234567890, BLZ: 200 400 60, Deutsche Bank",
        "Girokonto bei der Sparkasse, IBAN DE12 3456 7890 1234 5678 90",
        "Bankverbindung: Volksbank Rhein-Ruhr, IBAN: DE02 3501 0060 0110 7011 00",
        "Bank account: GB29 NWBK 6016 1331 9268 19, Sort code: 60-16-13",
        "Account holder: John Smith, Account number: 12345678, Routing: 021000021",
        "Wire transfer to: IBAN CH56 0483 5012 3456 7800 9",
    ],
    "VECTOR_CREDITCARD": [
        "Kreditkartennummer: 4111 1111 1111 1111, Gültig bis 12/25, CVV: 123",
        "Visa-Karte: 4532 0151 1283 0366, Ablaufdatum: 09/26, Prüfziffer: 456",
        "MasterCard: 5425 2334 3010 9903, gültig bis 03/27, CVC: 789",
        "Kreditkarte gesperrt: 3782 822463 10005 (Amex), CVV2: 1234",
        "Credit card number: 5425 2334 3010 9903, CVV: 456, exp: 08/26",
        "Visa card ending in 4242, expiry: 01/28, billing zip: 10001",
        "MasterCard: 2720 9960 1390 2897, valid through 03/27",
    ],
    "VECTOR_HEALTH": [
        "Diagnose: Diabetes mellitus Typ 2, behandelnder Arzt: Dr. Weber, AOK-versichert",
        "Patient Müller, Versichertennummer: A123456789, Diagnose: Bluthochdruck",
        "Krankenakte: Herzinsuffizienz Grad II, stationär aufgenommen 14.01.2024",
        "Medikation: Metformin 1000mg 2x täglich, verschrieben von Dr. Schäfer",
        "Medical record: Patient John Doe, diagnosis: hypertension, Dr. Smith, NHS",
        "Health condition: Type 1 diabetes, insulin therapy, insurance ID: 987654321",
        "Prescription: Lisinopril 10mg daily, patient DOB: 1965-03-22",
    ],
    "VECTOR_BIOMETRIC": [
        "Fingerabdruckdaten gespeichert, Mitarbeiter-ID: EMP-2024-001, Referenz: BIO-A3F7",
        "Gesichtserkennung aktiv, Biometrie-Hash: a3f7b2c1d9e4, Kamera-ID: CAM-03",
        "Iris-Scan registriert für Zugangskontrolle, Benutzer-ID: USR-00456",
        "Stimmabdruck-Profil erstellt, Authentifizierungssystem Version 2.1",
        "Biometric data: fingerprint template stored for employee ID: EMP-9876",
        "Face recognition profile created, confidence: 99.2%, user: jsmith",
        "Voice authentication enrolled, retinal scan reference: RET-20240115",
    ],
    "VECTOR_LOCATION": [
        "GPS-Koordinaten: 50.1109° N, 8.6821° E (Frankfurt Innenstadt)",
        "Standortdaten: Breitengrad 52.5200, Längengrad 13.4050, Berlin",
        "Aufenthaltsort laut Mobilfunkdaten: Düsseldorf, 20:14 Uhr",
        "Bewegungsprofil: täglicher Pendelweg von Wiesbaden nach Frankfurt",
        "Location tracking: 40.7128°N 74.0060°W, New York City",
        "Last known position: 51.5074°N, 0.1278°W, London",
        "Check-in history: San Francisco, CA at 2024-01-15 09:30 UTC",
    ],
    "VECTOR_VEHICLE": [
        "Kraftfahrzeugkennzeichen: F-AB 1234, Fahrzeug: VW Golf, Halter: Müller",
        "KFZ: B-XY 9876, FIN: WBA3A5C59FK135071, TÜV bis 04/2026",
        "Fahrzeugbrief für: Mercedes E200, Kennzeichen MK-AB 987",
        "License plate: CA 7ABC234, VIN: 1HGBH41JXMN109186",
        "Vehicle registration: ABC-1234, registered to Jane Doe, expires 2025",
        "Motor vehicle: Reg. LK21 ABC, owner: R. Johnson, MOT due: Nov 2025",
    ],
    "VECTOR_CREDENTIALS": [
        "Benutzername: max.mustermann, Passwort: Muster123!, System: SAP",
        "Login: admin@firma.de, Kennwort: P@ssw0rd2024, VPN-Zugang",
        "SSH-Schlüssel für Benutzer deploy, Fingerprint: SHA256:abc123...",
        "API-Token: sk-proj-abc123xyz789, gültig bis 31.12.2024",
        "Username: jsmith, password: Hunter2!, system: internal portal",
        "API key: Bearer eyJhbGciOiJSUzI1NiJ9..., expires 2024-12-31",
        "Private key file: ~/.ssh/id_rsa, passphrase stored in keychain",
    ],
}

# Flat list of (category, exemplar_text) tuples for batch embedding
EXEMPLAR_PAIRS: list[tuple[str, str]] = [
    (category, text) for category, texts in PII_EXEMPLARS.items() for text in texts
]
