# config.py — MoleNet Communication Manager Configuration
VERSION = "5.1.0"

# ============================================================
# Global mode
# ============================================================

SIMULATION_MODE = False
DEBUG_LORA = True
DEBUG_SIM = False


# ============================================================
# Node identity
# ============================================================

NODE_ID = 1


# ------------------------------------------------------------

ENABLE_DEEPSLEEP = False

SOIL_MODE = "SIM_FIXED"
ENERGY_MODE = "SIM_FIXED"

SIM_SOIL_FIXED_VALUE = 0.30
SIM_ENERGY_STATE = "OK"

FUZZY_SEND_THRESHOLD = 0.55

DTN_FLUSH_THRESHOLD = 1.10
FLUSH_MAX_BATCH = 5

WIFI_MAINTENANCE_INTERVAL_CYCLES = 999

# ------------------------------------------------------------



# ============================================================
# Embedded wake cycle
# ============================================================

SENSOR_INTERVAL_SECONDS = 3600
ENABLE_DEEPSLEEP = False
DEV_LOOP = False


# ============================================================
# Energy model
# ============================================================

# Options:
#   "SIM_FIXED"
#   "SIM_RANDOM"
#   "ADC"          future work

#ENERGY_MODE = "SIM_RANDOM" #"SIM_FIXED"

#SIM_ENERGY_STATE = "OK"

ENERGY_RANDOM_OK_PROB = 0.60
ENERGY_RANDOM_LOW_PROB = 0.25
ENERGY_RANDOM_CRITICAL_PROB = 0.15


# ============================================================
# Soil moisture model
# ============================================================

# Options:
#   "SIM_FIXED"
#   "SIM_RANDOM"
#   "SIM_RANDOM_SCENARIO"
#   "REAL"         future work
#SOIL_MODE = "SIM_RANDOM_SCENARIO" #"SIM_FIXED"

#SIM_SOIL_FIXED_VALUE = 0.30 #0.35

SOIL_RANDOM_MIN = 0.05
SOIL_RANDOM_MAX = 0.95

SOIL_NORMAL_MIN = 0.25
SOIL_NORMAL_MAX = 0.40

SOIL_RAINFALL_MIN = 0.40
SOIL_RAINFALL_MAX = 0.75

SOIL_EXTREME_DRY_MIN = 0.05
SOIL_EXTREME_DRY_MAX = 0.19

SOIL_EXTREME_WET_MIN = 0.80
SOIL_EXTREME_WET_MAX = 0.95

SOIL_SCENARIO_NORMAL_PROB = 0.40
SOIL_SCENARIO_RAINFALL_PROB = 0.35
SOIL_SCENARIO_EXTREME_DRY_PROB = 0.10
SOIL_SCENARIO_EXTREME_WET_PROB = 0.15


# ============================================================
# SX1276 / LoRa pins — MoleNet v6.3
# ============================================================

SPI_ID = 1

PIN_SCK = 14
PIN_MOSI = 47
PIN_MISO = 21

PIN_NSS = 48
PIN_RST = 15
PIN_DIO0 = 46


# ============================================================
# LoRa PHY settings
# ============================================================

LORA_FREQ_HZ = 868100000
LORA_BW = 125000
LORA_SF = 7
LORA_CR = 5
LORA_SYNC_WORD = 0x12

LORA_TX_POWER_DBM = 14
LORA_TX_TIMEOUT_MS = 3000
LORA_SR_PRIOR = 0.9

# ============================================================
# LoRa ACK / reliability
# ============================================================

ACK_WAIT_MS = 6000 #3000 


ACK_RETRIES_NORMAL = 2
ACK_RETRIES_EMERG = 3
ACK_RETRIES_LOW_ENERGY_CRITICAL = 0

LORA_HIST_N = 10
LORA_SR_PRIOR = 0.6


# ============================================================
# WiFi UDP ACK — data communication
# ============================================================


WIFI_SSID = "MERCUSYS_FCF8"
WIFI_PASS = "04092000"

# Compatibility aliases
WIFI_PASSWORD = WIFI_PASS

WIFI_UDP_HOST = "192.168.1.216"
WIFI_UDP_PORT = 5005

WIFI_CONNECT_TIMEOUT_MS = 10000 #6000
WIFI_ACK_WAIT_MS = 8000 #3000

WIFI_SR_PRIOR = 0.6
WIFI_FLUSH_MIN_SR = 0.5


# ============================================================
# BLE
# ============================================================

BLE_ADV_PREFIX = b"MNET"
BLE_ADV_MAX_PAYLOAD = 20
BLE_ADV_MS = 800

BLE_TARGET_NAME = "MoleNet-BLE-RX"
BLE_ACK_WAIT_MS = 5000


# ============================================================
# SD card / DTN storage
# ============================================================

SD_MOUNT_POINT = "/sd"

DTN_DIR = "/sd/dtn"
DTN_QUEUE_FILE = "/sd/dtn/queue.txt"
DTN_LOG_FILE = "/sd/dtn/dtn.log"

DTN_MAX_ITEMS = 200
DTN_DROP_POLICY = "DROP_OLDEST"

# For path-functionality testing: 1.10 disables ANSA flushing.
# For DTN/ANSA evaluation: set to 0.70.
#DTN_FLUSH_THRESHOLD = 0.70 #1.10

DTN_WARNING_USAGE = 0.85
#FLUSH_MAX_BATCH = 10


# ============================================================
# Priority levels
# ============================================================

PRIORITY_NORMAL = "NORMAL"
PRIORITY_WARNING = "WARNING"
PRIORITY_CRITICAL = "CRITICAL"


# ============================================================
# Event types
# ============================================================

EVENT_NONE = "NONE"

EVENT_EXTREME_WET = "EXTREME_WET"
EVENT_EXTREME_DRY = "EXTREME_DRY"

EVENT_LOW_BATTERY = "LOW_BATTERY"
EVENT_BATTERY_CRITICAL = "BATTERY_CRITICAL"

EVENT_SENSOR_FAULT = "SENSOR_FAULT"
EVENT_STORAGE_FAULT = "STORAGE_FAULT"
EVENT_DTN_ALMOST_FULL = "DTN_ALMOST_FULL"
EVENT_LINK_FAILURE = "LINK_FAILURE"


# ============================================================
# Two-level architecture naming
# ============================================================

PATH_NORMAL_FUZZY = "normal_fuzzy_path"
PATH_DETERMINISTIC_EVENT = "deterministic_event_path"

SUBPOLICY_FUZZY_SEND = "fuzzy_send"
SUBPOLICY_FUZZY_STORE = "fuzzy_store"
SUBPOLICY_FUZZY_LORA_FAILED_STORE = "fuzzy_lora_failed_store"

SUBPOLICY_WARNING_LOW_BATTERY = "warning_low_battery"

SUBPOLICY_CRITICAL_ENVIRONMENTAL = "critical_environmental"
SUBPOLICY_CRITICAL_ENVIRONMENTAL_LOW_ENERGY = "critical_environmental_low_energy_lora_only"

SUBPOLICY_CRITICAL_BATTERY_SHUTDOWN = "critical_battery_shutdown"


# Backward-compatible names
EVENT_PATH_NORMAL_FUZZY = PATH_NORMAL_FUZZY
EVENT_PATH_DETERMINISTIC_WARNING = PATH_DETERMINISTIC_EVENT
EVENT_PATH_DETERMINISTIC_CRITICAL = PATH_DETERMINISTIC_EVENT
EVENT_PATH_BATTERY_CRITICAL_STORE_ONLY = PATH_DETERMINISTIC_EVENT


# ============================================================
# Energy policies
# ============================================================

ENERGY_POLICY_FULL_OPERATION = "full_operation"
ENERGY_POLICY_LOW_WARNING_ONLY = "low_warning_only"
ENERGY_POLICY_LOW_EMERGENCY_LORA_ONLY = "low_emergency_lora_only"
ENERGY_POLICY_CRITICAL_STORE_ONLY = "critical_store_only"


# ============================================================
# Priority thresholds
# ============================================================

MOISTURE_CRITICAL_DRY = 0.20
MOISTURE_CRITICAL_HIGH = 0.80


# ============================================================
# Fuzzy layer
# ============================================================

FUZZY_SEND_THRESHOLD = 0.55
SEND_CONF_THRESHOLD = FUZZY_SEND_THRESHOLD


# ============================================================
# WiFi maintenance / remote configuration update
# ============================================================

WIFI_MAINTENANCE_ENABLED = True
#WIFI_MAINTENANCE_INTERVAL_CYCLES = 24

CONFIG_UPDATE_HOST = WIFI_UDP_HOST
CONFIG_UPDATE_PORT = 8080
CONFIG_UPDATE_PATH = "/molenet_config.json"

FIRMWARE_MANIFEST_PATH = "/firmware_manifest.json"

RUNTIME_CONFIG_FILE = "/sd/runtime_config.json"

CONFIG_UPDATE_ALLOWED_KEYS = [
    "FUZZY_SEND_THRESHOLD",
    "DTN_FLUSH_THRESHOLD",
    "FLUSH_MAX_BATCH",
    "ACK_WAIT_MS",
    "WIFI_ACK_WAIT_MS",
    "SENSOR_INTERVAL_SECONDS",
    "WIFI_MAINTENANCE_INTERVAL_CYCLES"
]


# ============================================================
# Low battery warning
# ============================================================

LOW_BATTERY_SEND_WARNING_ONCE = True
LOW_BATTERY_WARNING_FILE = "/sd/dtn/low_battery_warning_sent.txt"


# ============================================================
# Outcomes
# ============================================================

OUTCOME_SUCCESS = "success"
OUTCOME_FAILED = "failed"
OUTCOME_STORED = "stored"

OUTCOME_FLUSH_SUCCESS = "flush_success"
OUTCOME_FLUSH_PARTIAL = "flush_partial"
OUTCOME_FLUSH_FAILED = "flush_failed"

OUTCOME_BLE_ADVERTISED_ONLY = "ble_advertised_only"


# ============================================================
# Energy proxy weights
# ============================================================

ENERGY_COST_CPU_WAKE = 0.2

ENERGY_COST_LORA_TX = 1.0
ENERGY_COST_LORA_ACK_WAIT = 0.5

ENERGY_COST_WIFI_TX = 5.0
ENERGY_COST_WIFI_MAINT = 0.8

ENERGY_COST_BLE_ADV = 0.3
ENERGY_COST_BLE_GATT = 0.8

ENERGY_COST_SD_WRITE = 0.1

# ============================================================
# ANSA
# ============================================================
ANSA_WIFI_ENABLED = True
ANSA_WIFI_BACKLOG_THRESHOLD = 0.50

# ============================================================
# Evaluation logging
# ============================================================

EVAL_LOG_ENABLED = True

EVAL_LOG_DIR = "/sd/logs"
EVAL_LOG_FILE = "/sd/logs/cm_eval.csv"

RUN_ID = 1


EVAL_LOG_DIR = "/sd"

EVAL_OUTPUT_FILE = "cm_functionality.csv"

# ============================================================
# Evaluation defaults
# ============================================================

EVAL_SCENARIO = "TEST"
RUN_ID = 1
GLOBAL_CYCLE = 1
MIX_LABEL = ""
SCENARIO_BLOCK = ""

SOIL_MODE = "SIM_FIXED"
SIM_SOIL_VALUE = 0.30
SIM_SOIL_FIXED_VALUE = 0.30

ENERGY_MODE = "SIM_FIXED"
SIM_ENERGY_STATE = "OK"