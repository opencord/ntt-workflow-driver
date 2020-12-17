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


class NttWorkflowDriverWhiteListEntryPolicy(Policy):
    model_name = "NttWorkflowDriverWhiteListEntry"

    def handle_create(self, whitelist):
        self.handle_update(whitelist)

    # Update the SI if the onu_state has changed.
    # The SI model policy will take care of updating other state.
    def validate_onu_state(self, si):
        [valid, message] = NttHelpers.validate_onu(self.model_accessor, self.logger, si)
        if valid:
            si.admin_onu_state = "ENABLED"
        else:
            si.admin_onu_state = "DISABLED"

        self.logger.debug(
            "MODEL_POLICY: activating NttWorkflowDriverServiceInstance because of change in the whitelist",
            si=si,
            onu_state=si.admin_onu_state,
            authentication_state=si.authentication_state)

        si.status_message = message
        si.save_changed_fields(always_update_timestamp=True)

    def handle_update(self, whitelist):
        self.logger.debug("MODEL_POLICY: handle_update for NttWorkflowDriverWhiteListEntry", whitelist=whitelist)

        sis = self.model_accessor.NttWorkflowDriverServiceInstance.objects.all()

        for si in sis:

            if si.mac_address.lower() != whitelist.mac_address.lower():
                # NOTE we don't care about this SI as it has a different serial number
                continue

            self.validate_onu_state(si)

        whitelist.backend_need_delete_policy = True
        whitelist.save_changed_fields()

    def handle_delete(self, whitelist):
        self.logger.debug(
            "MODEL_POLICY: handle_delete for NttWorkflowDriverWhiteListEntry")

        # BUG: Sometimes the delete policy is not called, because the reaper deletes

        assert(whitelist.owner)

        sis = self.model_accessor.NttWorkflowDriverServiceInstance.objects.all()
        sis = [si for si in sis if si.mac_address.lower() == whitelist.mac_address.lower()]

        for si in sis:
            self.validate_onu_state(si)

        whitelist.backend_need_reap = True
        whitelist.save_changed_fields()
