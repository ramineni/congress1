#! /usr/bin/python
#
# Copyright (c) 2014 VMware, Inc. All rights reserved.
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

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import socket
import sys

import eventlet
eventlet.monkey_patch()
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import service

from congress.common import config
# FIXME It has to initialize distributed_architecture flag basing on the
# config file before the python interpreter imports python file which has
# if-statement for deepsix. Since the default value of the flag is False
# in current implementation, so it will import dse.deepsix as deepsix
# even if you set it to True in congress.conf.
# After changing the default to True, remove following one line and unncoment
# "Initialize config here!!"
config.init(sys.argv[1:])
from congress.common import eventlet_server

LOG = logging.getLogger(__name__)


class ServerWrapper(object):
    """Wraps an eventlet_server with some launching info & capabilities."""

    def __init__(self, server, workers):
        self.server = server
        self.workers = workers

    def launch_with(self, launcher):
        if hasattr(self.server, 'listen'):
            self.server.listen()
        if self.workers > 1:
            # Use multi-process launcher
            launcher.launch_service(self.server, self.workers)
        else:
            # Use single process launcher
            launcher.launch_service(self.server)


def create_api_server(conf_path, name, host, port, workers, policy_engine):
    congress_api_server = eventlet_server.APIServer(
        conf_path, name, host=host, port=port,
        keepalive=cfg.CONF.tcp_keepalive,
        keepidle=cfg.CONF.tcp_keepidle,
        policy_engine=policy_engine)

    return name, ServerWrapper(congress_api_server, workers)


def create_server(name, workers, policy_engine):
    congress_server = eventlet_server.Server(name,
                                             policy_engine=policy_engine)
    return name, ServerWrapper(congress_server, workers)


def serve(*servers):
    if max([server[1].workers for server in servers]) > 1:
        # TODO(arosen) - need to provide way to communicate with DSE services
        launcher = service.ProcessLauncher(cfg.CONF)
    else:
        launcher = service.ServiceLauncher(cfg.CONF)

    for name, server in servers:
        try:
            server.launch_with(launcher)
        except socket.error:
            LOG.exception(_('Failed to start the %s server'), name)
            raise

    try:
        launcher.wait()
    except KeyboardInterrupt:
        LOG.info("Congress server stopped by interrupt.")


def launch_api_server(policy_engine):
    LOG.info("Starting congress server on port %d", cfg.CONF.bind_port)

    # API resource runtime encapsulation:
    #   event loop -> wsgi server -> webapp -> resource manager

    paste_config = config.find_paste_config()
    config.set_config_defaults()
    servers = []
    servers.append(create_api_server(paste_config,
                                     cfg.CONF.dse.node_id,
                                     cfg.CONF.bind_host,
                                     cfg.CONF.bind_port,
                                     cfg.CONF.api_workers,
                                     policy_engine=policy_engine))
    return servers


def launch_server(policy_engine):
    servers = []
    servers.append(create_server(cfg.CONF.dse.node_id,
                                 cfg.CONF.api_workers, policy_engine))

    return servers


def main():
    # Initialize config here!! after completing to migrate the new architecture
    # config.init(args)
    args = sys.argv[1:]
    if not cfg.CONF.config_file:
        sys.exit("ERROR: Unable to find configuration file via default "
                 "search paths ~/.congress/, ~/, /etc/congress/, /etc/) and "
                 "the '--config-file' option!")
    config.setup_logging()

    if config.WITHOUT_ENGINE in args:
        policy_engine = False
    else:
        policy_engine = True

    if (config.WITHOUT_API in sys.argv[1:] and
            cfg.CONF.distributed_architecture is True):
        # launch dse node without all API services
        servers = launch_server(policy_engine)
    else:
        servers = launch_api_server(policy_engine)

    serve(*servers)


if __name__ == '__main__':
    main()
