from django.utils.translation import ugettext_lazy as _

import horizon

class PolicyGroup(horizon.PanelGroup):
    slug = "policy"
    name = _("Policy")
    panels = ("policies", "datasources")

class Congress(horizon.Dashboard):
   name = _("Congress")
   slug = "congress"
   panels = (PolicyGroup, )           # Add your panels here.
   default_panel = 'policies'    # Specify the slug of the dashboard's default panel.


horizon.register(Congress)
