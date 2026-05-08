"""
One-shot demo setup command.

Usage:
  python manage.py setup_demo                        # create PG table + seed + Milvus collection
  python manage.py setup_demo --step pg              # PostgreSQL only
  python manage.py setup_demo --step milvus          # Milvus only
  python manage.py setup_demo --recreate-pg          # drop and recreate PG table + reseed
  python manage.py setup_demo --step milvus --recreate  # drop and recreate Milvus collection
"""
import psycopg2
from django.conf import settings
from django.core.management.base import BaseCommand
from milvussync.logging import get_logger
from sync.postgres.connection import get_connection
from sync.tc_milvus.tender_search_client import TenderSearchMilvusClient

logger = get_logger(__name__)

_DROP_TABLE = "DROP TABLE IF EXISTS tender_translations_demo"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tender_translations_demo (
    pk                  VARCHAR(256) PRIMARY KEY,
    tender_id           VARCHAR(64)  NOT NULL,
    platform_id         VARCHAR(256),
    tender_national_id  VARCHAR(256),
    publication_date    DATE,
    closing_date        DATE,
    estimated_total_value FLOAT,
    language_code       VARCHAR(8)   NOT NULL,
    title               TEXT         NOT NULL,
    nut_code            VARCHAR(32),
    nut_label           VARCHAR(256),
    cpv_codes           TEXT[]       DEFAULT '{}',
    created_at          TIMESTAMPTZ  DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ttd_updated_at ON tender_translations_demo(updated_at);
CREATE INDEX IF NOT EXISTS idx_ttd_tender_id  ON tender_translations_demo(tender_id);
"""

# Each tuple:
# (pk, tender_id, platform_id, tender_national_id, publication_date, closing_date,
#  estimated_total_value, language_code, title, nut_code, nut_label, cpv_codes)
_SEED_ROWS = [
    # ── T001  Road construction — Italy (EN + IT) ────────────────────────────
    ("T001_en", "T001", "PLT-IT-001", "CIG-2024-001", "2024-01-15", "2024-03-31", 500_000.00, "en",
     "Road construction and maintenance works in the downtown district",
     "ITC1", "Piemonte", ["45233120-6", "45000000-7"]),
    ("T001_it", "T001", "PLT-IT-001", "CIG-2024-001", "2024-01-15", "2024-03-31", 500_000.00, "it",
     "Lavori di costruzione e manutenzione stradale nel distretto del centro",
     "ITC1", "Piemonte", ["45233120-6", "45000000-7"]),

    # ── T002  IT hardware & software — France (FR + EN) ─────────────────────
    ("T002_fr", "T002", "PLT-FR-001", "REF-FR-2024-002", "2024-02-01", "2024-04-15", 250_000.00, "fr",
     "Fourniture de matériel informatique et de logiciels pour les services administratifs",
     "FR101", "Île-de-France", ["30213000-5", "48000000-8"]),
    ("T002_en", "T002", "PLT-FR-001", "REF-FR-2024-002", "2024-02-01", "2024-04-15", 250_000.00, "en",
     "Supply of computer hardware and software for administrative services",
     "FR101", "Île-de-France", ["30213000-5", "48000000-8"]),

    # ── T003  Medical diagnostic equipment — UK + Italy (EN + IT) ───────────
    ("T003_en", "T003", "PLT-UK-001", "OJEU-2024-003", "2024-03-01", "2024-05-30", 1_200_000.00, "en",
     "Supply and maintenance of medical diagnostic equipment for public hospitals",
     "UKI3", "Inner London", ["33111000-1", "50400000-9"]),
    ("T003_it", "T003", "PLT-UK-001", "OJEU-2024-003", "2024-03-01", "2024-05-30", 1_200_000.00, "it",
     "Fornitura e manutenzione di apparecchiature diagnostiche mediche per ospedali pubblici",
     "ITC4", "Lombardia", ["33111000-1", "50400000-9"]),

    # ── T004  Digital transformation consulting — Spain (ES + EN) ───────────
    ("T004_es", "T004", "PLT-ES-001", "BOE-2024-004", "2024-04-01", "2024-06-30", 750_000.00, "es",
     "Servicios de consultoría para la transformación digital e implementación de sistemas cloud",
     "ES300", "Comunidad de Madrid", ["72000000-5", "72267100-0"]),
    ("T004_en", "T004", "PLT-ES-001", "BOE-2024-004", "2024-04-01", "2024-06-30", 750_000.00, "en",
     "Digital transformation consulting and cloud systems implementation services",
     "ES300", "Comunidad de Madrid", ["72000000-5", "72267100-0"]),

    # ── T005  Environmental assessment — Germany (EN + DE) ───────────────────
    ("T005_en", "T005", "PLT-DE-001", "VgV-2024-005", "2024-05-01", "2024-07-31", 380_000.00, "en",
     "Environmental impact assessment and waste management services for industrial facilities",
     "DEA2", "Köln", ["90710000-7", "90500000-2"]),
    ("T005_de", "T005", "PLT-DE-001", "VgV-2024-005", "2024-05-01", "2024-07-31", 380_000.00, "de",
     "Umweltverträglichkeitsprüfung und Abfallentsorgungsdienste für Industrieanlagen",
     "DEA2", "Köln", ["90710000-7", "90500000-2"]),

    # ── T006  Bridge rehabilitation — Poland (PL + EN) ───────────────────────
    ("T006_pl", "T006", "PLT-PL-001", "PZP-2024-006", "2024-01-20", "2024-04-20", 2_800_000.00, "pl",
     "Remont i modernizacja mostu drogowego nad rzeką Wisłą wraz z infrastrukturą towarzyszącą",
     "PL911", "Mazowieckie", ["45221111-3", "45233000-9"]),
    ("T006_en", "T006", "PLT-PL-001", "PZP-2024-006", "2024-01-20", "2024-04-20", 2_800_000.00, "en",
     "Rehabilitation and modernisation of road bridge over the Vistula river and ancillary infrastructure",
     "PL911", "Mazowieckie", ["45221111-3", "45233000-9"]),

    # ── T007  Security services — Netherlands (NL + EN) ─────────────────────
    ("T007_nl", "T007", "PLT-NL-001", "TED-NL-2024-007", "2024-02-10", "2024-04-30", 420_000.00, "nl",
     "Beveiligingsdiensten voor overheidsgebouwen en publieke ruimtes in Amsterdam",
     "NL329", "Groot-Amsterdam", ["79710000-4", "79711000-1"]),
    ("T007_en", "T007", "PLT-NL-001", "TED-NL-2024-007", "2024-02-10", "2024-04-30", 420_000.00, "en",
     "Security guard and surveillance services for government buildings and public spaces in Amsterdam",
     "NL329", "Groot-Amsterdam", ["79710000-4", "79711000-1"]),

    # ── T008  School renovation — Portugal (PT + EN) ─────────────────────────
    ("T008_pt", "T008", "PLT-PT-001", "BASE-PT-2024-008", "2024-03-05", "2024-05-15", 650_000.00, "pt",
     "Reabilitação e ampliação de estabelecimentos de ensino público no município de Lisboa",
     "PT170", "Área Metropolitana de Lisboa", ["45214200-2", "45000000-7"]),
    ("T008_en", "T008", "PLT-PT-001", "BASE-PT-2024-008", "2024-03-05", "2024-05-15", 650_000.00, "en",
     "Rehabilitation and extension of public school buildings in the municipality of Lisbon",
     "PT170", "Área Metropolitana de Lisboa", ["45214200-2", "45000000-7"]),

    # ── T009  Water treatment plant — Romania (RO + EN) ──────────────────────
    ("T009_ro", "T009", "PLT-RO-001", "SICAP-2024-009", "2024-04-10", "2024-07-10", 4_500_000.00, "ro",
     "Construcție și echipare stație de tratare a apei potabile pentru județul Cluj",
     "RO113", "Cluj", ["45252100-9", "65100000-4"]),
    ("T009_en", "T009", "PLT-RO-001", "SICAP-2024-009", "2024-04-10", "2024-07-10", 4_500_000.00, "en",
     "Construction and equipping of drinking water treatment plant for Cluj county",
     "RO113", "Cluj", ["45252100-9", "65100000-4"]),

    # ── T010  Public transport fleet — Czech Republic (CS + EN) ──────────────
    ("T010_cs", "T010", "PLT-CZ-001", "UOHS-2024-010", "2024-02-15", "2024-05-01", 8_200_000.00, "cs",
     "Dodávka nízkoemisních autobusů pro městskou hromadnou dopravu v Brně",
     "CZ064", "Jihomoravský kraj", ["34121100-2", "60112000-6"]),
    ("T010_en", "T010", "PLT-CZ-001", "UOHS-2024-010", "2024-02-15", "2024-05-01", 8_200_000.00, "en",
     "Supply of low-emission buses for urban public transport in Brno",
     "CZ064", "Jihomoravský kraj", ["34121100-2", "60112000-6"]),

    # ── T011  Cybersecurity audit — Belgium (FR + EN) ────────────────────────
    ("T011_fr", "T011", "PLT-BE-001", "BULL-BE-2024-011", "2024-03-12", "2024-05-20", 180_000.00, "fr",
     "Audit de cybersécurité et tests de pénétration pour les systèmes d'information fédéraux",
     "BE100", "Région de Bruxelles-Capitale", ["72315100-7", "72225000-8"]),
    ("T011_en", "T011", "PLT-BE-001", "BULL-BE-2024-011", "2024-03-12", "2024-05-20", 180_000.00, "en",
     "Cybersecurity audit and penetration testing for federal information systems",
     "BE100", "Région de Bruxelles-Capitale", ["72315100-7", "72225000-8"]),

    # ── T012  Renewable energy park — Sweden (EN only) ───────────────────────
    ("T012_en", "T012", "PLT-SE-001", "KKV-2024-012", "2024-05-10", "2024-08-10", 12_000_000.00, "en",
     "Design, construction and commissioning of onshore wind energy park in northern Sweden",
     "SE332", "Västernorrland", ["45231221-0", "09310000-5"]),

    # ── T013  Ambulance services — Austria (DE + EN) ─────────────────────────
    ("T013_de", "T013", "PLT-AT-001", "BVA-AT-2024-013", "2024-01-25", "2024-03-25", 3_600_000.00, "de",
     "Betrieb von Rettungs- und Krankentransportdiensten für den Bezirk Wien-Umgebung",
     "AT130", "Wien", ["85143000-3", "85111500-0"]),
    ("T013_en", "T013", "PLT-AT-001", "BVA-AT-2024-013", "2024-01-25", "2024-03-25", 3_600_000.00, "en",
     "Operation of emergency ambulance and patient transport services for the Vienna district",
     "AT130", "Wien", ["85143000-3", "85111500-0"]),

    # ── T014  Legal advisory services — Greece (EN only) ─────────────────────
    ("T014_en", "T014", "PLT-GR-001", "DIAVGEIA-2024-014", "2024-04-20", "2024-06-20", 95_000.00, "en",
     "Legal advisory services for public procurement and EU state-aid compliance",
     "EL301", "Attiki", ["79111000-5", "79100000-5"]),

    # ── T015  Hospital canteen catering — Italy (IT + EN) ────────────────────
    ("T015_it", "T015", "PLT-IT-002", "CIG-2024-015", "2024-06-01", "2024-08-31", 920_000.00, "it",
     "Servizio di ristorazione collettiva per le mense ospedaliere della ASL Napoli 1",
     "ITF33", "Napoli", ["55523100-3", "55511000-5"]),
    ("T015_en", "T015", "PLT-IT-002", "CIG-2024-015", "2024-06-01", "2024-08-31", 920_000.00, "en",
     "Collective catering service for hospital canteens of ASL Napoli 1",
     "ITF33", "Napoli", ["55523100-3", "55511000-5"]),

    # ── T016  Broadband network rollout — Germany (DE + EN) ──────────────────
    ("T016_de", "T016", "PLT-DE-002", "VgV-2024-016", "2024-05-15", "2024-09-01", 6_750_000.00, "de",
     "Ausbau und Betrieb eines Glasfaser-Breitbandnetzes im ländlichen Raum Bayern",
     "DE21H", "Miesbach", ["32571000-6", "45314320-0"]),
    ("T016_en", "T016", "PLT-DE-002", "VgV-2024-016", "2024-05-15", "2024-09-01", 6_750_000.00, "en",
     "Rollout and operation of fibre-optic broadband network in rural Bavaria",
     "DE21H", "Miesbach", ["32571000-6", "45314320-0"]),

    # ── T017  Archive digitisation — France (FR only) ────────────────────────
    ("T017_fr", "T017", "PLT-FR-002", "REF-FR-2024-017", "2024-03-18", "2024-05-18", 140_000.00, "fr",
     "Numérisation et indexation des archives historiques des collectivités locales du Var",
     "FRL05", "Var", ["79995100-6", "72320000-4"]),

    # ── T018  Smart city traffic management — Spain (ES + EN) ────────────────
    ("T018_es", "T018", "PLT-ES-002", "BOE-2024-018", "2024-06-10", "2024-09-30", 2_100_000.00, "es",
     "Sistema inteligente de gestión del tráfico urbano con sensores IoT para Barcelona",
     "ES511", "Barcelona", ["34970000-7", "72000000-5"]),
    ("T018_en", "T018", "PLT-ES-002", "BOE-2024-018", "2024-06-10", "2024-09-30", 2_100_000.00, "en",
     "Smart urban traffic management system with IoT sensors for the city of Barcelona",
     "ES511", "Barcelona", ["34970000-7", "72000000-5"]),

    # ── T019  Park and green-space maintenance — Netherlands (NL only) ───────
    ("T019_nl", "T019", "PLT-NL-002", "TED-NL-2024-019", "2024-02-28", "2024-04-28", 310_000.00, "nl",
     "Onderhoud van openbaar groen, parken en plantsoenen in de gemeente Rotterdam",
     "NL33A", "Groot-Rijnmond", ["77310000-6", "90610000-6"]),

    # ── T020  Waste water infrastructure — Poland (PL + EN) ──────────────────
    ("T020_pl", "T020", "PLT-PL-002", "PZP-2024-020", "2024-07-01", "2024-11-30", 9_400_000.00, "pl",
     "Budowa kanalizacji sanitarnej i oczyszczalni ścieków dla gminy Kraków-Zachód",
     "PL213", "Miasto Kraków", ["45231300-8", "45252127-4"]),
    ("T020_en", "T020", "PLT-PL-002", "PZP-2024-020", "2024-07-01", "2024-11-30", 9_400_000.00, "en",
     "Construction of sanitary sewerage network and wastewater treatment plant for western Kraków district",
     "PL213", "Miasto Kraków", ["45231300-8", "45252127-4"]),
]

_INSERT = """
    INSERT INTO tender_translations_demo
        (pk, tender_id, platform_id, tender_national_id, publication_date, closing_date,
         estimated_total_value, language_code, title, nut_code, nut_label, cpv_codes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (pk) DO NOTHING
"""


class Command(BaseCommand):
    help = "Create PostgreSQL demo table, seed data, and Milvus collection."

    def add_arguments(self, parser):
        parser.add_argument(
            "--step", choices=["pg", "milvus", "all"], default="all",
            help="Which setup step to run (default: all).",
        )
        parser.add_argument(
            "--recreate-pg", action="store_true",
            help="Drop and recreate the PostgreSQL table before creating.",
        )
        parser.add_argument(
            "--recreate", action="store_true",
            help="Drop and recreate the Milvus collection before creating.",
        )

    def handle(self, *args, **options):
        step = options["step"]

        if step in ("all", "pg"):
            self._setup_postgres(recreate=options["recreate_pg"])

        if step in ("all", "milvus"):
            self._setup_milvus(recreate=options["recreate"])

    # ------------------------------------------------------------------

    def _setup_postgres(self, recreate: bool = False):
        logger.info("setup_demo.pg.start")
        with get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                if recreate:
                    cur.execute(_DROP_TABLE)
                    logger.info("setup_demo.pg.table_dropped")
                for stmt in _CREATE_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
            logger.info("setup_demo.pg.table_ready")

            conn.autocommit = False
            with conn.cursor() as cur:
                cur.executemany(_INSERT, _SEED_ROWS)
            conn.commit()
            logger.info("setup_demo.pg.seeded", rows=len(_SEED_ROWS))

    def _setup_milvus(self, recreate: bool = False):
        logger.info("setup_demo.milvus.start")
        client = TenderSearchMilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN,
            collection_name=settings.TENDER_SEARCH_COLLECTION,
            vector_dim=settings.TENDER_SEARCH_VECTOR_DIM,
        )
        if recreate:
            client.drop_collection()
            logger.info("setup_demo.milvus.dropped")
        client.ensure_collection()
        logger.info("setup_demo.milvus.ready",
                    collection=settings.TENDER_SEARCH_COLLECTION)
