from pyramid.view import view_config, view_defaults

import logging
logger = logging.getLogger(__name__)

@view_defaults(permission='edit', layout='default')
class Wizard:
    def __init__(self, request):
        self.request = request
        self.session = self.request.session
        self.csw = self.request.csw

    # csw function
    def search_csw_files(self, filter):
        logger.debug('filter=%s', filter)
        keywords = [k for k in map(str.strip, str(filter).split(' ')) if len(k)>0]

        results = []
        try:
            self.csw.getrecords(keywords=keywords)
            logger.debug('csw results %s', self.csw.results)
            for rec in self.csw.records:
                myrec = self.csw.records[rec]
                results.append(dict(
                    identifier = myrec.identifier,
                    title = myrec.title,
                    abstract = myrec.abstract,
                    subjects = myrec.subjects,
                    ))
        except:
            logger.exception('retrieving files failed! filter=%s', filter)
        return results

    @view_config(route_name='csw', renderer='templates/csw.pt')
    def csw_view(self):
        if 'next' in self.request.POST:
            return HTTPFound(location=self.request.route_url('csw'))
        elif 'previous' in self.request.POST:
            return HTTPFound(location=self.request.route_url('csw'))
        elif 'cancel' in self.request.POST:
            return HTTPFound(location=self.request.route_url('csw'))

        items = self.search_csw_files(filter='tas')

        from .grid import CatalogSearchGrid    
        grid = CatalogSearchGrid(
                self.request,
                items,
                ['title', 'abstract', 'subjects', 'identifier', 'action'],
            )

        return dict(
            title="Catalog Search", 
            description="Search in Catalog Service",
            grid=grid,
            items=items,
        )
