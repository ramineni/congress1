# Copyright (c) 2015 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
from oslo_config import cfg
from oslo_utils import uuidutils

from congress.api import datasource_model
from congress.api import webservice
from congress import harness
from congress.managers import datasource
from congress.tests import base
from congress.tests import helper


class TestDatasourceModel(base.SqlTestCase):
    def setUp(self):
        super(TestDatasourceModel, self).setUp()
        # Here we load the fake driver
        cfg.CONF.set_override(
            'drivers',
            ['congress.tests.fake_datasource.FakeDataSource'])

        self.cage = harness.create(helper.root_path())
        self.engine = self.cage.service_object('engine')
        self.ds_model = datasource_model.DatasourceModel("datasource_model", {},
                                                         policy_engine=self.engine)

        self._add_test_datasource()

    def tearDown(self):
        super(TestDatasourceModel, self).tearDown()

    @mock.patch.object(datasource.DataSourceManager, 'get_driver_info')
    def _add_test_datasource(self, driver_info_mock):
        test_ds1 = {
            "name": "test-datasource",
            "driver": 'nova',
            "description": "test description",
            "type": "fake-type",
            "config": {},
        }

        test_policy_id, obj = self.ds_model.add_item(test_ds1, {})
        test_ds1["id"] = test_policy_id

        test_ds2 = {
            "name": "test-ds2",
            "description": "neutronv2",
            "type": "fake",
            "config": "my_config"
        }

        test_policy_id, obj = self.ds_model.add_item(test_ds2, {})
        test_ds2["id"] = test_policy_id

#        self.policy = test_policy
 #       self.policy2 = test_policy2

    @mock.patch.object(datasource.DataSourceManager, 'get_datasources')
    def test_get_items(self, get_info_mock):
        get_info_mock.return_value = [{'name': 'ds1', 'driver': 'neutron'},
                                      {'name': 'ds2', 'driver': 'nova'}]

        ret = self.ds_model.get_items({})
        get_info_mock.assert_called_once_with(filter_secret=True)
        self.assertEqual(2, len(ret['results']))
        self.assertIn('id', ret['results'][0])

    def test_add_item(self):
        pass
