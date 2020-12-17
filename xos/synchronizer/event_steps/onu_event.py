
# Copyright 2020-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import json
from xossynchronizer.event_steps.eventstep import EventStep
from helpers import NttHelpers
import requests
from requests.auth import HTTPBasicAuth

class ONUEventStep(EventStep):
    topics = ["onu.events"]
    technology = "kafka"

    max_onu_retry = 50

    def __init__(self, *args, **kwargs):
        super(ONUEventStep, self).__init__(*args, **kwargs)

    def process_event(self, event):
        value = json.loads(event.value)
        self.log.info("onu.events: received event", value=value)
        # This is needed to be compatible with both Voltha 1.7 and Voltha 2.x
        # It supposes to have only 1 subscriber per ONU and the subscriber is connected to the first port
        if "-" in value["serialNumber"] and not value["serialNumber"].endswith("-1"):
            self.log.info("Skip event, only consider [serialNumber]-1 events")
            return

        ntt_oi = NttHelpers.find_or_create_ntt_oi(self.model_accessor, self.log, value)
        ntt_oi.no_sync = False
        ntt_oi.of_dpid = value["deviceId"]
        ntt_oi.save_changed_fields(always_update_timestamp=True)
        ntt_si = NttHelpers.find_or_create_ntt_si(self.model_accessor, self.log, value)
        if value["status"] == "activated":
            self.log.info("onu.events: activated onu", value=value)
            ntt_si.no_sync = False
            ntt_si.uni_port_id = long(value["portNumber"])
            ntt_si.of_dpid = value["deviceId"]
            ntt_si.oper_onu_status = "ENABLED"
            ntt_si.save_changed_fields(always_update_timestamp=True)
        elif value["status"] == "disabled":
            self.log.info("onu.events: disabled onu, resetting the subscriber", value=value)
            ntt_si.oper_onu_status = "DISABLED"
            ntt_si.save_changed_fields(always_update_timestamp=True)
            
            log.debug("Removing subscriber with info",
                uni_port_id = ntt_si.uni_port_id,
                dp_id = ntt_si.of_dpid
            )

            onos_voltha_basic_auth = HTTPBasicAuth("karaf", "karaf")

            handle = "%s/%s" % (ntt_si.of_dpid, ntt_si.uni_port_id)
            # TODO store URL and PORT in the vOLT Service model
            full_url = "http://129.60.110.180:8181/onos/olt/oltapp/%s" % (handle)

            log.info("Sending request to onos-voltha", url=full_url)

            request = requests.delete(full_url, auth=onos_voltha_basic_auth)

            if request.status_code != 204:
                raise Exception("Failed to remove subscriber from onos-voltha: %s" % request.text)

            log.info("Removed Subscriber from onos voltha", response=request.text)

            return
        else:
            self.log.warn("onu.events: Unknown status value: %s" % value["status"], value=value)
            return