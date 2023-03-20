## OBS MQTT Status to Home Assistant

## NOTE:

This is a clone of https://gist.github.com/HeedfulCrayon/9ff74d2aa1bc629ed17e0780f9a91a3d

The main difference is that it contains the support for Virtual Camera in OBS.

The work is copyrighted to [@HeedfulCrayon](https://github.com/HeedfulCrayon), this repository
is here for archiving purposes only.

Tested under OBS Studio 29.0.2, on Pop!_OS 22.04, connecting to Home Assistant 2023.3.5.

### Setup:
1. Download script
2. Install mqtt-wrapper `pip install mqtt-wrapper`
3. Open OBS Studio
4. In OBS Studio add a script (Tools -> Scripts)
5. Configure script parameters (my base channel is homeassistant and my sensor name is obs, creating the path homeassistant/sensor/obs)

![script_parameters](https://user-images.githubusercontent.com/5224972/116624859-eeb98b80-a905-11eb-9620-6dfe53b15551.png)

6. Click the script refresh button
7. If mqtt autodiscovery is on in home assistant, you should see a sensor called sensor.[MQTT Sensor Name] with attributes containing the stats.

   If you have allowed the MQTT to control OBS, you will see two switches called switch.[MQTT Sensor Name]_record and switch.[MQTT Sensor Name]_stream

   You will also see a switch for each profile named switch.[MQTT Sensor Name]_[OBS Profile Name]_Profile (__NOTE: Profiles in OBS will have to contain no spaces__)

   If mqtt autodiscovery is not turned on, you will need to add this as your sensor config
    ```
    - platform: "mqtt"
      name: "OBS"
      state_topic: "[Your set topic here]/state"
      icon: "mdi:video-wireless"
      force_update: true
      qos: 1
      json_attributes_topic: "[Your set topic here]/attributes"
    ```
   and if you would like to control via MQTT without autodiscovery you will need to add two mqtt switches for recording and streaming
    ```
    - platform: "mqtt"
      name: OBS Record Switch
      state_topic: "[MQTT Base Channel]/switch/[MQTT Sensor Name]/record/state"
      command_topic: "[MQTT Base Channel]/switch/[MQTT Sensor Name]/record/set"
      available_topic: "[MQTT Base Channel]/switch/[MQTT Sensor Name]/record/available"
      payload_on: "ON"
      payload_off: "OFF"
      icon: mdi:record
    - platform: "mqtt"
      name: OBS Stream Switch
      state_topic: "[MQTT Base Channel]/switch/[MQTT Sensor Name]/stream/state"
      command_topic: "[MQTT Base Channel]/switch/[MQTT Sensor Name]/stream/set"
      available_topic: "[MQTT Base Channel]/switch/[MQTT Sensor Name]/stream/available"
      payload_on: "ON"
      payload_off: "OFF"
      icon: mdi:broadcast
    ```
   If you would like to control profiles without discovery turned on you will need to add switches __FOR EACH__ profile you wish to turn on from Home Assistant
    ```
    - platform: "mqtt"
      name: OBS Test Profile
      state_topic: "[MQTT Base Channel]/switch/[OBS Profile Name]/state"
      command_topic: "[MQTT Base Channel]/switch/[OBS Profile Name]/profile/set"
      payload_on: "ON"
      payload_off: "OFF"
      icon: mdi:alpha-p-box
    ```

### Sensor States
* Recording
* Streaming
* Streaming and Recording
* Stopped (OBS Open)
* Off (OBS Closed)

# NOTE: If you have autodiscovery on when you update the script, make sure to remove the Stream, Record and OBS Sensor configs by doing an empty publish to their respective configs

`[Your base channel]/sensor/[Sensor Name]/config` for sensor

`[Your base channel]/switch/[Sensor Name]_stream/config` for stream switch

`[Your base channel]/sensor/[Sensor Name]_record/config` for record switch
