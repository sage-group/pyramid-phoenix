from pyramid.view import view_config, view_defaults

from phoenix.views import MyView

import logging
logger = logging.getLogger(__name__)

@view_defaults(permission='view', layout='default')
class Home(MyView):
    def __init__(self, request):
        super(Home, self).__init__(request, name='title', title='Home')

    @view_config(route_name='home', renderer='phoenix:templates/home.pt')
    def view(self):
        #lm = self.request.layout_manager
        #lm.layout.add_breadcrumb(route_name="home", title="Home")
        return {}