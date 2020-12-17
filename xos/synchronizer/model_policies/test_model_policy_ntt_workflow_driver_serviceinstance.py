
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


import unittest
from mock import patch

import os
import sys

test_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class TestModelPolicyNttWorkflowDriverServiceInstance(unittest.TestCase):
    def setUp(self):

        self.sys_path_save = sys.path

        config = os.path.join(test_path, "../test_config.yaml")
        from xosconfig import Config
        Config.clear()
        Config.init(config, 'synchronizer-config-schema.yaml')

        from xossynchronizer.mock_modelaccessor_build import mock_modelaccessor_config
        mock_modelaccessor_config(test_path, [("ntt-workflow-driver", "ntt-workflow-driver.xproto"),
                                              ("olt-service", "volt.xproto"),
                                              ("rcord", "rcord.xproto")])

        import xossynchronizer.modelaccessor
        import mock_modelaccessor
        reload(mock_modelaccessor)  # in case nose2 loaded it in a previous test
        reload(xossynchronizer.modelaccessor)      # in case nose2 loaded it in a previous test

        from xossynchronizer.modelaccessor import model_accessor
        from model_policy_ntt_workflow_driver_serviceinstance import NttWorkflowDriverServiceInstancePolicy, NttHelpers
        self.NttHelpers = NttHelpers

        # import all class names to globals
        for (k, v) in model_accessor.all_model_classes.items():
            globals()[k] = v

        # Some of the functions we call have side-effects. For example, creating a VSGServiceInstance may lead to
        # creation of tags. Ideally, this wouldn't happen, but it does. So make sure we reset the world.
        model_accessor.reset_all_object_stores()

        self.policy = NttWorkflowDriverServiceInstancePolicy(model_accessor=model_accessor)
        self.si = NttWorkflowDriverServiceInstance()
        self.si.owner = NttWorkflowDriverService()
        self.si.serial_number = "BRCM1234"

    def tearDown(self):
        sys.path = self.sys_path_save

    def test_update_onu(self):

        onu = ONUDevice(
            serial_number="BRCM1234",
            admin_state="ENABLED"
        )
        with patch.object(ONUDevice.objects, "get_items") as get_onu, \
                patch.object(onu, "save") as onu_save:
            get_onu.return_value = [onu]

            self.policy.update_onu("brcm1234", "ENABLED")
            onu_save.assert_not_called()

            self.policy.update_onu("brcm1234", "DISABLED")
            self.assertEqual(onu.admin_state, "DISABLED")
            onu_save.assert_called_with(
                always_update_timestamp=True, update_fields=[
                    'admin_state', 'serial_number', 'updated'])

    def test_enable_onu(self):
        with patch.object(self.NttHelpers, "validate_onu") as validate_onu, \
                patch.object(self.policy, "update_onu") as update_onu:
            validate_onu.return_value = [True, "valid onu"]

            self.policy.process_onu_state(self.si)

            update_onu.assert_called_once()
            update_onu.assert_called_with("BRCM1234", "ENABLED")

            self.assertIn("valid onu", self.si.status_message)

    def test_disable_onu(self):
        with patch.object(self.NttHelpers, "validate_onu") as validate_onu, \
                patch.object(self.policy, "update_onu") as update_onu:
            validate_onu.return_value = [False, "invalid onu"]

            self.policy.process_onu_state(self.si)

            update_onu.assert_called_once()
            update_onu.assert_called_with("BRCM1234", "DISABLED")

            self.assertIn("invalid onu", self.si.status_message)

    def test_handle_update_validate_onu(self):
        """
        Testing that handle_update calls validate_onu with the correct parameters
        when necessary
        """
        with patch.object(self.policy, "process_onu_state") as process_onu_state, \
                patch.object(self.policy, "update_onu") as update_onu:
            update_onu.return_value = None

            self.si.admin_onu_state = "AWAITING"
            self.si.oper_onu_status = "AWAITING"
            self.policy.handle_update(self.si)
            process_onu_state.assert_called_with(self.si)

            self.si.admin_onu_state = "ENABLED"
            self.si.oper_onu_status = "ENABLED"
            self.policy.handle_update(self.si)
            process_onu_state.assert_called_with(self.si)

            self.si.admin_onu_state = "DISABLED"
            self.si.oper_onu_status = "DISABLED"
            self.policy.handle_update(self.si)
            process_onu_state.assert_called_with(self.si)

if __name__ == '__main__':
    sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
    unittest.main()
