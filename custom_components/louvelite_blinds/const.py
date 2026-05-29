"""Constants for the Louvelite Blinds integration."""

DOMAIN = "louvelite_blinds"

# Hub config keys
CONF_HOST = "host"
CONF_HUB_ID = "hub_id"
CONF_PROTOCOL = "protocol"
CONF_PORT = "port"
CONF_MOTOR_CODE = "motor_code"

# Collection keys held in entry.options
CONF_REMOTES = "remotes"
CONF_BLINDS = "blinds"

# Per-remote keys
CONF_REMOTE_ID = "remote_id"          # internal stable id (slug or uuid)
CONF_REMOTE_LABEL = "label"           # user-facing name e.g. "Living Room remote"
CONF_PREFIX = "prefix"                # "ID1.ID2", e.g. "021.230"
CONF_REMOTE_MODEL = "model"           # optional, e.g. "RF1944" — cosmetic only

# Per-blind keys
CONF_BLIND_ID = "blind_id"            # internal stable id
CONF_NAME = "name"
CONF_ROOM = "room"
CONF_CHANNEL = "channel"              # 01-15 (15 = group/room broadcast)
CONF_BLIND_TYPE = "blind_type"
CONF_CLOSE_TIME = "close_time"

# Channel limits (per Neo Open Local protocol)
MIN_CHANNEL = 1
MAX_CHANNEL = 15
GROUP_CHANNEL = 15

# Protocols
PROTOCOL_HTTP = "http"
PROTOCOL_TCP = "tcp"
DEFAULT_PROTOCOL = PROTOCOL_TCP
DEFAULT_HTTP_PORT = 8838
DEFAULT_TCP_PORT = 8839
DEFAULT_PORT = DEFAULT_TCP_PORT  # tracks DEFAULT_PROTOCOL
DEFAULT_CLOSE_TIME = 30

# Blind types — drive the supported_features the cover entity exposes
BLIND_TYPE_ROLLER = "roller"
BLIND_TYPE_VENETIAN = "venetian"
BLIND_TYPE_TDBU = "tdbu"  # Top-Down / Bottom-Up

BLIND_TYPES = [BLIND_TYPE_ROLLER, BLIND_TYPE_VENETIAN, BLIND_TYPE_TDBU]

# Wire commands (from Neo Open Local HTTP / TCP protocol)
CMD_UP = "up"
CMD_DOWN = "dn"
CMD_STOP = "sp"
CMD_MICRO_UP = "mu"
CMD_MICRO_DOWN = "md"

# Top-Down / Bottom-Up second-rail commands
CMD_UP_RAIL2 = "u2"
CMD_DOWN_RAIL2 = "d2"

# Per-blind sub-id used to distinguish TDBU rails inside one config entry
RAIL_PRIMARY = 1
RAIL_SECONDARY = 2

# Hub I/O behaviour
IO_TIMEOUT = 10.0
COMMAND_BACKOFF = 0.7  # min seconds between consecutive commands to the hub
