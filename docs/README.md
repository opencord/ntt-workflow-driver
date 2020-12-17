# NTT Workflow Driver Service

This service implements the ONU and Subscriber management logic for a sample workflow to support the IEEE standard PON. 

> NOTE1: This service depends on models contained in the R-CORD and OLT Services, so make sure that the `rcord-synchronizer` and `volt-synchronzier` are running

> NOTE2: When this service runs, make sure that [`voltha-eponolt-adater`](https://github.com/opencord/voltha-eponolt-adapter) and [`voltha-epononu-adapter`](https://github.com/opencord/voltha-epononu-adapter) are used as VOLTHA adapter. 

## Models

This service is composed of the following models:

- `NttWorkflowDriverServiceInstance`. This model holds various state associated with the state machine for validating a subscriber's ONU.
    - `serial_number`. Serial number of ONU.
    - NOTE: we might consider creating ONU always in APPROVED 
    - `authentication_state`. [`AWAITING` | `STARTED` | `REQUESTED` | `APPROVED` | `DENIED`]. Current authentication state.
    - `of_dpid`. OLT Openflow ID.
    - `uni_port_id`. ONU UNI Port ID.
    - `admin_onu_state`. [`AWAITING` | `ENABLED` | `DISABLED`]. ONU administrative state.
    - `status_message`. Status text of current state machine state.
    - `mac_address`. Subscriber mac address.
    - `oper_onu_status`. [`AWAITING` | `ENABLED` | `DISABLED`]. ONU operational state.
- `NttWorkflowDriverOltInformation`. This model holds various parameter associated with the detected OLTs.
    - `of_dpid`. OLT mac address.
    - `olt_location`. OLT location information. 
    - `olt_package`. OLT package information (SIEPON package A or B). 
    - `port_no`. Number of the port where the OLT was inserted. 
- `NttWorkflowDriverWhiteListEntry`. This model holds a whitelist authorizing an ONU. The mac address authentication is implemented as package A and the IEEE802.1X authentication is implemented as package B. It is also possible to specify the range of the port number where the OLT is inserted. 
    - `owner`. Relation to the NttWorkflowDriverService that owns this whitelist entry.
    - `mac_address`. MAC address of ONU.
    - `pon_port_from`. Starting port number where OLT insertion is allowed. 
    - `pon_port_to`. Last port number where OLT insertion is allowed.

## Example Tosca - Create a whitelist entry

```yaml
tosca_definitions_version: tosca_simple_yaml_1_0
imports:
  - custom_types/nttworkflowdriverwhitelistentry.yaml
  - custom_types/nttworkflowdriverservice.yaml
description: Create an entry in the whitelist
topology_template:
  node_templates:

    service#nttworkflow:
      type: tosca.nodes.NttWorkflowDriverService
      properties:
        name: ntt-workflow-driver
        must-exist: true

    whitelist:
      type: tosca.nodes.NttWorkflowDriverWhiteListEntry
      properties:
        mac_address: 0a0a0a0a0a0a
        pon_port_from: 536870912
        pon_port_to: 536870915
      requirements:
        - owner:
            node: service#nttworkflow
            relationship: tosca.relationships.BelongsToOne
```

## Integration with other Services

This service integrates closely with the `R-CORD` and `vOLT` services, directly manipulating models (`RCORDSubscriber`, `ONUDevice`, `TechnologyProfile`) in those services.

## Synchronizer Workflows

This synchronizer implements only event_steps and model_policies. It's job is to listen for events and execute a state machine associated with those events. Service Instances are created automatically when ONU events are received. As the state machine changes various states for authentication, etc., those changes will be propagated to the appropriate objects in the `R-CORD` and `vOLT` services.

### Model Policy: NttWorkflowDriverServiceInstancePolicy

This model policy is responsible for reacting to state changes that are caused by various event steps, implementing the state machine described above.

### Event Step: ONUEventStep

Listens on `onu.events` and updates the `onu_state` of `NttWorkflowDriverServiceInstance`. Listens on `authentication events` and updates the authentication_state fields of `NttWorkflowDriverServiceInstance`. Automatically creates `NttWorkflowDriverServiceInstance` and `NttWorkflowDriverOltInformation` as necessary.

## Events format

This events are generated by various applications running on top of ONOS and published on a Kafka bus.
Here is the structure of the events and their topics.

### onu.events

```json
{
  "timestamp": "2018-09-11T01:00:49.506Z",
  "status": "activated", // or disabled
  "serialNumber": "ALPHe3d1cfde", // ONU serial number
  "portNumber": "16", // uni port
  "deviceId": "of:000000000a5a0072" // OLT OpenFlow Id
}
```

### authentication.events

```json
{
  "timestamp": "2018-09-11T00:41:47.483Z",
  "deviceId": "of:000000000a5a0072", // OLT OpenFlow Id
  "portNumber": "16", // uni port
  "serialNumber": "ALPHe3d1cfde", // ONU serial number
  "authenticationState": "STARTED" // REQUESTED, APPROVED, DENIED
}
```