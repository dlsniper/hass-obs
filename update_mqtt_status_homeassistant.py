import json
import socket # Just so we can properly handle hostname exceptions
import obspython as obs
import paho.mqtt.client as mqtt
import ssl
import pathlib
import time
import enum
import uuid


# Meta
__version__ = '1.0.2'
__version_info__ = (1, 0, 1)
__license__ = "AGPLv3"
__license_info__ = {
    "AGPLv3": {
        "product": "update_mqtt_status_homeassistant",
        "users": 0, # 0 being unlimited
        "customer": "Unsupported",
        "version": __version__,
        "license_format": "1.0",
    }
}
__author__ = 'HeedfulCrayon'

__doc__ = """\
Publishes real-time OBS status info to the given MQTT server/port/channel \
at the configured interval. Also opens up controllable aspects of OBS to \
be controlled through MQTT.
"""

# Default values for the configurable options:
INTERVAL = 5 # Update interval (in seconds)
MQTT_HOST = "localhost" # Hostname of your MQTT server
MQTT_USER = ""
MQTT_PW = ""
MQTT_PORT = 1883 # Default MQTT port is 1883
MQTT_BASE_CHANNEL = ""
MQTT_SENSOR_NAME = "obs"
PROFILES = []
STREAM_SWITCH = None
VIRTUAL_CAMERA_SWITCH = None
RECORD_SWITCH = None
SENSOR = None
CONTROL = False
DEBUG = False
LOCK = False
MAC = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                for ele in range(0,8*6,8)][::-1])

class SwitchType(str, enum.Enum):
    profile = "profile"
    record = "record"
    stream = "stream"
    virtual_camera = "virtual_camera"

class SwitchPayload(str, enum.Enum):
    OFF = "OFF"
    ON = "ON"

class Switch:
    """
    Represents a controllable aspect of OBS (Profile, Record, Stream, etc.)
    """
    def __init__(self):
        self.publish_config()
        self.subscribe()
        self.publish_command(SwitchPayload.OFF)

    def publish_config(self):
        CLIENT.publish(self.config_topic, json.dumps(self.config))
        if DEBUG: print(f"Published config {self.config['name']}")

    def subscribe(self):
        CLIENT.subscribe(self.command_topic)
        if DEBUG: print(f"Subscribed to {self.config['name']}")

    def publish_state(self, payload):
        CLIENT.publish(self.state_topic, payload)
        if DEBUG: print(f"{self.config['name']} state changed to {payload}")

    def publish_command(self, payload):
        CLIENT.publish(self.command_topic, payload)
        if DEBUG: print(f"{self.config['name']} command published. Payload: {payload}")

class PersistentSwitch(Switch):
    """
    Switch that is persisted (retained) in MQTT
    """
    def __init__(self):
        super().__init__()
        self.publish_availability(SwitchPayload.ON)

    def publish_config(self):
        CLIENT.publish(self.config_topic, json.dumps(self.config), retain=True)
        if DEBUG: print(f"Published config {self.config['name']}")

    def publish_availability(self, payload):
        CLIENT.publish(self.available_topic, payload)
        if DEBUG: print(f"{self.config['name']} availability set to {payload}")

class ProfileSwitch(Switch):
    def __init__(self, profile_name, mqtt_base_channel, mqtt_sensor_name):
        self.profile_name = profile_name
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.profile
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.profile_name}/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.profile_name}/profile/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.profile_name}/config"
        self.config = {
            "name": f"{self.profile_name} Profile",
            "unique_id": f"{self.mqtt_sensor_name}_{self.profile_name}_profile",
            "device": {
                "name": f"{self.mqtt_sensor_name}",
                "identifiers": f"[['mac',{MAC}]]",
                "manufacturer": f"OBS Script v.{__version__}",
                "sw_version": __version__
            },
            "state_topic": self.state_topic,
            "command_topic": self.command_topic,
            "icon": f"mdi:alpha-{self.profile_name[0].lower()}-box",
            "payload_on": SwitchPayload.ON,
            "payload_off": SwitchPayload.OFF
        }
        super().__init__()

    def publish_remove_config(self):
        CLIENT.publish(self.config_topic, "")
        if DEBUG: print(f"Removed config {self.config['name']}")

class StreamSwitch(PersistentSwitch):
    def __init__(self,  mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.stream
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/stream/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/stream/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}_stream/config"
        self.available_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/stream/available"
        self.config = {
            "name": f"{self.mqtt_sensor_name} Stream",
            "unique_id": f"{self.mqtt_sensor_name}_stream",
            "device": {
                "name": f"{self.mqtt_sensor_name}",
                "identifiers": f"[['mac',{MAC}]]",
                "manufacturer": f"OBS Script v.{__version__}",
                "sw_version": __version__
            },
            "state_topic": self.state_topic,
            "command_topic": self.command_topic,
            "payload_on": SwitchPayload.ON,
            "payload_off": SwitchPayload.OFF,
            "availability": {
                "payload_available": SwitchPayload.ON,
                "payload_not_available": SwitchPayload.OFF,
                "topic": self.available_topic
            },
            "icon": "mdi:broadcast"
        }
        super().__init__()

class VirtualCameraSwitch(PersistentSwitch):
    def __init__(self,  mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.virtual_camera
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtual_camera/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtual_camera/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}_virtual_camera/config"
        self.available_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/virtual_camera/available"
        self.config = {
            "name": f"{self.mqtt_sensor_name} Virtual Camera",
            "unique_id": f"{self.mqtt_sensor_name}_virtual_camera",
            "device": {
                "name": f"{self.mqtt_sensor_name}",
                "identifiers": f"[['mac',{MAC}]]",
                "manufacturer": f"OBS Script v.{__version__}",
                "sw_version": __version__
            },
            "state_topic": self.state_topic,
            "command_topic": self.command_topic,
            "payload_on": SwitchPayload.ON,
            "payload_off": SwitchPayload.OFF,
            "availability": {
                "payload_available": SwitchPayload.ON,
                "payload_not_available": SwitchPayload.OFF,
                "topic": self.available_topic
            },
            "icon": "mdi:broadcast"
        }
        super().__init__()

class RecordSwitch(PersistentSwitch):
    def __init__(self,  mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.switch_type = SwitchType.record
        self.state_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/record/state"
        self.command_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/record/set"
        self.config_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}_record/config"
        self.available_topic = f"{self.mqtt_base_channel}/switch/{self.mqtt_sensor_name}/record/available"
        self.config = {
            "name": f"{self.mqtt_sensor_name} Record",
            "unique_id": f"{self.mqtt_sensor_name}_record",
            "device": {
                "name": f"{self.mqtt_sensor_name}",
                "identifiers": f"[['mac',{MAC}]]",
                "manufacturer": f"OBS Script v.{__version__}",
                "sw_version": __version__
            },
            "state_topic": self.state_topic,
            "command_topic": self.command_topic,
            "payload_on": SwitchPayload.ON,
            "payload_off": SwitchPayload.OFF,
            "availability": {
                "payload_available": SwitchPayload.ON,
                "payload_not_available": SwitchPayload.OFF,
                "topic": self.available_topic
            },
            "icon": "mdi:record"
        }
        super().__init__()

class SensorState(str, enum.Enum):
    Off = "Off"
    Stopped = "Stopped"
    Recording = "Recording"
    Streaming = "Streaming"
    Recording_and_Streaming = "Recording and Streaming"
    VirtualCamera = "Virtual Camera"

class Sensor:
    def __init__(self, mqtt_base_channel, mqtt_sensor_name):
        self.mqtt_base_channel = mqtt_base_channel
        self.mqtt_sensor_name = mqtt_sensor_name
        self.state_topic = f"{self.mqtt_base_channel}/sensor/{self.mqtt_sensor_name}/state"
        self.config_topic = f"{self.mqtt_base_channel}/sensor/{self.mqtt_sensor_name}/config"
        self.attributes_topic = f"{self.mqtt_base_channel}/sensor/{self.mqtt_sensor_name}/attributes"
        self.config = {
            "name": self.mqtt_sensor_name,
            "unique_id": self.mqtt_sensor_name,
            "device": {
                "name": f"{self.mqtt_sensor_name}",
                "identifiers": f"[['mac',{MAC}]]",
                "manufacturer": f"OBS Script v.{__version__}",
                "sw_version": __version__
            },
            "state_topic": self.state_topic,
            "json_attributes_topic": self.attributes_topic
        }
        self.state = self.get_state
        self.previous_state = SensorState.Off
        self.recording = obs.obs_frontend_recording_active
        self.streaming = obs.obs_frontend_streaming_active
        self.virtual_camera = obs.obs_frontend_virtualcam_active
        self.paused = obs.obs_frontend_recording_paused
        self.replay_buffer =obs.obs_frontend_replay_buffer_active
        self.fps = obs.obs_get_active_fps
        self.frame_time_ns = obs.obs_get_average_frame_time_ns
        self.frames = obs.obs_get_total_frames
        self.lagged_frames = obs.obs_get_lagged_frames
        self.active = False
        self.publish_config()
        self.publish_state()
        self.publish_attributes()

    def publish_config(self):
        CLIENT.publish(self.config_topic, json.dumps(self.config))
        if DEBUG: print(f"Published config {self.config['name']}")

    def publish_attributes(self):
        stats = {
            "recording": self.recording(),
            "streaming": self.streaming(),
            "virtual_camera": self.virtual_camera(),
            "paused": self.paused(),
            "fps": self.fps(),
            "frame_time_ns": self.frame_time_ns(),
            "frames": self.frames(),
            "lagged_frames": self.lagged_frames()
        }
        CLIENT.publish(self.attributes_topic, json.dumps(stats))
        self.publish_state()
        if DEBUG:
            print(f"{self.config['name']} attributes updated")
            print(json.dumps(stats))

    def get_state(self):
        recording = self.recording()
        streaming = self.streaming()
        virtual_camera = self.virtual_camera()
        if recording and streaming:
            self.active = True
            self.previous_state = SensorState.Recording_and_Streaming
            return SensorState.Recording_and_Streaming
        elif streaming:
            self.active = True
            self.previous_state = SensorState.Streaming
            return SensorState.Streaming
        elif recording:
            self.active = True
            self.previous_state = SensorState.Recording
            return SensorState.Recording
        elif virtual_camera:
            self.active = True
            self.previous_state = SensorState.VirtualCamera
            return SensorState.VirtualCamera
        else:
            self.active = False
            self.previous_state = SensorState.Stopped
            return SensorState.Stopped

    def publish_state(self):
        state = self.state()
        CLIENT.publish(self.state_topic, state)
        if DEBUG: print(f"{self.config['name']} state changed to {state}")

    def publish_off_state(self):
        self.previous_state = SensorState.Off
        CLIENT.publish(self.state_topic, SensorState.Off)
        if DEBUG: print(f"{self.config['name']} state changed to {SensorState.Off}")

# MQTT Event Functions
def on_mqtt_connect(client, userdata, flags, rc):
    """
    Called when the MQTT client is connected from the server.  Just prints a
    message indicating we connected successfully.
    """
    print("MQTT connection successful")

    set_homeassistant_config()

def on_mqtt_disconnect(client, userdata, rc):
    """
    Called when the MQTT client gets disconnected.  Just logs a message about it
    (we'll auto-reconnect inside of update_status()).
    """
    print("MQTT disconnected.  Reason: {}".format(str(rc)))

def on_mqtt_message(client, userdata, message):
    """
    Handles MQTT messages that have been subscribed to
    """
    payload = str(message.payload.decode("utf-8"))
    if DEBUG: print(f"{message.topic}: {payload}")
    entity = message_to_switch_entity(message)
    if entity != None:
        execute_action(entity, payload)

# OBS Script Function Exports
def script_description():
    return __doc__ # We wrote a nice docstring...  Might as well use it!

def script_load(settings):
    """
    Just prints a message indicating that the script was loaded successfully.
    """
    global STATE
    print("MQTT script loaded.")
    STATE = "Initializing"

def script_unload():
    """
    Publishes a final status message indicating OBS is off
    (so your MQTT sensor doesn't get stuck thinking you're
    recording/streaming forever) and calls `CLIENT.disconnect()`.
    """
    global STATE
    print("Script unloading")
    STATE = "Off"
    if CLIENT.is_connected():
        SENSOR.publish_off_state()
        set_persistent_switch_availability()
        remove_profiles_from_homeassistant()
        time.sleep(0.5)
        CLIENT.disconnect()
    CLIENT.loop_stop()

def script_defaults(settings):
    """
    Sets up our default settings in the OBS Scripts interface.
    """
    obs.obs_data_set_default_string(settings, "mqtt_host", MQTT_HOST)
    obs.obs_data_set_default_string(settings, "mqtt_user", MQTT_USER)
    obs.obs_data_set_default_string(settings, "mqtt_pw", MQTT_PW)
    obs.obs_data_set_default_string(settings, "mqtt_base_channel", MQTT_BASE_CHANNEL)
    obs.obs_data_set_default_string(settings, "mqtt_sensor_name", MQTT_SENSOR_NAME)
    obs.obs_data_set_default_int(settings, "mqtt_port", MQTT_PORT)
    obs.obs_data_set_default_int(settings, "interval", INTERVAL)
    obs.obs_data_set_default_bool(settings, "controllable", CONTROL)

def script_properties():
    """
    Makes this script's settings configurable via OBS's Scripts GUI.
    """
    props = obs.obs_properties_create()
    obs.obs_properties_add_text(props, "mqtt_host", "MQTT server hostname", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "mqtt_user", "MQTT username", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "mqtt_pw", "MQTT password", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_text(props, "mqtt_base_channel", "MQTT Base channel",obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "mqtt_sensor_name", "MQTT Sensor Name",obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(props, "mqtt_port", "MQTT TCP/IP port", MQTT_PORT, 65535, 1)
    obs.obs_properties_add_int(props, "interval", "Update Interval (seconds)", 1, 3600, 1)
    obs.obs_properties_add_bool(props, "controllable", "Control Streaming/Recording via MQTT")
    obs.obs_properties_add_bool(props, "debug", "Debug")
    return props

def script_update(settings):
    """
    Applies any changes made to the MQTT settings in the OBS Scripts GUI then
    reconnects the MQTT client.
    """
    # Apply the new settings
    global MQTT_HOST
    global MQTT_USER
    global MQTT_PW
    global MQTT_PORT
    global MQTT_BASE_CHANNEL
    global MQTT_SENSOR_NAME
    global INTERVAL
    global CONTROL
    global DEBUG
    mqtt_host = obs.obs_data_get_string(settings, "mqtt_host")
    if mqtt_host != MQTT_HOST:
        MQTT_HOST = mqtt_host
    mqtt_user = obs.obs_data_get_string(settings, "mqtt_user")
    if mqtt_user != MQTT_USER:
        MQTT_USER = mqtt_user
    mqtt_pw = obs.obs_data_get_string(settings, "mqtt_pw")
    if mqtt_pw != MQTT_PW:
        MQTT_PW = mqtt_pw
    mqtt_base_channel = obs.obs_data_get_string(settings, "mqtt_base_channel")
    if mqtt_base_channel != MQTT_BASE_CHANNEL:
        MQTT_BASE_CHANNEL = mqtt_base_channel
    mqtt_sensor_name = obs.obs_data_get_string(settings, "mqtt_sensor_name")
    if mqtt_sensor_name != MQTT_SENSOR_NAME:
        MQTT_SENSOR_NAME = mqtt_sensor_name
    mqtt_port = obs.obs_data_get_int(settings, "mqtt_port")
    if mqtt_port != MQTT_PORT:
        MQTT_PORT = mqtt_port
    INTERVAL = obs.obs_data_get_int(settings, "interval")
    CONTROL = obs.obs_data_get_bool(settings, "controllable")
    DEBUG = obs.obs_data_get_bool(settings, "debug")

    # Disconnect (if connected) and reconnect the MQTT client
    CLIENT.disconnect()
    try:
        if MQTT_PW != "" and MQTT_USER != "":
            CLIENT.username_pw_set(MQTT_USER, password=MQTT_PW)
        CLIENT.connect_async(MQTT_HOST, MQTT_PORT, 60)
    except (socket.gaierror, ConnectionRefusedError) as e:
        print("NOTE: Got a socket issue: %s" % e)
        pass # Ignore it for now


    obs.obs_frontend_remove_event_callback(frontend_changed)
    obs.obs_frontend_add_event_callback(frontend_changed)
    # Remove and replace the timer that publishes our status information
    obs.timer_remove(update_status)
    obs.timer_add(update_status, INTERVAL * 1000)
    CLIENT.loop_start()

def frontend_changed(event):
    """
    Callback for frontend events
    """
    switcher = {
        obs.OBS_FRONTEND_EVENT_PROFILE_CHANGED: profile_changed,
        obs.OBS_FRONTEND_EVENT_PROFILE_LIST_CHANGED: profile_list_changed,
        obs.OBS_FRONTEND_EVENT_RECORDING_STARTED: recording_started,
        obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED: recording_stopped,
        obs.OBS_FRONTEND_EVENT_STREAMING_STARTED: streaming_started,
        obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED: streaming_stopped,
        obs.OBS_FRONTEND_EVENT_VIRTUALCAM_STARTED: virtual_camera_started,
        obs.OBS_FRONTEND_EVENT_VIRTUALCAM_STOPPED: virtual_camera_stopped,
    }
    function = switcher.get(event, None)
    if function != None:
        function()
    else:
        print(f"Unknown event fired: {event}")

def profile_changed():
    """
    Callback for OBS_FRONTEND_EVENT_PROFILE_CHANGED
    """
    global PROFILE
    while LOCK:
        time.sleep(0.5)
    PROFILE.publish_state(SwitchPayload.OFF)
    new_profile = obs.obs_frontend_get_current_profile()
    for profile in PROFILES:
        if profile.profile_name == new_profile:
            profile.publish_state(SwitchPayload.ON)
            PROFILE = profile
    print("Profile Changed")

def profile_list_changed():
    """
    Callback for OBS_FRONTEND_EVENT_PROFILE_LIST_CHANGED
    """
    global LOCK
    LOCK = True
    for profile in PROFILES:
        profile.publish_remove_config()
    time.sleep(0.1)
    setup_profiles_in_homeassistant()
    LOCK = False
    print("Profile List Changed")

def recording_started():
    """
    Publishes state of sensor and record switch
    """
    SENSOR.publish_state()
    SENSOR.publish_attributes()
    if CONTROL:
        RECORD_SWITCH.publish_state(SwitchPayload.ON)

def recording_stopped():
    """
    Publishes state of sensor and record switch
    """
    SENSOR.publish_state()
    if CONTROL:
        RECORD_SWITCH.publish_state(SwitchPayload.OFF)

def streaming_started():
    """
    Publishes state of sensor and stream switch
    """
    SENSOR.publish_state()
    SENSOR.publish_attributes()
    if CONTROL:
        STREAM_SWITCH.publish_state(SwitchPayload.ON)

def streaming_stopped():
    """
    Publishes state of sensor and stream switch
    """
    SENSOR.publish_state()
    if CONTROL:
        STREAM_SWITCH.publish_state(SwitchPayload.OFF)

def virtual_camera_started():
    """
    Publishes state of sensor and virtual camera switch
    """
    SENSOR.publish_state()
    SENSOR.publish_attributes()
    if CONTROL:
        VIRTUAL_CAMERA_SWITCH.publish_state(SwitchPayload.ON)

def virtual_camera_stopped():
    """
    Publishes state of sensor and virtual camera switch
    """
    SENSOR.publish_state()
    if CONTROL:
        VIRTUAL_CAMERA_SWITCH.publish_state(SwitchPayload.OFF)

# Event Helper Functions
def set_homeassistant_config():
    """
    Sends initial configuration state and attributes topic
    for autodiscovery in Home Assistant
    """
    global SENSOR
    SENSOR = Sensor(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)

    if CONTROL:
        setup_homeassistant_control()

def setup_homeassistant_control():
    """
    Sets up profile, recording and streaming controls
    """
    global STREAM_SWITCH
    global VIRTUAL_CAMERA_SWITCH
    global RECORD_SWITCH
    setup_profiles_in_homeassistant()
    # Set up switches for autodiscovery
    STREAM_SWITCH = StreamSwitch(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)
    VIRTUAL_CAMERA_SWITCH = VirtualCameraSwitch(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)
    RECORD_SWITCH = RecordSwitch(MQTT_BASE_CHANNEL, MQTT_SENSOR_NAME)

def setup_profiles_in_homeassistant():
    """
    Publishes config, and subscribes to the command topic for each profile.
    Also sets the current profile's state
    """
    global PROFILE
    global PROFILES
    current_profile = obs.obs_frontend_get_current_profile()
    profiles = obs.obs_frontend_get_profiles()
    PROFILES = []
    for profile in profiles:
        profile_switch = ProfileSwitch(
            profile_name=profile,
            mqtt_base_channel=MQTT_BASE_CHANNEL,
            mqtt_sensor_name=MQTT_SENSOR_NAME
        )
        PROFILES.append(profile_switch)
        if DEBUG: print(f"Profile {profile_switch.profile_name} added to PROFILES")
        if profile_switch.profile_name == current_profile:
            PROFILE = profile_switch
            profile_switch.publish_state(SwitchPayload.ON)

def set_persistent_switch_availability():
    """
    Reports the availability of the persistent switches
    """
    RECORD_SWITCH.publish_availability(SwitchPayload.OFF)
    STREAM_SWITCH.publish_availability(SwitchPayload.OFF)

def remove_profiles_from_homeassistant():
    """
    Profiles are removed when obs is not open
    """
    global PROFILES
    for profile in PROFILES:
        profile.publish_remove_config()
    PROFILES = []

def execute_action(switch, payload):
    """
    Executes frontend actions (Profile change, recording, streaming)
    """
    if switch.switch_type == SwitchType.profile:
        if SENSOR.active: # Not sure if this NEEDS to be here as it won't actually change the profile while streaming/recording
            return
        prev_profile = obs.obs_frontend_get_current_profile()
        if PROFILE.profile_name != switch.profile_name:
            obs.obs_frontend_set_current_profile(switch.profile_name)
        else:
            print(f"Already on profile {switch.profile_name}")
    elif switch.switch_type == SwitchType.stream:
        if payload == SwitchPayload.ON:
            obs.obs_frontend_streaming_start()
        else:
            obs.obs_frontend_streaming_stop()
    elif switch.switch_type == SwitchType.virtual_camera:
        if payload == SwitchPayload.ON:
            obs.obs_frontend_start_virtualcam()
        else:
            obs.obs_frontend_stop_virtualcam()
    elif switch.switch_type == SwitchType.record:
        if payload == SwitchPayload.ON:
            obs.obs_frontend_recording_start()
        else:
            obs.obs_frontend_recording_stop()

# Helper Functions
def update_status():
    """
    Updates the STATE and the STATUS global with the stats of the current session.
    This info if published (JSON-encoded) to the configured MQTT_HOST/MQTT_PORT/MQTT_BASE_CHANNEL.
    Meant to be called at the configured INTERVAL.
    """
    global SENSOR
    if CONTROL:
        STREAM_SWITCH.publish_availability(SwitchPayload.ON)
        VIRTUAL_CAMERA_SWITCH.publish_availability(SwitchPayload.ON)
        RECORD_SWITCH.publish_availability(SwitchPayload.ON)
    sensor_state = SENSOR.state()
    previous_state = SENSOR.previous_state
    if previous_state != SensorState.Stopped and sensor_state == SensorState.Stopped:
        print("Publishing Final Stopped Message")
        SENSOR.publish_attributes()
    if previous_state != SensorState.Off and sensor_state == SensorState.Off:
        print("Publishing Final Off Message")
        SENSOR.publish_attributes()
    if SENSOR.active:
        SENSOR.publish_attributes()

def message_to_switch_entity(message):
    """
    Converts MQTT Message to the corresponding switch entity
    """
    topic = pathlib.PurePosixPath(message.topic)
    message_type = SwitchType[topic.parent.stem] # Stream, Record or Profile
    if message_type == SwitchType.stream:
        return STREAM_SWITCH
    if message_type == SwitchType.virtual_camera:
        return VIRTUAL_CAMERA_SWITCH
    if message_type == SwitchType.record:
        return RECORD_SWITCH
    if message_type == SwitchType.profile:
        for profile in PROFILES:
            if profile.command_topic == message.topic:
                return profile
    return None

# Using a global MQTT client variable to keep things simple:
CLIENT = mqtt.Client()
CLIENT.on_connect = on_mqtt_connect
CLIENT.on_disconnect = on_mqtt_disconnect
CLIENT.on_message = on_mqtt_message
