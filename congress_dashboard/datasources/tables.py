# Copyright 2014 VMware.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _                         
from django.utils.translation import ungettext_lazy                             
from horizon import tables


def get_resource_url(obj):
    return reverse('horizon:admin:datasources:datasource_table_detail',
                   args=(obj['datasource_id'], obj['table_id']))


class DataSourcesTablesTable(tables.DataTable):
    name = tables.Column("name", verbose_name=_("Table Name"),
                         link=get_resource_url)

    class Meta(object):
        name = "datasources_tables"
        verbose_name = _("Service Data")
        hidden_title = False


def get_policy_link(datum):
    return reverse('horizon:admin:policies:detail',
                   args=(datum['policy_name'],))


def get_policy_table_link(datum):
    return reverse('horizon:admin:datasources:policy_table_detail',
                   args=(datum['policy_name'], datum['name']))


class PoliciesTablesTable(tables.DataTable):
    name = tables.Column("name", verbose_name=_("Table Name"),
                         link=get_policy_table_link)
    policy_name = tables.Column("policy_name", verbose_name=_("Policy"),
                                link=get_policy_link)
    policy_owner_id = tables.Column("policy_owner_id",
                                    verbose_name=_("Owner ID"))

    class Meta(object):
        name = "policies_tables"
        verbose_name = _("Policy Data")
        hidden_title = False


class DataSourceRowsTable(tables.DataTable):
    class Meta(object):
        name = "datasource_rows"
        verbose_name = _("Rows")
        hidden_title = False


class CreateDatasource(tables.LinkAction):
    name = 'create_datasource'
    verbose_name = _('Create Datasource')
    url = 'horizon:admin:datasources:create'
    classes = ('ajax-modal',)
    icon = 'plus'

class DeleteDatasource(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Datasource",
            u'Deleted Datasources',
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u'Deleted Datasource',
            u'Deleted Datasources',
            count
        )

    redirect_url = 'horizon:admin:datasources:index'

    def delete(self, request, name):
        congress.delete_datasource(request, name)


# TODO(ramineni): support create/delete datasource
class DataSourcesTable(tables.DataTable):
    name = tables.Column("name", verbose_name=_("Datasource Name"),
                         link='horizon:admin:datasources:datasource_detail')
    enabled = tables.Column("enabled", verbose_name=_("Enabled"))
    driver = tables.Column("driver", verbose_name=_("Driver"))
    config = tables.Column("config", verbose_name=_("Config"))

    class Meta(object):
        name = "datasources_list"
        verbose_name = _("Configured DataSources")
        hidden_title = False
        table_actions = (CreateDatasource, DeleteDatasource)
        row_actions = (DeleteDatasource,)
