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

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from congress.api import webservice
from congress.tests.api import base as api_base
from congress.tests import base


class TestDriverModel(base.SqlTestCase):
    def setUp(self):
        super(TestDriverModel, self).setUp()
        services = api_base.setup_config()
        self.node = services['node']
        self.ds_manager = services['ds_manager']

        self.ds_manager.add_datasource(self._get_datasource_request())
        self.driver_model = services['api']['api-system']

    def _get_datasource_request(self):
        req = {'driver': 'fake_datasource',
               'name': 'fake_datasource'}
        req['config'] = {'auth_url': 'foo',
                         'username': 'foo',
                         'password': 'password',
                         'tenant_name': 'foo'}
        return req

    def tearDown(self):
        super(TestDriverModel, self).tearDown()

    def test_drivers_list(self):
        context = {}
        expected_ret = {"results": [
            {
                "description": "This is a fake driver used for testing",
                "id": "fake_datasource"
            }
        ]}

        ret = self.driver_model.get_items({}, context)
        self.assertEqual(expected_ret, ret)

    def test_driver_details(self):
        context = {
            "driver_id": "fake_datasource"
        }
        expected_ret = {
            "config": {
                "auth_url": "required",
                "endpoint": "(optional)",
                "password": "required",
                "poll_time": "(optional)",
                "region": "(optional)",
                "project_name": "(optional)",
                "tenant_name": "required",
                "username": "required"
            },
            "description": "This is a fake driver used for testing",
            "id": "fake_datasource",
            "module": "congress.tests.fake_datasource.FakeDataSource",
            "secret": ["password"],
            "tables": [{'columns': [
                {'description': None, 'name': 'id'},
                {'description': None, 'name': 'name'}],
                'table_id': 'fake_table'}
            ]
        }

        ret = self.driver_model.get_item('fake_datasource', {}, context)
        self.assertEqual(expected_ret, ret)

    def test_invalid_driver_details(self):
        context = {
            "driver_id": "invalid-id"
        }
        self.assertRaises(webservice.DataModelException,
                          self.driver_model.get_item,
                          'invalid-id', {}, context)
