# Copyright (c) 2016 NEC Corp. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
import json
import six

from oslo_config import cfg
from oslo_db import exception as db_exc
from oslo_log import log as logging
from oslo_utils import importutils
from oslo_utils import strutils
from oslo_utils import uuidutils

from congress.api import base as api_base
from congress.datasources import constants
from congress.db import datasources as datasources_db
from congress.dse2 import data_service
from congress import exception

LOG = logging.getLogger(__name__)


class DSManager(data_service.DataService):
    """A proxy service to datasource managing methods in dse_node."""

    loaded_drivers = {} 
    DS_MANAGER_SERVICE_ID = '_ds_manager'

    def __init__(self):
        super(DSManager, self).__init__(self.DS_MANAGER_SERVICE_ID)
        self.add_rpc_endpoint(DSManagerEndpoints(self))

    @classmethod
    def create_datasource_service(cls, datasource):
        """Create a new DataService on this node.

        :param name is the name of the service.  Must be unique across all
               services
        :param classPath is a string giving the path to the class name, e.g.
               congress.datasources.fake_datasource.FakeDataSource
        :param args is the list of arguments to give the DataService
               constructor
        :param type_ is the kind of service
        :param id_ is an optional parameter for specifying the uuid.
        """
        # get the driver info for the datasource
        ds_dict = cls.make_datasource_dict(datasource)
        if not ds_dict['enabled']:
            LOG.info("datasource %s not enabled, skip loading",
                     ds_dict['name'])
            return

        driver_info = cls.get_driver_info(ds_dict['driver'])
        # split class_path into module and class name
        class_path = driver_info['module']
        pieces = class_path.split(".")
        module_name = ".".join(pieces[:-1])
        class_name = pieces[-1]

        if ds_dict['config'] is None:
            args = {'ds_id': ds_dict['id']}
        else:
            args = dict(ds_dict['config'], ds_id=ds_dict['id'])
        kwargs = {'name': ds_dict['name'], 'args': args}
        LOG.info("creating service %s with class %s and args %s",
                 ds_dict['name'], module_name,
                 strutils.mask_password(kwargs, "****"))

        try:
            module = importutils.import_module(module_name)
            service = getattr(module, class_name)(**kwargs)
        except Exception:
            msg = ("Error loading instance of module '%s'")
            LOG.exception(msg, class_path)
            raise exception.DataServiceError(msg % class_path)
        return service

    @classmethod
    def validate_create_datasource(cls, req):
        driver = req['driver']
        config = req['config'] or {}
        for loaded_driver in cls.loaded_drivers.values():
            if loaded_driver['id'] == driver:
                specified_options = set(config.keys())
                valid_options = set(loaded_driver['config'].keys())
                # Check that all the specified options passed in are
                # valid configuration options that the driver exposes.
                invalid_options = specified_options - valid_options
                if invalid_options:
                    raise exception.InvalidDriverOption(
                        invalid_options=invalid_options)

                # check that all the required options are passed in
                required_options = set(
                    [k for k, v in loaded_driver['config'].items()
                     if v == constants.REQUIRED])
                missing_options = required_options - specified_options
                if missing_options:
                    missing_options = ', '.join(missing_options)
                    raise exception.MissingRequiredConfigOptions(
                        missing_options=missing_options)
                return loaded_driver

        # If we get here no datasource driver match was found.
        raise exception.InvalidDriver(driver=req)

    def delete_missing_driver_datasources(self):
        removed = 0
        for datasource in datasources_db.get_datasources():
            try:
                self.get_driver_info(datasource.driver)
            except exception.DriverNotFound:
                ds_dict = self.make_datasource_dict(datasource)
                self.delete_datasource(ds_dict)
                removed = removed+1
                LOG.debug("Deleted datasource with config %s ",
                          strutils.mask_password(ds_dict))

        LOG.info("Datsource cleanup completed, removed %d datasources",
                 removed)

    @classmethod
    def make_datasource_dict(cls, req, fields=None):
        result = {'id': req.get('id') or uuidutils.generate_uuid(),
                  'name': req.get('name'),
                  'driver': req.get('driver'),
                  'description': req.get('description'),
                  'type': None,
                  'enabled': req.get('enabled', True)}
        # NOTE(arosen): we store the config as a string in the db so
        # here we serialize it back when returning it.
        if isinstance(req.get('config'), six.string_types):
            result['config'] = json.loads(req['config'])
        else:
            result['config'] = req.get('config')

        return cls._fields(result, fields)

    @classmethod
    def _fields(self, resource, fields):
        if fields:
            return dict(((key, item) for key, item in resource.items()
                         if key in fields))
        return resource

    @classmethod
    def load_drivers(cls):
        """Load all configured drivers and check no name conflict"""
        result = {}
        for driver_path in cfg.CONF.drivers:
            # Note(thread-safety): blocking call?
            obj = importutils.import_class(driver_path)
            driver = obj.get_datasource_info()
            if driver['id'] in result:
                raise exception.BadConfig(_("There is a driver loaded already"
                                          "with the driver name of %s")
                                          % driver['id'])
            driver['module'] = driver_path
            result[driver['id']] = driver
        cls.loaded_drivers = result

    @classmethod
    def get_driver_info(cls, driver):
        driver = cls.loaded_drivers.get(driver)
        if not driver:
            raise exception.DriverNotFound(id=driver)
        return driver

    @classmethod
    def get_drivers_info(cls):
        return cls.loaded_drivers

    @classmethod
    def get_driver_schema(cls, drivername):
        driver = cls.get_driver_info(drivername)
        # Note(thread-safety): blocking call?
        obj = importutils.import_class(driver['module'])
        return obj.get_schema()

    # Note(thread-safety): blocking function
    def add_datasource(self, item, deleted=False, update_db=True):
        req = self.make_datasource_dict(item)

        # check the request has valid information
        self.validate_create_datasource(req)
        if (len(req['name']) == 0 or req['name'][0] == '_'):
            raise exception.InvalidDatasourceName(value=req['name'])

        new_id = req['id']
        LOG.debug("adding datasource %s", req['name'])
        if update_db:
            LOG.debug("updating db")
            try:
                # Note(thread-safety): blocking call
                datasource = datasources_db.add_datasource(
                    id_=req['id'],
                    name=req['name'],
                    driver=req['driver'],
                    config=req['config'],
                    description=req['description'],
                    enabled=req['enabled'])
            except db_exc.DBDuplicateEntry:
                raise exception.DatasourceNameInUse(value=req['name'])
            except db_exc.DBError:
                LOG.exception('Creating a new datasource failed.')
                raise exception.DatasourceCreationError(value=req['name'])

        new_id = datasource['id']
        try:
            self.node.synchronize_datasources()
            # immediate synch policies on local PE if present
            # otherwise wait for regularly scheduled synch
            # TODO(dse2): use finer-grained method to synch specific policies
            engine = self.node.service_object(api_base.ENGINE_SERVICE_ID)
            if engine is not None:
                engine.synchronize_policies()
            # TODO(dse2): also broadcast to all PE nodes to synch
        except exception.DataServiceError:
            LOG.exception('the datasource service is already '
                          'created in the node')
        except Exception:
            LOG.exception(
                'Unexpected exception encountered while registering '
                'new datasource %s.', req['name'])
            if update_db:
                datasources_db.delete_datasource(req['id'])
            msg = ("Datasource service: %s creation fails." % req['name'])
            raise exception.DatasourceCreationError(message=msg)

        new_item = dict(item)
        new_item['id'] = new_id
        return self.node.make_datasource_dict(new_item)

    # Note(thread-safety): blocking function
    def delete_datasource(self, datasource, update_db=True):
        LOG.debug("Deleting %s datasource ", datasource['name'])
        datasource_id = datasource['id']
        if update_db:
            # Note(thread-safety): blocking call
            result = datasources_db.delete_datasource_with_data(datasource_id)
            if not result:
                raise exception.DatasourceNotFound(id=datasource_id)

        # Note(thread-safety): blocking call
        try:
            self.node.synchronize_datasources()
        except Exception:
            msg = ('failed to synchronize_datasource after '
                   'deleting datasource: %s' % datasource_id)
            LOG.exception(msg)
            raise exception.DataServiceError(msg)

    @classmethod
    def get_datasource(cls, id_):
        """Return the created datasource."""
        # Note(thread-safety): blocking call
        result = datasources_db.get_datasource(id_)
        if not result:
            raise exception.DatasourceNotFound(id=id_)
        return cls.make_datasource_dict(result)

    @classmethod
    def get_datasources(cls, filter_secret=False):
        """Return the created datasources as recorded in the DB.

        This returns what datasources the database contains, not the
        datasources that this server instance is running.
        """
        results = []
        for datasource in datasources_db.get_datasources():
            result = cls.make_datasource_dict(datasource)
            if filter_secret:
                # driver_info knows which fields should be secret
                driver_info = cls.get_driver_info(result['driver'])
                try:
                    for hide_field in driver_info['secret']:
                        result['config'][hide_field] = "<hidden>"
                except KeyError:
                    pass
            results.append(result)
        return results


class DSManagerEndpoints(object):
    def __init__(self, service):
        self.service = service

    def add_datasource(self, context, items):
        return self.service.add_datasource(items)

    def delete_datasource(self, context, datasource):
        return self.service.delete_datasource(datasource)

