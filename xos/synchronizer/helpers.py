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
from xossynchronizer.steps.syncstep import DeferredException
import time
import requests
from requests.auth import HTTPBasicAuth

class NttHelpers():
    @staticmethod
    def validate_onu(model_accessor, log, ntt_si):
        """
        This method validate an ONU against the whitelist and set the appropriate state.
        It's expected that the deferred exception is managed in the caller method,
        for example a model_policy or a sync_step.

        :param ntt_si: NttWorkflowDriverServiceInstance
        :return: [boolean, string]
        """
        tech_value = json.loads(model_accessor.TechnologyProfile.objects.get(profile_id=64).profile_value)
        if tech_value["profile_type"] == "EPON":
            tech = tech_value["epon_attribute"]["package_type"]
        else:
            tech = tech_value["profile_type"]
              
        oss_service = ntt_si.owner.leaf_model

        # See if there is a matching entry in the whitelist.
        matching_entries = model_accessor.NttWorkflowDriverWhiteListEntry.objects.filter(
            owner_id=oss_service.id,
        )
        
        matching_entries = [e for e in matching_entries if e.mac_address.lower() == ntt_si.mac_address.lower()]
        
        if len(matching_entries) == 0:
            log.warn("ONU not found in whitelist")
            return [False, "ONU not found in whitelist"]

        whitelisted = matching_entries[0]
        try:
            onu = model_accessor.ONUDevice.objects.get(serial_number=ntt_si.serial_number.split("-")[0])
            pon_port = onu.pon_port
        except IndexError:
            raise DeferredException("ONU device %s is not know to XOS yet" % ntt_si.serial_number)

        if onu.admin_state == "ADMIN_DISABLED":
            return [False, "ONU has been manually disabled"]

        if pon_port.port_no < whitelisted.pon_port_from or pon_port.port_no > whitelisted.pon_port_to:
            log.warn("PON port is not approved.")
            return [False, "PON port is not approved."]
        
        if tech == "B":
            if ntt_si.authentication_state == "DENIED":
                return [False, "IEEE802.1X authentication has not been denied."]
            elif ntt_si.authentication_state != "APPROVED":
                return [True, "IEEE802.1X authentication has not been done yet."]
        else:
            ntt_si.authentication_state = "APPROVED"

        log.debug("Adding subscriber with info",
            uni_port_id = ntt_si.uni_port_id,
            dp_id = ntt_si.of_dpid
        )
        
        time.sleep(180)

        onos_voltha_basic_auth = HTTPBasicAuth("karaf", "karaf")

        handle = "%s/%s" % (ntt_si.of_dpid, ntt_si.uni_port_id)
        # TODO store URL and PORT in the vOLT Service model
        full_url = "http://129.60.110.180:8181/onos/olt/oltapp/%s" % (handle)

        log.info("Sending request to onos-voltha", url=full_url)

        request = requests.post(full_url, auth=onos_voltha_basic_auth)

        if request.status_code != 200:
            raise Exception("Failed to add subscriber in onos-voltha: %s" % request.text)
        log.info("Added Subscriber in onos voltha", response=request.text)

        return [True, "ONU has been validated"]

    @staticmethod
    def find_or_create_ntt_si(model_accessor, log, event):
        try:
            ntt_si = model_accessor.NttWorkflowDriverServiceInstance.objects.get(
                serial_number=event["serialNumber"]
            )
            try:
                onu = model_accessor.ONUDevice.objects.get(serial_number=event["serialNumber"].split("-")[0])
                ntt_si.mac_address = onu.mac_address
            except IndexError:
                log.debug("NttHelpers: ONU has been deleted", si=ntt_si)
            log.debug("NttHelpers: Found existing NttWorkflowDriverServiceInstance", si=ntt_si)
        except IndexError:
            # create an NttWorkflowDriverServiceInstance, the validation will be
            # triggered in the corresponding sync step
            while True:
                try:
                    onu = model_accessor.ONUDevice.objects.get(serial_number=event["serialNumber"].split("-")[0])
                    break
                except IndexError:
                    time.sleep(1)
                    continue

            ntt_si = model_accessor.NttWorkflowDriverServiceInstance(
                serial_number=event["serialNumber"],
                of_dpid=event["deviceId"],
                uni_port_id=long(event["portNumber"]),
                mac_address=onu.mac_address,
                # we assume there is only one NttWorkflowDriverService
                owner=model_accessor.NttWorkflowDriverService.objects.first()
            )
            log.debug("NttHelpers: Created new NttWorkflowDriverServiceInstance", si=ntt_si)
        return ntt_si

    @staticmethod
    def find_or_create_ntt_oi(model_accessor, log, event):
        try:
            ntt_oi = model_accessor.NttWorkflowDriverOltInformation.objects.get(
                of_dpid=event["deviceId"]
            )
            try:
                onu = model_accessor.ONUDevice.objects.get(serial_number=event["serialNumber"].split("-")[0])
                ntt_oi.port_no = onu.pon_port.port_no
                tech_value = json.loads(model_accessor.TechnologyProfile.objects.get(profile_id=64).profile_value)
                if tech_value["profile_type"] == "EPON":
                    tech = tech_value["epon_attribute"]["package_type"]
                else:
                    tech = tech_value["profile_type"]
                ntt_oi.olt_package = tech
            except IndexError:
                log.debug("NttHelpers: ONU has been deleted", oi=ntt_oi)
            log.debug("NttHelpers: Found existing NttWorkflowDriverOltInformation", oi=ntt_oi)
        except IndexError:
            while True:
                try:
                    onu = model_accessor.ONUDevice.objects.get(serial_number=event["serialNumber"].split("-")[0])
                    break
                except IndexError:
                    time.sleep(1)
                    continue

            tech_value = json.loads(model_accessor.TechnologyProfile.objects.get(profile_id=64).profile_value)
            if tech_value["profile_type"] == "EPON":
                tech = tech_value["epon_attribute"]["package_type"]
            else:
                tech = tech_value["profile_type"]

            pon_port = onu.pon_port
            ntt_oi = model_accessor.NttWorkflowDriverOltInformation(
                of_dpid=event["deviceId"],
                olt_package=tech,
                port_no=pon_port.port_no,
                owner=model_accessor.NttWorkflowDriverService.objects.first()
            )
            log.debug("NttHelpers: Created new NttWorkflowDriverOltInformation", oi=ntt_oi)
        return ntt_oi