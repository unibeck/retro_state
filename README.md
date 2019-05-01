# Retro State
Home Assistant (HA) component to handle state changes that have occurred in the past.
This is useful for asynchronous data that is not guaranteed to be delivered/processed immediately or in order. Note that
there are large implications of enabling such a powerful feature that is not natively implemented in HA. Please read 
all of the following documentation before using or submitting a bug report.

Provided are integrations with various base HA components to support states that occur in the past. While you can 
enable all of them, I suggest only enabling the integrations as needed. This will help reduced unexpected behavior 
given the invasive nature of supporting older states non-natively. The component integrations include:
- Recorder
- InfluxDB

Enabling these can partially or completely override the default behavior of the base HA component. Keep this in mind 
while debugging associated components.

The other part of this feature is having components to create states that occur in the past. Currently only [historic_template](#Historic Template Component)
is implemented, though it is quite flexible. Though you can copy or build your own component from scratch and update it 
to implement 

## Base HA Component Integrations

The example belows enables all the available component integrations:
```aidl


```

## Historic Template Component

A component modeled from the original Template component, with the addition of `last_changed_template` and 
`last_updated_template` inputs. This allows you to save a state that has occurred in the past. The Template component 
was chosen for its flexibility as you can aggregate a new state based on any other state change.

// TODO: This may not be the case when we implement the new historic state event since the UI is listening for the new 
state event.
Note that when saving a state that is older than the current state, the value on the UI may temporarily update to the 
older state. Refresh the UI to get the actual _current_ state.

## Devs

`historic_template` is a good example to get started implementing your own component that creates states in the past.
There are a few major pieces that make this all work:
- `HistoricEntity` class
  - This replicates the base HA `Entity` class, though it includes `last_changed` and `last_updated` properties
  - Subclass your component from `HistoricEntity` and set the `last_changed` and `last_updated` properties as your
  component needs, and retro_state's framework will handle the rest
- `new_historic_state_event` event
  - An event that fires when a state has occurred in the past within this retro_state's framework
  - The component integrations listen for this event and integrate it respectively
  - You should not need to manually fire this event
