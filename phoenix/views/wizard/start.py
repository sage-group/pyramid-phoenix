from pyramid.view import view_config

from phoenix.views.wizard import Wizard

import logging
logger = logging.getLogger(__name__)

class Start(Wizard):
    def __init__(self, request):
        super(Start, self).__init__(request, name='wizard', title='Start')
        self.description = "Choose Favorite or None."
        self.wizard_state.clear()

    def schema(self):
        from phoenix.schema import WizardSchema
        return WizardSchema().bind(favorites=self.favorite.names())

    def success(self, appstruct):
        logger.debug('favorite: %s', appstruct.get('favorite'))
        favorite_state = self.favorite.get(appstruct.get('favorite'))
        logger.debug('favorite state: %s', favorite_state)
        self.wizard_state.load(favorite_state)
        super(Start, self).success(appstruct)

    def next_success(self, appstruct):
        self.success(appstruct)
        return self.next('wizard_wps')

    @view_config(route_name='wizard', renderer='phoenix:templates/wizard/default.pt')
    def view(self):
        return super(Start, self).view()