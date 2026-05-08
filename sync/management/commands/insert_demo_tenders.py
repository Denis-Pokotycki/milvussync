"""
Seed tender_translations_demo with demo data.

Five batches covering T021-T080 across all 24 EU languages:
  --batch 1   T021-T026  (9 rows)   FI, IT, DE, FR, GR, SE
  --batch 2   T027-T034  (14 rows)  NL, PT, RO, CZ, ES, PL, FR, DE
  --batch 3   T035-T044  (19 rows)  SE, BE, AT, HU, GR, FI, DK, SK, IE, BG
  --batch 4   T045-T054  (20 rows)  NL, IT, DE, FR, GR, PL, ES, CZ, PT, RO
  --batch 5   T055-T080  (50 rows)  LT, LV, ET, SL, HR, LU, MT, CY, HU, BG,
                                    IE, DK, SE, FI, PL, RO, CZ, SK, AT, ES,
                                    PT, IT, FR, DE, NL, BE
  --batch all all 112 rows (default)

Rows already present are updated (updated_at = NOW()) so auto-sync picks them up.

Usage:
  python manage.py insert_demo_tenders
  python manage.py insert_demo_tenders --batch 5
  python manage.py insert_demo_tenders --batch all --list
"""
from django.core.management.base import BaseCommand, CommandError
from milvussync.logging import get_logger
from sync.postgres.connection import get_connection

logger = get_logger(__name__)

_INSERT = """
    INSERT INTO tender_translations_demo
        (pk, tender_id, platform_id, tender_national_id, publication_date, closing_date,
         estimated_total_value, language_code, title, nut_code, nut_label, cpv_codes,
         updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (pk) DO UPDATE SET updated_at = NOW()
"""

# fmt: off
_BATCH_1 = [
    # T021  AI-assisted medical diagnostics — Finland (EN)
    ("T021_en", "T021", "PLT-FI-001", "HILMA-2024-021", "2024-08-01", "2024-10-31", 2_300_000.00, "en",
     "Artificial intelligence software platform for radiology image analysis in university hospitals",
     "FI1B1", "Helsinki-Uusimaa", ["72212000-4", "33111000-1"]),

    # T022  Public library renovation — Italy (IT + EN)
    ("T022_it", "T022", "PLT-IT-003", "CIG-2024-022", "2024-07-15", "2024-09-30", 870_000.00, "it",
     "Ristrutturazione e ampliamento della rete di biblioteche comunali di Milano",
     "ITC45", "Milano", ["45214400-4", "45000000-7"]),
    ("T022_en", "T022", "PLT-IT-003", "CIG-2024-022", "2024-07-15", "2024-09-30", 870_000.00, "en",
     "Renovation and expansion of the municipal public library network in Milan",
     "ITC45", "Milano", ["45214400-4", "45000000-7"]),

    # T023  Railway electrification — Germany (DE + EN)
    ("T023_de", "T023", "PLT-DE-003", "VgV-2024-023", "2024-09-01", "2025-01-15", 18_500_000.00, "de",
     "Elektrifizierung und Modernisierung des Schienennetzes im Großraum Hamburg",
     "DE600", "Hamburg", ["45234100-7", "45234115-5"]),
    ("T023_en", "T023", "PLT-DE-003", "VgV-2024-023", "2024-09-01", "2025-01-15", 18_500_000.00, "en",
     "Electrification and modernisation of the rail network in the Hamburg metropolitan area",
     "DE600", "Hamburg", ["45234100-7", "45234115-5"]),

    # T024  Agricultural data management — France (FR + EN)
    ("T024_fr", "T024", "PLT-FR-003", "REF-FR-2024-024", "2024-08-20", "2024-11-20", 560_000.00, "fr",
     "Développement d'un système de gestion des données agricoles et des aides PAC en Occitanie",
     "FRJ23", "Hérault", ["72212517-6", "72300000-8"]),
    ("T024_en", "T024", "PLT-FR-003", "REF-FR-2024-024", "2024-08-20", "2024-11-20", 560_000.00, "en",
     "Development of agricultural data management and EU CAP subsidies tracking system in Occitanie",
     "FRJ23", "Hérault", ["72212517-6", "72300000-8"]),

    # T025  Coastal flood protection — Greece (EN)
    ("T025_en", "T025", "PLT-GR-002", "DIAVGEIA-2024-025", "2024-10-01", "2025-02-28", 7_800_000.00, "en",
     "Construction of coastal flood protection barriers and early warning system for Thessaloniki bay",
     "EL522", "Thessaloniki", ["45246400-7", "45246200-5"]),

    # T026  Smart electricity grid — Sweden (EN)
    ("T026_en", "T026", "PLT-SE-002", "KKV-2024-026", "2024-09-15", "2024-12-15", 5_100_000.00, "en",
     "Design and deployment of smart electricity grid sensors and demand-response management platform",
     "SE110", "Stockholms län", ["31213000-2", "72212517-6"]),
]

_BATCH_2 = [
    # T027  Cybersecurity — Netherlands (NL + EN)
    ("T027_nl", "T027", "PLT-NL-003", "TED-NL-2024-027", "2024-10-01", "2025-01-15", 3_400_000.00, "nl",
     "Levering en implementatie van een zero-trust cyberbeveiligingsplatform voor overheidsinstanties",
     "NL310", "Zuid-Holland", ["72212517-6", "72220000-9"]),
    ("T027_en", "T027", "PLT-NL-003", "TED-NL-2024-027", "2024-10-01", "2025-01-15", 3_400_000.00, "en",
     "Supply and implementation of a zero-trust cybersecurity platform for government agencies",
     "NL310", "Zuid-Holland", ["72212517-6", "72220000-9"]),

    # T028  Water treatment plant — Portugal (PT + EN)
    ("T028_pt", "T028", "PLT-PT-002", "BASE-PT-2024-028", "2024-09-20", "2025-03-20", 12_000_000.00, "pt",
     "Construção de nova estação de tratamento de águas residuais na região metropolitana do Porto",
     "PT11A", "Grande Porto", ["45252100-9", "45232420-2"]),
    ("T028_en", "T028", "PLT-PT-002", "BASE-PT-2024-028", "2024-09-20", "2025-03-20", 12_000_000.00, "en",
     "Construction of a new wastewater treatment plant in the Porto metropolitan area",
     "PT11A", "Grande Porto", ["45252100-9", "45232420-2"]),

    # T029  School digitisation — Romania (RO + EN)
    ("T029_ro", "T029", "PLT-RO-002", "SEAP-RO-2024-029", "2024-11-01", "2025-02-28", 4_750_000.00, "ro",
     "Dotarea școlilor din mediul rural cu echipamente digitale și infrastructură de rețea",
     "RO321", "Ilfov", ["30213000-5", "32420000-3"]),
    ("T029_en", "T029", "PLT-RO-002", "SEAP-RO-2024-029", "2024-11-01", "2025-02-28", 4_750_000.00, "en",
     "Supplying rural schools with digital equipment and network infrastructure",
     "RO321", "Ilfov", ["30213000-5", "32420000-3"]),

    # T030  Urban mobility app — Czech Republic (CS + EN)
    ("T030_cs", "T030", "PLT-CZ-002", "ISVZ-CZ-2024-030", "2024-10-15", "2025-01-31", 980_000.00, "cs",
     "Vývoj mobilní aplikace pro integrovanou veřejnou dopravu v Brněnské metropolitní oblasti",
     "CZ064", "Jihomoravský kraj", ["72212517-6", "72300000-8"]),
    ("T030_en", "T030", "PLT-CZ-002", "ISVZ-CZ-2024-030", "2024-10-15", "2025-01-31", 980_000.00, "en",
     "Development of a mobile app for integrated public transport in the Brno metropolitan area",
     "CZ064", "Jihomoravský kraj", ["72212517-6", "72300000-8"]),

    # T031  Solar energy park — Spain (ES + EN)
    ("T031_es", "T031", "PLT-ES-004", "BOE-2024-031", "2024-11-05", "2025-04-30", 22_500_000.00, "es",
     "Construcción de parque solar fotovoltaico de 50 MW con sistema de almacenamiento en baterías en Extremadura",
     "ES431", "Extremadura", ["09331200-0", "45261215-4"]),
    ("T031_en", "T031", "PLT-ES-004", "BOE-2024-031", "2024-11-05", "2025-04-30", 22_500_000.00, "en",
     "Construction of a 50 MW photovoltaic solar park with battery storage system in Extremadura",
     "ES431", "Extremadura", ["09331200-0", "45261215-4"]),

    # T032  Border crossing infrastructure — Poland (PL + EN)
    ("T032_pl", "T032", "PLT-PL-003", "BZP-PL-2024-032", "2024-12-01", "2025-05-31", 8_200_000.00, "pl",
     "Modernizacja i rozbudowa infrastruktury przejścia granicznego wraz z systemem kontroli celnej",
     "PL811", "Podkarpackie", ["45221000-2", "35120000-1"]),
    ("T032_en", "T032", "PLT-PL-003", "BZP-PL-2024-032", "2024-12-01", "2025-05-31", 8_200_000.00, "en",
     "Modernisation and expansion of border crossing infrastructure with customs control system",
     "PL811", "Podkarpackie", ["45221000-2", "35120000-1"]),

    # T033  Hospital extension — France (FR + EN)
    ("T033_fr", "T033", "PLT-FR-004", "REF-FR-2024-033", "2024-10-10", "2025-06-30", 31_000_000.00, "fr",
     "Extension du bâtiment principal du CHU de Lyon et mise à niveau des équipements médicaux",
     "FRK22", "Rhône", ["45215140-0", "33100000-1"]),
    ("T033_en", "T033", "PLT-FR-004", "REF-FR-2024-033", "2024-10-10", "2025-06-30", 31_000_000.00, "en",
     "Extension of the main building of Lyon University Hospital and upgrade of medical equipment",
     "FRK22", "Rhône", ["45215140-0", "33100000-1"]),

    # T034  Drone inspection services — Germany (DE + EN)
    ("T034_de", "T034", "PLT-DE-004", "VgV-2024-034", "2024-11-20", "2025-02-20", 640_000.00, "de",
     "Drohnengestützte Inspektion von Brücken und Hochspannungsleitungen in Bayern",
     "DE21H", "München", ["71631000-0", "60000000-8"]),
    ("T034_en", "T034", "PLT-DE-004", "VgV-2024-034", "2024-11-20", "2025-02-20", 640_000.00, "en",
     "Drone-based inspection of bridges and high-voltage power lines in Bavaria",
     "DE21H", "München", ["71631000-0", "60000000-8"]),
]

_BATCH_3 = [
    # T035  Offshore wind farm — Sweden (SV + EN)
    ("T035_sv", "T035", "PLT-SE-001", "UH-SE-2024-035", "2025-01-10", "2025-07-31", 85_000_000.00, "sv",
     "Upphandling av havsvindkraftverk och marin infrastruktur i Östersjön",
     "SE224", "Blekinge", ["31614100-6", "45231400-9"]),
    ("T035_en", "T035", "PLT-SE-001", "UH-SE-2024-035", "2025-01-10", "2025-07-31", 85_000_000.00, "en",
     "Procurement of offshore wind turbines and marine infrastructure in the Baltic Sea",
     "SE224", "Blekinge", ["31614100-6", "45231400-9"]),

    # T036  Smart city IoT platform — Belgium (NL + EN)
    ("T036_nl", "T036", "PLT-BE-001", "BOSA-BE-2024-036", "2024-11-15", "2025-03-15", 6_200_000.00, "nl",
     "Levering van een IoT-platform voor slimme stadsmonitoring van luchtkwaliteit en verkeer",
     "BE211", "Arrondissement Antwerpen", ["48000000-8", "32441200-8"]),
    ("T036_en", "T036", "PLT-BE-001", "BOSA-BE-2024-036", "2024-11-15", "2025-03-15", 6_200_000.00, "en",
     "Supply of an IoT platform for smart city monitoring of air quality and traffic",
     "BE211", "Arrondissement Antwerpen", ["48000000-8", "32441200-8"]),

    # T037  Railway electrification — Austria (DE + EN)
    ("T037_de", "T037", "PLT-AT-001", "BBG-AT-2024-037", "2025-02-01", "2025-09-30", 42_000_000.00, "de",
     "Elektrifizierung und Modernisierung der Regionalbahnstrecke Graz–Klagenfurt",
     "AT221", "Graz", ["45234100-7", "45234115-5"]),
    ("T037_en", "T037", "PLT-AT-001", "BBG-AT-2024-037", "2025-02-01", "2025-09-30", 42_000_000.00, "en",
     "Electrification and modernisation of the Graz–Klagenfurt regional railway line",
     "AT221", "Graz", ["45234100-7", "45234115-5"]),

    # T038  Waste-to-energy plant — Hungary (HU + EN)
    ("T038_hu", "T038", "PLT-HU-001", "KH-HU-2024-038", "2024-12-10", "2025-06-10", 28_500_000.00, "hu",
     "Hulladékból energia termelő létesítmény tervezése és építése Budapest agglomerációjában",
     "HU101", "Budapest", ["45251200-3", "90513000-6"]),
    ("T038_en", "T038", "PLT-HU-001", "KH-HU-2024-038", "2024-12-10", "2025-06-10", 28_500_000.00, "en",
     "Design and construction of a waste-to-energy facility in the Budapest agglomeration",
     "HU101", "Budapest", ["45251200-3", "90513000-6"]),

    # T039  Archaeological heritage restoration — Greece (EL + EN)
    ("T039_el", "T039", "PLT-GR-001", "ESHDP-GR-2024-039", "2025-01-05", "2025-04-30", 3_800_000.00, "el",
     "Αποκατάσταση και ανάδειξη αρχαιολογικού χώρου Ολυμπίας με ψηφιακή τεκμηρίωση",
     "EL632", "Ilia", ["45212350-4", "92312000-1"]),
    ("T039_en", "T039", "PLT-GR-001", "ESHDP-GR-2024-039", "2025-01-05", "2025-04-30", 3_800_000.00, "en",
     "Restoration and promotion of the Olympia archaeological site with digital documentation",
     "EL632", "Ilia", ["45212350-4", "92312000-1"]),

    # T040  Rural broadband rollout — Finland (FI + EN)
    ("T040_fi", "T040", "PLT-FI-001", "HILMA-FI-2024-040", "2025-01-20", "2025-08-31", 18_700_000.00, "fi",
     "Laajakaistayhteyksien rakentaminen syrjäisille alueille Pohjois-Suomessa",
     "FI1D2", "Lappi", ["32562000-0", "45314300-4"]),
    ("T040_en", "T040", "PLT-FI-001", "HILMA-FI-2024-040", "2025-01-20", "2025-08-31", 18_700_000.00, "en",
     "Construction of broadband connections in remote areas of Northern Finland",
     "FI1D2", "Lappi", ["32562000-0", "45314300-4"]),

    # T041  EV charging network — Denmark (DA + EN)
    ("T041_da", "T041", "PLT-DK-001", "UHDI-DK-2024-041", "2024-11-25", "2025-02-28", 9_100_000.00, "da",
     "Etablering af landsdækkende netværk af lynladestationer til elbiler langs motorveje",
     "DK012", "Københavns omegn", ["31158000-8", "45316100-6"]),
    ("T041_en", "T041", "PLT-DK-001", "UHDI-DK-2024-041", "2024-11-25", "2025-02-28", 9_100_000.00, "en",
     "Establishment of a nationwide network of fast-charging stations for electric vehicles along motorways",
     "DK012", "Københavns omegn", ["31158000-8", "45316100-6"]),

    # T042  Public safety AI surveillance — Slovakia (SK + EN)
    ("T042_sk", "T042", "PLT-SK-001", "UVO-SK-2024-042", "2025-02-10", "2025-05-31", 4_300_000.00, "sk",
     "Dodávka a inštalácia inteligentného kamerového systému pre verejné priestranstvá Bratislavy",
     "SK010", "Bratislavský kraj", ["35120000-1", "48000000-8"]),
    ("T042_en", "T042", "PLT-SK-001", "UVO-SK-2024-042", "2025-02-10", "2025-05-31", 4_300_000.00, "en",
     "Supply and installation of an AI-powered CCTV surveillance system for Bratislava public spaces",
     "SK010", "Bratislavský kraj", ["35120000-1", "48000000-8"]),

    # T043  Green building renovation — Ireland (EN)
    ("T043_en", "T043", "PLT-IE-001", "OGP-IE-2024-043", "2025-01-15", "2025-07-15", 14_500_000.00, "en",
     "Deep energy retrofit of public sector office buildings to achieve NZEB standard in Dublin",
     "IE061", "Dublin City", ["45210000-2", "45321000-3"]),

    # T044  Agricultural research centre — Bulgaria (BG + EN)
    ("T044_bg", "T044", "PLT-BG-001", "AOP-BG-2024-044", "2025-01-01", "2025-06-01", 7_600_000.00, "bg",
     "Изграждане на научноизследователски център за прецизно земеделие и биотехнологии",
     "BG331", "Варна", ["45215000-7", "73110000-6"]),
    ("T044_en", "T044", "PLT-BG-001", "AOP-BG-2024-044", "2025-01-01", "2025-06-01", 7_600_000.00, "en",
     "Construction of a research centre for precision agriculture and biotechnology",
     "BG331", "Varna", ["45215000-7", "73110000-6"]),
]

_BATCH_4 = [
    # T045  Flood risk mapping — Netherlands (NL + EN)
    ("T045_nl", "T045", "PLT-NL-004", "TED-NL-2025-045", "2025-03-01", "2025-09-01", 5_600_000.00, "nl",
     "Ontwikkeling van een nationaal digitaal overstromingsrisicosysteem en vroegwaarschuwingsplatform",
     "NL333", "Zuid-Holland", ["72212517-6", "72300000-8"]),
    ("T045_en", "T045", "PLT-NL-004", "TED-NL-2025-045", "2025-03-01", "2025-09-01", 5_600_000.00, "en",
     "Development of a national digital flood risk mapping system and early warning platform",
     "NL333", "Zuid-Holland", ["72212517-6", "72300000-8"]),

    # T046  Smart hospital management — Italy (IT + EN)
    ("T046_it", "T046", "PLT-IT-004", "CIG-2025-046", "2025-02-15", "2025-08-15", 9_300_000.00, "it",
     "Fornitura di sistema integrato di gestione ospedaliera con intelligenza artificiale e IoT",
     "ITI43", "Roma", ["72212000-4", "33000000-0"]),
    ("T046_en", "T046", "PLT-IT-004", "CIG-2025-046", "2025-02-15", "2025-08-15", 9_300_000.00, "en",
     "Supply of an integrated hospital management system with artificial intelligence and IoT",
     "ITI43", "Roma", ["72212000-4", "33000000-0"]),

    # T047  Carbon capture and storage — Germany (DE + EN)
    ("T047_de", "T047", "PLT-DE-005", "VgV-2025-047", "2025-04-01", "2025-12-31", 67_000_000.00, "de",
     "Planung und Errichtung einer CO2-Abscheide- und Speicheranlage an einem Industriestandort im Ruhrgebiet",
     "DEA52", "Ruhr", ["45251000-9", "71320000-7"]),
    ("T047_en", "T047", "PLT-DE-005", "VgV-2025-047", "2025-04-01", "2025-12-31", 67_000_000.00, "en",
     "Planning and construction of a CO2 capture and storage facility at an industrial site in the Ruhr area",
     "DEA52", "Ruhr", ["45251000-9", "71320000-7"]),

    # T048  Social housing renovation — France (FR + EN)
    ("T048_fr", "T048", "PLT-FR-005", "REF-FR-2025-048", "2025-03-10", "2025-10-31", 24_500_000.00, "fr",
     "Rénovation thermique et mise aux normes d'accessibilité de 400 logements sociaux en Île-de-France",
     "FR101", "Paris", ["45211000-9", "45321000-3"]),
    ("T048_en", "T048", "PLT-FR-005", "REF-FR-2025-048", "2025-03-10", "2025-10-31", 24_500_000.00, "en",
     "Thermal renovation and accessibility upgrade of 400 social housing units in Île-de-France",
     "FR101", "Paris", ["45211000-9", "45321000-3"]),

    # T049  Maritime border surveillance — Greece (EL + EN)
    ("T049_el", "T049", "PLT-GR-003", "DIAVGEIA-2025-049", "2025-02-20", "2025-07-20", 11_200_000.00, "el",
     "Προμήθεια και εγκατάσταση συστήματος ολοκληρωμένης θαλάσσιας επιτήρησης στο Αιγαίο",
     "EL411", "Lesvos", ["35620000-0", "32440000-9"]),
    ("T049_en", "T049", "PLT-GR-003", "DIAVGEIA-2025-049", "2025-02-20", "2025-07-20", 11_200_000.00, "en",
     "Supply and installation of an integrated maritime surveillance system in the Aegean Sea",
     "EL411", "Lesvos", ["35620000-0", "32440000-9"]),

    # T050  Railway bridge reconstruction — Poland (PL + EN)
    ("T050_pl", "T050", "PLT-PL-004", "BZP-PL-2025-050", "2025-05-01", "2026-03-31", 38_000_000.00, "pl",
     "Przebudowa i wzmocnienie mostów kolejowych na linii E30 Kraków–Rzeszów",
     "PL213", "Kraków", ["45221100-3", "45234100-7"]),
    ("T050_en", "T050", "PLT-PL-004", "BZP-PL-2025-050", "2025-05-01", "2026-03-31", 38_000_000.00, "en",
     "Reconstruction and reinforcement of railway bridges on the E30 line Kraków–Rzeszów",
     "PL213", "Kraków", ["45221100-3", "45234100-7"]),

    # T051  Clean energy microgrid — Spain (ES + EN)
    ("T051_es", "T051", "PLT-ES-005", "BOE-2025-051", "2025-03-15", "2025-11-15", 16_800_000.00, "es",
     "Diseño e instalación de microrredes de energía renovable con almacenamiento para municipios rurales de Castilla-La Mancha",
     "ES422", "Cuenca", ["09331200-0", "31213000-2"]),
    ("T051_en", "T051", "PLT-ES-005", "BOE-2025-051", "2025-03-15", "2025-11-15", 16_800_000.00, "en",
     "Design and installation of renewable energy microgrids with storage for rural municipalities in Castilla-La Mancha",
     "ES422", "Cuenca", ["09331200-0", "31213000-2"]),

    # T052  National digital identity platform — Czech Republic (CS + EN)
    ("T052_cs", "T052", "PLT-CZ-003", "ISVZ-CZ-2025-052", "2025-04-01", "2025-10-01", 7_900_000.00, "cs",
     "Vývoj a provoz národní platformy pro digitální identitu a elektronické podpisy občanů",
     "CZ010", "Praha", ["72212517-6", "72300000-8"]),
    ("T052_en", "T052", "PLT-CZ-003", "ISVZ-CZ-2025-052", "2025-04-01", "2025-10-01", 7_900_000.00, "en",
     "Development and operation of a national platform for digital identity and electronic signatures",
     "CZ010", "Praha", ["72212517-6", "72300000-8"]),

    # T053  Forest fire prevention — Portugal (PT + EN)
    ("T053_pt", "T053", "PLT-PT-003", "BASE-PT-2025-053", "2025-03-20", "2025-09-20", 13_400_000.00, "pt",
     "Implementação de sistema integrado de deteção e combate a incêndios florestais no Alentejo",
     "PT185", "Alentejo", ["35111000-5", "32441200-8"]),
    ("T053_en", "T053", "PLT-PT-003", "BASE-PT-2025-053", "2025-03-20", "2025-09-20", 13_400_000.00, "en",
     "Implementation of an integrated forest fire detection and response system in Alentejo",
     "PT185", "Alentejo", ["35111000-5", "32441200-8"]),

    # T054  E-government citizen portal — Romania (RO + EN)
    ("T054_ro", "T054", "PLT-RO-003", "SEAP-RO-2025-054", "2025-02-28", "2025-08-31", 6_100_000.00, "ro",
     "Dezvoltarea portalului național de servicii electronice pentru cetățeni și mediul de afaceri",
     "RO321", "Ilfov", ["72212517-6", "72300000-8"]),
    ("T054_en", "T054", "PLT-RO-003", "SEAP-RO-2025-054", "2025-02-28", "2025-08-31", 6_100_000.00, "en",
     "Development of the national e-government services portal for citizens and businesses",
     "RO321", "Ilfov", ["72212517-6", "72300000-8"]),
]

_BATCH_5 = [
    # T055  Smart port logistics — Lithuania (LT + EN)
    ("T055_lt", "T055", "PLT-LT-001", "CVP-LT-2025-055", "2025-04-01", "2025-10-01", 14_200_000.00, "lt",
     "Klaipedos juriu uosto logistikos centro modernizavimas ir skaitmenines valdymo sistemos diegimas",
     "LT022", "Klaipedos apskritis", ["45241000-8", "72212517-6"]),
    ("T055_en", "T055", "PLT-LT-001", "CVP-LT-2025-055", "2025-04-01", "2025-10-01", 14_200_000.00, "en",
     "Modernisation of Klaipeda seaport logistics centre and deployment of digital management system",
     "LT022", "Klaipedos apskritis", ["45241000-8", "72212517-6"]),

    # T056  Passenger terminal — Latvia (LV + EN)
    ("T056_lv", "T056", "PLT-LV-001", "IUB-LV-2025-056", "2025-03-15", "2026-01-15", 19_800_000.00, "lv",
     "Rigas pasazieru ostas jauna terminala buvnieciba un satiksmes infrastrukturas modernizacija",
     "LV006", "Riga", ["45241000-8", "45200000-9"]),
    ("T056_en", "T056", "PLT-LV-001", "IUB-LV-2025-056", "2025-03-15", "2026-01-15", 19_800_000.00, "en",
     "Construction of new Riga passenger port terminal and modernisation of transport infrastructure",
     "LV006", "Riga", ["45241000-8", "45200000-9"]),

    # T057  Digital identity infrastructure — Estonia (ET + EN)
    ("T057_et", "T057", "PLT-EE-001", "RIK-EE-2025-057", "2025-05-01", "2025-12-31", 8_400_000.00, "et",
     "Riikliku digitaalse identiteedi ja e-residentsuse platvormi laiendamine ning turvalisuse tugevdamine",
     "EE001", "Pohja-Eesti", ["72212517-6", "72220000-9"]),
    ("T057_en", "T057", "PLT-EE-001", "RIK-EE-2025-057", "2025-05-01", "2025-12-31", 8_400_000.00, "en",
     "Expansion and security hardening of national digital identity and e-residency platform",
     "EE001", "Pohja-Eesti", ["72212517-6", "72220000-9"]),

    # T058  Alpine tourism infrastructure — Slovenia (SL + EN)
    ("T058_sl", "T058", "PLT-SI-001", "JAVNE-SI-2025-058", "2025-04-15", "2025-11-30", 11_500_000.00, "sl",
     "Posodobitev turisticne in transportne infrastrukture v gorski regiji Kranjska Gora",
     "SI042", "Gorenjska", ["45200000-9", "45233120-6"]),
    ("T058_en", "T058", "PLT-SI-001", "JAVNE-SI-2025-058", "2025-04-15", "2025-11-30", 11_500_000.00, "en",
     "Upgrade of tourism and transport infrastructure in the Kranjska Gora mountain region",
     "SI042", "Gorenjska", ["45200000-9", "45233120-6"]),

    # T059  Coastal water supply — Croatia (HR + EN)
    ("T059_hr", "T059", "PLT-HR-001", "EOJN-HR-2025-059", "2025-06-01", "2026-04-30", 23_600_000.00, "hr",
     "Izgradnja regionalnog sustava opskrbe pitkom vodom za dalmatinsko zaobalje i otoke",
     "HR035", "Splitsko-dalmatinska", ["45231300-8", "45232150-8"]),
    ("T059_en", "T059", "PLT-HR-001", "EOJN-HR-2025-059", "2025-06-01", "2026-04-30", 23_600_000.00, "en",
     "Construction of a regional drinking water supply system for the Dalmatian hinterland and islands",
     "HR035", "Splitsko-dalmatinska", ["45231300-8", "45232150-8"]),

    # T060  Secure government data centre — Luxembourg (FR + EN)
    ("T060_fr", "T060", "PLT-LU-001", "MPF-LU-2025-060", "2025-05-15", "2026-02-28", 31_000_000.00, "fr",
     "Construction d'un centre de donnees gouvernemental securise et certifie Tier IV au Luxembourg",
     "LU000", "Luxembourg", ["45213141-4", "72212517-6"]),
    ("T060_en", "T060", "PLT-LU-001", "MPF-LU-2025-060", "2025-05-15", "2026-02-28", 31_000_000.00, "en",
     "Construction of a Tier IV certified secure government data centre in Luxembourg",
     "LU000", "Luxembourg", ["45213141-4", "72212517-6"]),

    # T061  Solar and battery park — Malta (MT + EN)
    ("T061_mt", "T061", "PLT-MT-001", "GDP-MT-2025-061", "2025-04-01", "2025-12-31", 9_700_000.00, "mt",
     "Zvilupp ta' park solari u sistema ta' hzin tal-batteriji biex jintlahaq l-objettiv ta' 70% energija rinnovabbli",
     "MT001", "Malta", ["09331200-0", "31213000-2"]),
    ("T061_en", "T061", "PLT-MT-001", "GDP-MT-2025-061", "2025-04-01", "2025-12-31", 9_700_000.00, "en",
     "Development of solar park and battery storage system to achieve 70% renewable energy target",
     "MT001", "Malta", ["09331200-0", "31213000-2"]),

    # T062  Seawater desalination plant — Cyprus (EL + EN)
    ("T062_el", "T062", "PLT-CY-001", "SPPD-CY-2025-062", "2025-06-01", "2026-06-30", 44_000_000.00, "el",
     "Kataskevi neas monadaas afalatosis thalassinou nerou upsilis energeiakas apodosis sti Lemeso",
     "CY000", "Cyprus", ["45252120-5", "45231300-8"]),
    ("T062_en", "T062", "PLT-CY-001", "SPPD-CY-2025-062", "2025-06-01", "2026-06-30", 44_000_000.00, "en",
     "Construction of a new high-efficiency seawater desalination plant in Limassol",
     "CY000", "Cyprus", ["45252120-5", "45231300-8"]),

    # T063  Metro line extension — Hungary (HU + EN)
    ("T063_hu", "T063", "PLT-HU-002", "KH-HU-2025-063", "2025-07-01", "2027-12-31", 310_000_000.00, "hu",
     "Budapest metrohalozat M3 vonalanak felujitasa es M4 vonal meghosszabbitasa Kelenföldig",
     "HU110", "Budapest", ["45234121-7", "45234100-7"]),
    ("T063_en", "T063", "PLT-HU-002", "KH-HU-2025-063", "2025-07-01", "2027-12-31", 310_000_000.00, "en",
     "Renovation of Budapest metro line M3 and extension of M4 line to Kelenföld",
     "HU110", "Budapest", ["45234121-7", "45234100-7"]),

    # T064  Airport terminal expansion — Bulgaria (BG + EN)
    ("T064_bg", "T064", "PLT-BG-002", "AOP-BG-2025-064", "2025-05-01", "2027-04-30", 156_000_000.00, "bg",
     "Izgrazhdane na nov terminal 3 na Mezhdunarodno letishte Sofia i razshiryavane na pistovsata sistema",
     "BG411", "Sofia-Stolitsa", ["45213330-7", "45235000-3"]),
    ("T064_en", "T064", "PLT-BG-002", "AOP-BG-2025-064", "2025-05-01", "2027-04-30", 156_000_000.00, "en",
     "Construction of new Terminal 3 at Sofia International Airport and expansion of runway system",
     "BG411", "Sofia-Stolitsa", ["45213330-7", "45235000-3"]),

    # T065  Hyperscale data centre campus — Ireland (EN only)
    ("T065_en", "T065", "PLT-IE-002", "OGP-IE-2025-065", "2025-04-10", "2026-10-31", 420_000_000.00, "en",
     "Development of hyperscale data centre campus with on-site renewable energy supply in County Meath",
     "IE012", "Leinster", ["45213141-4", "09331200-0"]),

    # T066  Green hydrogen production — Denmark (DA + EN)
    ("T066_da", "T066", "PLT-DK-002", "UHDI-DK-2025-066", "2025-06-01", "2026-12-31", 78_000_000.00, "da",
     "Etablering af storskala groent brintproduktionsanlaeg og distributionsinfrastruktur ved Esbjerg havn",
     "DK053", "Sydjylland", ["09123000-7", "45251100-6"]),
    ("T066_en", "T066", "PLT-DK-002", "UHDI-DK-2025-066", "2025-06-01", "2026-12-31", 78_000_000.00, "en",
     "Establishment of large-scale green hydrogen production facility and distribution infrastructure at Esbjerg port",
     "DK053", "Sydjylland", ["09123000-7", "45251100-6"]),

    # T067  High-speed rail — Sweden (SV + EN)
    ("T067_sv", "T067", "PLT-SE-003", "TRV-SE-2025-067", "2025-08-01", "2027-06-30", 520_000_000.00, "sv",
     "Projektering och byggande av nya stambanor for hoghastighetstag mellan Stockholm och Goteborg",
     "SE110", "Stockholms lan", ["45234100-7", "45234115-5"]),
    ("T067_en", "T067", "PLT-SE-003", "TRV-SE-2025-067", "2025-08-01", "2027-06-30", 520_000_000.00, "en",
     "Design and construction of new main lines for high-speed trains between Stockholm and Gothenburg",
     "SE110", "Stockholms lan", ["45234100-7", "45234115-5"]),

    # T068  Nuclear waste repository — Finland (FI + EN)
    ("T068_fi", "T068", "PLT-FI-002", "HILMA-FI-2025-068", "2025-09-01", "2026-06-30", 94_000_000.00, "fi",
     "Loppusijoitustunnelin louhintatyot ja geotekninen tuki Olkiluodon ydinpolttoaineen loppusijoituslaitoksessa",
     "FI196", "Satakunta", ["45251100-6", "45262000-1"]),
    ("T068_en", "T068", "PLT-FI-002", "HILMA-FI-2025-068", "2025-09-01", "2026-06-30", 94_000_000.00, "en",
     "Final disposal tunnel excavation and geotechnical support at Olkiluoto nuclear fuel repository",
     "FI196", "Satakunta", ["45251100-6", "45262000-1"]),

    # T069  LNG terminal expansion — Poland (PL + EN)
    ("T069_pl", "T069", "PLT-PL-005", "BZP-PL-2025-069", "2025-07-01", "2027-09-30", 240_000_000.00, "pl",
     "Rozbudowa terminala LNG w Swinoujsciu o nowy zbiornik kriogeniczny i nabrzeze rozladunkowe",
     "PL424", "Miasto Szczecin", ["45251000-9", "45241000-8"]),
    ("T069_en", "T069", "PLT-PL-005", "BZP-PL-2025-069", "2025-07-01", "2027-09-30", 240_000_000.00, "en",
     "Expansion of Swinoujscie LNG terminal with new cryogenic storage tank and unloading berth",
     "PL424", "Miasto Szczecin", ["45251000-9", "45241000-8"]),

    # T070  Danube flood protection — Romania (RO + EN)
    ("T070_ro", "T070", "PLT-RO-004", "SEAP-RO-2025-070", "2025-05-15", "2027-03-31", 67_500_000.00, "ro",
     "Reabilitarea si consolidarea sistemului de aparare impotriva inundatiilor in zona luncii Dunarii",
     "RO222", "Galati", ["45246000-3", "45247200-4"]),
    ("T070_en", "T070", "PLT-RO-004", "SEAP-RO-2025-070", "2025-05-15", "2027-03-31", 67_500_000.00, "en",
     "Rehabilitation and reinforcement of flood defence system in the Danube floodplain zone",
     "RO222", "Galati", ["45246000-3", "45247200-4"]),

    # T071  Metro line D — Czech Republic (CS + EN)
    ("T071_cs", "T071", "PLT-CZ-004", "ISVZ-CZ-2025-071", "2025-06-15", "2028-12-31", 480_000_000.00, "cs",
     "Vystavba nove linky metra D v Praze — usek Pankrac–Olbrachtova s tunelovanim a stanicemi",
     "CZ010", "Praha", ["45234121-7", "45262000-1"]),
    ("T071_en", "T071", "PLT-CZ-004", "ISVZ-CZ-2025-071", "2025-06-15", "2028-12-31", 480_000_000.00, "en",
     "Construction of new Prague metro line D -- Pankrac to Olbrachtova section with tunnelling and stations",
     "CZ010", "Praha", ["45234121-7", "45262000-1"]),

    # T072  Electric vehicle technology park — Slovakia (SK + EN)
    ("T072_sk", "T072", "PLT-SK-002", "UVO-SK-2025-072", "2025-04-20", "2026-07-31", 34_000_000.00, "sk",
     "Vystavba priemyselneho parku pre elektromobilitu a vyskum batériovych technologii v Trnave",
     "SK021", "Trnavsky kraj", ["45213150-9", "73110000-6"]),
    ("T072_en", "T072", "PLT-SK-002", "UVO-SK-2025-072", "2025-04-20", "2026-07-31", 34_000_000.00, "en",
     "Construction of industrial park for electric mobility and battery technology research in Trnava",
     "SK021", "Trnavsky kraj", ["45213150-9", "73110000-6"]),

    # T073  Alpine motorway bridges — Austria (DE + EN)
    ("T073_de", "T073", "PLT-AT-002", "BBG-AT-2025-073", "2025-05-01", "2027-08-31", 88_000_000.00, "de",
     "Sanierung und Ertüchtigung der Autobahnbrücken auf der A10 Tauernautobahn im Pinzgauer Abschnitt",
     "AT323", "Salzburg und Umgebung", ["45221000-2", "45221100-3"]),
    ("T073_en", "T073", "PLT-AT-002", "BBG-AT-2025-073", "2025-05-01", "2027-08-31", 88_000_000.00, "en",
     "Renovation and strengthening of motorway bridges on the A10 Tauern motorway in the Pinzgau section",
     "AT323", "Salzburg und Umgebung", ["45221000-2", "45221100-3"]),

    # T074  Canary Islands renewable energy — Spain (EN only)
    ("T074_en", "T074", "PLT-ES-006", "BOE-2025-074", "2025-05-15", "2026-11-30", 52_000_000.00, "en",
     "Construction of integrated wind and solar energy plant with grid storage for the Canary Islands energy transition",
     "ES705", "Las Palmas", ["09331200-0", "31614100-6"]),

    # T075  Ocean wave energy park — Portugal (PT + EN)
    ("T075_pt", "T075", "PLT-PT-004", "BASE-PT-2025-075", "2025-06-01", "2026-08-31", 26_000_000.00, "pt",
     "Instalacao de parque de energia undomotriz e infraestrutura de transmissao eletrica submarina nos Acores",
     "PT200", "Regiao Autonoma dos Acores", ["31614100-6", "45231400-9"]),
    ("T075_en", "T075", "PLT-PT-004", "BASE-PT-2025-075", "2025-06-01", "2026-08-31", 26_000_000.00, "en",
     "Installation of wave energy park and subsea electricity transmission infrastructure in the Azores",
     "PT200", "Regiao Autonoma dos Acores", ["31614100-6", "45231400-9"]),

    # T076  Rural ultra-broadband — Italy (IT + EN)
    ("T076_it", "T076", "PLT-IT-005", "ANAC-IT-2025-076", "2025-05-10", "2026-09-30", 37_000_000.00, "it",
     "Infrastruttura a banda ultra-larga per le aree rurali e montane della Sicilia interna",
     "ITG11", "Palermo", ["32562000-0", "45314300-4"]),
    ("T076_en", "T076", "PLT-IT-005", "ANAC-IT-2025-076", "2025-05-10", "2026-09-30", 37_000_000.00, "en",
     "Ultra-broadband infrastructure for rural and mountain areas of inland Sicily",
     "ITG11", "Palermo", ["32562000-0", "45314300-4"]),

    # T077  Nuclear plant maintenance — France (FR + EN)
    ("T077_fr", "T077", "PLT-FR-006", "BOAMP-FR-2025-077", "2025-07-01", "2026-12-31", 115_000_000.00, "fr",
     "Travaux de maintenance et de grand carenage de la centrale nucleaire de Flamanville en Normandie",
     "FRD11", "Calvados", ["45251100-6", "45251000-9"]),
    ("T077_en", "T077", "PLT-FR-006", "BOAMP-FR-2025-077", "2025-07-01", "2026-12-31", 115_000_000.00, "en",
     "Maintenance and major overhaul works at Flamanville nuclear power plant in Normandy",
     "FRD11", "Calvados", ["45251100-6", "45251000-9"]),

    # T078  Green hydrogen pipeline — Germany (DE + EN)
    ("T078_de", "T078", "PLT-DE-006", "VgV-2025-078", "2025-08-01", "2027-06-30", 193_000_000.00, "de",
     "Planung und Bau des ersten deutschen Fernleitungsnetzes für grünen Wasserstoff zwischen Hamburg und dem Ruhrgebiet",
     "DE600", "Hamburg", ["45231000-5", "09123000-7"]),
    ("T078_en", "T078", "PLT-DE-006", "VgV-2025-078", "2025-08-01", "2027-06-30", 193_000_000.00, "en",
     "Planning and construction of Germany's first long-distance green hydrogen pipeline between Hamburg and the Ruhr area",
     "DE600", "Hamburg", ["45231000-5", "09123000-7"]),

    # T079  Sea-level rise protection — Netherlands (NL + EN)
    ("T079_nl", "T079", "PLT-NL-005", "PIANOO-NL-2025-079", "2025-09-01", "2028-12-31", 340_000_000.00, "nl",
     "Versterking en innovatieve aanpassing van de zeewaterkering langs de Zeeuwse Delta voor zeespiegelstijging",
     "NL346", "Zeeland", ["45246400-7", "45246200-5"]),
    ("T079_en", "T079", "PLT-NL-005", "PIANOO-NL-2025-079", "2025-09-01", "2028-12-31", 340_000_000.00, "en",
     "Reinforcement and adaptive upgrade of sea level defences along the Zeeland Delta against rising sea levels",
     "NL346", "Zeeland", ["45246400-7", "45246200-5"]),

    # T080  Satellite ground station — Belgium (FR + EN)
    ("T080_fr", "T080", "PLT-BE-002", "BOSA-BE-2025-080", "2025-06-15", "2026-08-31", 18_500_000.00, "fr",
     "Construction et equipement d'une station sol pour satellites d'observation terrestre et telecommunications",
     "BE335", "Province de Luxembourg", ["32441200-8", "45213141-4"]),
    ("T080_en", "T080", "PLT-BE-002", "BOSA-BE-2025-080", "2025-06-15", "2026-08-31", 18_500_000.00, "en",
     "Construction and equipping of a ground station for Earth observation and telecommunications satellites",
     "BE335", "Province de Luxembourg", ["32441200-8", "45213141-4"]),
]
# fmt: on

_BATCHES = {
    "1": _BATCH_1,
    "2": _BATCH_2,
    "3": _BATCH_3,
    "4": _BATCH_4,
    "5": _BATCH_5,
}


class Command(BaseCommand):
    help = "Insert demo tenders (T021-T080) into tender_translations_demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            choices=["1", "2", "3", "4", "5", "all"],
            default="all",
            help="Which batch to insert: 1 (T021-T026), 2 (T027-T034), 3 (T035-T044), 4 (T045-T054), 5 (T055-T080), all (default).",
        )
        parser.add_argument(
            "--list", action="store_true",
            help="Print the rows that would be inserted without writing to the DB.",
        )

    def handle(self, *args, **options):
        batch_key = options["batch"]
        if batch_key == "all":
            rows = _BATCH_1 + _BATCH_2 + _BATCH_3 + _BATCH_4 + _BATCH_5
            label = "all (T021-T080)"
        else:
            rows = _BATCHES[batch_key]
            ranges = {"1": "T021-T026", "2": "T027-T034", "3": "T035-T044", "4": "T045-T054", "5": "T055-T080"}
            label = f"batch {batch_key} ({ranges[batch_key]})"

        if options["list"]:
            self.stdout.write(f"Would insert/update {len(rows)} rows ({label}):")
            for row in rows:
                self.stdout.write(f"  {row[0]:15s}  {row[8][:70]}")
            return

        with get_connection() as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.executemany(_INSERT, rows)
                affected = cur.rowcount
            conn.commit()

        logger.info("insert_demo_tenders.done", batch=batch_key, rows=len(rows), affected=affected)
        self.stdout.write(
            self.style.SUCCESS(
                f"Inserted/updated {affected} rows ({label}).\n"
                f"Auto-sync will pick them up within 10s — watch the Pipeline page."
            )
        )
