
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


from helpers import NttHelpers
from xossynchronizer.model_policies.policy import Policy

import os
import sys

sync_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
sys.path.append(sync_path)


class DeferredException(Exception):
    pass


class NttWorkflowDriverServiceInstancePolicy(Policy):
    model_name = "NttWorkflowDriverServiceInstance"

    def handle_create(self, si):
        self.logger.debug("MODEL_POLICY: handle_create for NttWorkflowDriverServiceInstance %s " % si.id)
        self.handle_update(si)

    def handle_update(self, si):
        self.logger.debug("MODEL_POLICY: handle_update for NttWorkflowDriverServiceInstance %s " %
                          (si.id), onu_state=si.admin_onu_state, authentication_state=si.authentication_state)
        self.process_onu_state(si)
        si.save_changed_fields()

    # Check the whitelist to see if the ONU is valid.  If it is, make sure that it's enabled.
    def process_onu_state(self, si):
        [valid, message] = NttHelpers.validate_onu(self.model_accessor, self.logger, si)
        si.status_message = message
        if valid:
            si.admin_onu_state = "ENABLED"
            self.update_onu(si.serial_number, "ENABLED")
            if si.authentication_state == '':
                si.authentication_state = "APPROVED"
        else:
            si.admin_onu_state = "DISABLED"
            self.update_onu(si.serial_number, "DISABLED")
            si.authentication_state = "DENIED"

    def update_onu(self, serial_number, admin_state):
        onu = [onu for onu in self.model_accessor.ONUDevice.objects.all()
               if onu.serial_number.lower() == serial_number.lower().split('-')[0]][0]
        if onu.admin_state == "ADMIN_DISABLED":
            self.logger.debug(
                "MODEL_POLICY: ONUDevice [%s] has been manually disabled, not changing state to %s" %
                (onu.serial_number, admin_state))
            return
        if onu.admin_state == admin_state:
            self.logger.debug(
                "MODEL_POLICY: ONUDevice [%s] already has admin_state to %s" %
                (onu.serial_number, admin_state))
        else:
            self.logger.debug("MODEL_POLICY: setting ONUDevice [%s] admin_state to %s" % (onu.serial_number, admin_state))
            onu.admin_state = admin_state
            onu.save_changed_fields(always_update_timestamp=True)

    def handle_delete(self, si):
        pass
