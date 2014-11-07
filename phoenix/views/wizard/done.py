from pyramid.view import view_config

from phoenix.views.wizard import Wizard

import logging
logger = logging.getLogger(__name__)

class Done(Wizard):
    def __init__(self, request):
        super(Done, self).__init__(
            request, name='wizard_done', title="Done")
        self.description = "Describe your Job and start Workflow."
        from owslib.wps import WebProcessingService
        self.wps = WebProcessingService(self.wizard_state.get('wizard_wps')['url'])
        self.csw = self.request.csw

    def schema(self):
        from phoenix.schema import DoneSchema
        return DoneSchema()

    def workflow_description(self):
        credentials = self.get_user().get('credentials')
        # if source and worker are on the same machine use local output_path
        # otherwise http url.
        from urlparse import urlparse
        source_hostname = urlparse(self.request.wps.url).netloc.split(':')[0]
        worker_hostname = urlparse(self.wps.url).netloc.split(':')[0]
        output = 'output_external'
        if source_hostname == worker_hostname:
            output = 'output'
        logger.debug('source output identifier: %s', output)

        inputs = ['credentials=%s' % (credentials)]
        for url in self.resources():
            inputs.append('resource=%s' % url)
        
        source = dict(
            service = self.request.wps.url,
            identifier = 'wget',
            input = inputs,
            output = output, # output for chaining to worker as input
        )
        from phoenix.wps import appstruct_to_inputs
        inputs = appstruct_to_inputs(self.wizard_state.get('wizard_literal_inputs', {}))
        worker_inputs = ['%s=%s' % (key, value) for key,value in inputs]
        worker = dict(
            service = self.wps.url,
            identifier = self.wizard_state.get('wizard_process')['identifier'],
            input = worker_inputs,
            complex_input = self.wizard_state.get('wizard_complex_inputs')['identifier'])
        nodes = dict(source=source, worker=worker)
        return nodes

    def execute_workflow(self, appstruct):
        logger.debug('done appstruct = %s', appstruct)
        nodes = self.workflow_description()
        logger.debug('done nodes = %s', nodes)
        from phoenix.wps import execute_restflow
        return execute_restflow(self.request.wps, nodes)

    def success(self, appstruct):
        super(Done, self).success(appstruct)
        if appstruct.get('is_favorite', False):
            self.favorite.set(
                name=appstruct.get('favorite_name'),
                state=self.wizard_state.dump())
            self.favorite.save()
        
        execution = self.execute_workflow(appstruct)
        from phoenix.models import add_job
        add_job(
            request = self.request,
            workflow = True,
            title = appstruct.get('title'),
            wps_url = execution.serviceInstance,
            status_location = execution.statusLocation,
            abstract = appstruct.get('abstract'),
            keywords = appstruct.get('keywords'))

    def next_success(self, appstruct):
        from pyramid.httpexceptions import HTTPFound
        self.success(appstruct)
        self.wizard_state.clear()
        return HTTPFound(location=self.request.route_url('myjobs'))

    def appstruct(self):
        appstruct = super(Done, self).appstruct()
        params = ', '.join(['%s=%s' % item for item in self.wizard_state.get('wizard_literal_inputs', {}).items()])
        identifier = self.wizard_state.get('wizard_process')['identifier']
        # TODO: add search facets to keywords
        appstruct.update( dict(
            title=identifier,
            abstract=params,
            keywords="test,workflow,%s" % identifier,
            favorite_name=identifier))
        return appstruct

    @view_config(route_name='wizard_done', renderer='phoenix:templates/wizard/default.pt')
    def view(self):
        return super(Done, self).view()