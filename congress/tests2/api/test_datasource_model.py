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

import mock

from oslo_config import cfg
cfg.CONF.distributed_architecture = True

from congress.api import datasource_model
from congress.api import webservice
from congress import exception
from congress.tests import base
from congress.tests import helper
from congress.tests2.api import base as api_base
from congress.datasources import nova_driver

import novaclient.client


class TestDatasourceModel(base.SqlTestCase):
    @mock.patch.object(novaclient.client, 'Client')
    def setUp(self, client_mock):
        super(TestDatasourceModel, self).setUp()
        self.datasource_model = datasource_model.DatasourceModel(
            'test_datasource', policy_engine='engine')
        fake_config = {'auth_url': 'foo', 'username': 'armax', 'password':'aa',
                       'tenant_name': 'armax'}
        self.nova_driver = nova_driver.NovaDriver('nova', args=fake_config)
        self.config = api_base.setup_config([self.datasource_model,
                                             self.nova_driver])
        self.data = self.config['data']
        self.node = self.config['node']
        self.engine = self.config['engine']
        self.datasource = self._get_datasource_request()
        self.node.add_datasource(self.datasource)

    def tearDown(self):
        super(TestDatasourceModel, self).tearDown()
        self.node.stop()
        self.node.start()

    def _get_datasource_request(self):
        # leave ID out--generated during creation
        return {'name': 'datasource1',
                'driver': 'fake_datasource',
                'description': 'hello world!',
                'enabled': True,
                'type': None,
                'config': {'auth_url': 'foo',
                           'username': 'armax',
                           'password': '<hidden>',
                           'tenant_name': 'armax'}}

    def test_get_items(self):
        dinfo = self.datasource_model.get_items(None)['results']
        self.assertEqual(1, len(dinfo))
        datasource2 = self._get_datasource_request()
        datasource2['name'] = 'datasource2'
        self.node.add_datasource(datasource2)
        dinfo = self.datasource_model.get_items(None)['results']
        self.assertEqual(2, len(dinfo))
        del dinfo[0]['id']
        self.assertEqual(self.datasource, dinfo[0])

    def test_add_item(self):
        datasource3 = self._get_datasource_request()
        datasource3['name'] = 'datasource-test-3'
        self.datasource_model.add_item(datasource3, {})
        obj = self.engine.policy_object('datasource-test-3')
        self.assertIsNotNone(obj.schema)
        self.assertEqual('datasource-test-3', obj.name)

    def test_add_item_duplicate(self):
        self.assertRaises(webservice.DataModelException,
                          self.datasource_model.add_item,
                          self.datasource, {})

    def test_delete_item(self):
        datasource = self._get_datasource_request()
        datasource['name'] = 'test-datasource'
        d_id, dinfo = self.datasource_model.add_item(datasource, {})
        self.assertTrue(self.engine.assert_policy_exists('test-datasource'))
        context = {'ds_id': d_id}
        self.datasource_model.delete_item(None, {}, context=context)
        self.assertRaises(exception.PolicyRuntimeException,
                          self.engine.assert_policy_exists, 'test-datasource')
        self.assertRaises(exception.DatasourceNotFound,
                          self.node.get_datasource, d_id)

    def test_delete_item_invalid_datasource(self):
        context = {'ds_id': 'fake'}
        self.assertRaises(webservice.DataModelException,
                          self.datasource_model.delete_item,
                          None, {}, context=context)

    def test_execute_action(self):
        def _execute_api(client, action, action_args):                          
            LOG.info("_execute_api called on %s and %s", action, action_args)   
            positional_args = action_args['positional']                         
            named_args = action_args['named']                                   
            method = reduce(getattr, action.split('.'), client)                 
            method(*positional_args, **named_args)                              
                                                                                
        class NovaClient(object):                                               
            def __init__(self, testkey):                                        
                self.testkey = testkey                                          
                                                                                
            def _get_testkey(self):                                             
                return self.testkey                                             
                                                                                
            def disconnectNetwork(self, arg1, arg2, arg3):                      
                self.testkey = "arg1=%s arg2=%s arg3=%s" % (arg1, arg2, arg3)   
                                                                                
        nova_client = NovaClient("testing")                                     
        nova = self.cage.service_object('nova')                                 
        nova._execute_api = _execute_api                                        
        nova.nova_client = nova_client                                          
                                                                                
        api = self.api                                                          
        body = {'name': 'nova:disconnectNetwork',                               
                'args': {'positional': ['value1', 'value2'],                    
                         'named': {'arg3': 'value3'}}}                          
                                                                                

        context = {'ds_id': self.data.service_id}
        body = {'name': 'fake_act',                                           
                'args': {'positional': ['value1', 'value2'],                    
                         'named': {'name': 'value3'}}}
        request = helper.FakeRequest(body)
        result = self.datasource_model.execute_action({}, context, request)
        

# TODO(ramineni): Migrate request_refresh and exeucte_action tests
