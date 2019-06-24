# Retro State
Home Assistant (HA) custom component to handle state changes that have occurred in the past.
This is useful for asynchronous data that is not guaranteed to be delivered/processed immediately or in order. Note that
there are large implications of enabling such a powerful feature that is not natively implemented in HA. Please read 
all of the following documentation before using or submitting a bug report.

Provided are integrations with various base HA components to _handle_ states that occur in the past. While you can 
enable all of them, I suggest only enabling the integrations as needed. This will help reduced unexpected behavior 
given the invasive nature of supporting older states non-natively. The component integrations include:
- Recorder
- InfluxDB

Enabling these can partially or completely override the default behavior of the base HA component. Keep this in mind 
while debugging associated components.

This project also provides components to _create_ states that can occur in the past. Currently, only [historic_template](#Historic Template Component)
is implemented, though it is quite flexible. Devs can use the `historic_template` component as an example to 
build your own component.

## Base HA Component Integrations

The example below enables all the available component integrations:
```
retro_state:
  recorder: enable
  influxdb: enable
```

There are some things to be aware of when enabling these integrations:
- Retro_state will wait up to 60 seconds for the base component to start. This is to ensure that the base component and 
retro_state integration are not running at the same time
- Retro_state will stop the base component, then start retro_stats's updated version that supports historic states. 
During this switch there may be some events that are not captured by the enabled component

## Historic Template Component

A component modeled from the original Template component, with the addition of `last_changed_template` and 
`last_updated_template` inputs. This allows you to save a state that has occurred in the past. The Template component 
was chosen for its flexibility as you can aggregate a new state based on any other state change.

Here is one example of the `historic_template` that parses an HTTP sensor's attributes:
```
sensor:
  - platform: historic_template
    sensors:
      f150_truck_rpm:
        value_template: '{{ states.sensor.f150_truck_data.attributes["rpm"] }}'
        last_updated_template: '{{ states.sensor.f150_truck_data.attributes["client_dt"] }}'
        unit_of_measurement: 'RPM'
```

## Devs

`historic_template` is a good example to get started implementing your own component that creates states in the past.
There are a few major pieces that make this all work:
- `HistoricEntity` class
  - This replicates the base HA `Entity` class, though it includes `last_changed` and `last_updated` properties
  - Subclass your component from `HistoricEntity` and set the `last_changed` and `last_updated` properties as your
  component needs, and retro_state's framework will handle the rest
- `historic_state_changed` event
  - An event that fires when a state has occurred in the past within this retro_state's framework
  - The component integrations listen for this event and integrate it respectively
  - You should not need to manually fire this event

### Demo Config

Use the following configuration snippet to get started with testing all integrations:
```yaml
recorder:

influxdb:
  database: hass

sensor:
  - platform: historic_template
    sensors:
      f150_truck_rpm:
        value_template: '{{ states.sensor.f150_truck_data.attributes["rpm"] }}'
        last_updated_template: '{{ states.sensor.f150_truck_data.attributes["client_dt"] }}'
        unit_of_measurement: 'RPM'

retro_state:
  recorder: enable
  influxdb: enable
  
logger:
    default: info
    logs:
        custom_components.historic_template: debug
        custom_components.retro_state: debug
```

If you don't already have a InfluxDB instance running, you can spin one up with docker:
```
docker run --name influxdb -d --rm \
    -p 8086:8086 \
    -e INFLUXDB_DB=hass \
    -v influxdb:/var/lib/influxdb \
    influxdb:1.7.6
```

### Manual Test

You can test these integrations with the curl command below. Note that this command is based on the aforementioned demo 
config and that you need to supply your own bearer token.
```bash
curl -X POST \
  http://localhost:8123/api/states/sensor.f150_truck_data \
  -H "Authorization: Bearer ${HASS_TOKEN}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d '{
        "state": "OK",
        "attributes": {
          "rpm": "824",
          "client_dt": "2019-06-21T22:45:59.869726+00:00"
        }
      }'
```
