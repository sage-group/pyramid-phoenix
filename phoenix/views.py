# views.py
# Copyright (C) 2013 the ClimDaPs/Phoenix authors and contributors
# <see AUTHORS file>
#
# This module is part of ClimDaPs/Phoenix and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

import os
import datetime

from pyramid.view import view_config, forbidden_view_config
from pyramid.httpexceptions import HTTPException, HTTPFound, HTTPNotFound
from pyramid.response import Response
from pyramid.security import remember, forget, authenticated_userid
from pyramid.events import subscriber, BeforeRender
from pyramid_deform import FormView
from pyramid_persona.views import verify_login 
from deform import Form
from deform.form import Button

from owslib.csw import CatalogueServiceWeb
from owslib.wps import WebProcessingService, WPSExecution, ComplexData

from .models import add_job, get_job, drop_jobs, update_job, num_jobs, jobs_by_userid

from .wps import WPSSchema  

from .helpers import wps_url
from .helpers import csw_url
from .helpers import update_wps_url
from .helpers import execute_wps
from .helpers import whitelist

import logging

log = logging.getLogger(__name__)

@subscriber(BeforeRender)
def add_global(event):
    event['message_type'] = 'alert-info'
    event['message'] = ''


# Exception view
# --------------

# @view_config(context=Exception)
# def error_view(exc, request):
#     msg = exc.args[0] if exc.args else ''
#     response = Response(str(msg))
#     response.status_int = 500
#     response.content_type = 'text/xml'
#     return response


# login
# -----

@view_config(route_name='login', check_csrf=True, renderer='json')
def login(request):
    # TODO: update login to my needs
    # https://pyramid_persona.readthedocs.org/en/latest/customization.html#do-extra-work-or-verification-at-login

    # Verify the assertion and get the email of the user
    email = verify_login(request)
    # check whitelist
    if email not in whitelist(request):
        request.session.flash('Sorry, you are not on the list')
        return {'redirect': '/', 'success': False}
    # Add the headers required to remember the user to the response
    request.response.headers.extend(remember(request, email))
    # Return a json message containing the address or path to redirect to.
    return {'redirect': request.POST['came_from'], 'success': True}

# logout
# ------


@view_config(route_name='logout', check_csrf=True, renderer='json')
def logout(request):
    request.response.headers.extend(forget(request))
    return {'redirect': request.POST['came_from']}


# home view
# ---------

@view_config(route_name='home',
             renderer='templates/home.pt',
             layout='default',
             permission='view'
             )
def home(request):
    log.debug('rendering home view')

    lm = request.layout_manager
    lm.layout.add_heading('heading_processes')
    lm.layout.add_heading('heading_jobs')
    return dict()


# processes
# ---------

@view_config(route_name='processes',
             renderer='templates/processes.pt',
             layout='default',
             permission='view'
             )
def processes(request):
    wps = WebProcessingService(wps_url(request), verbose=False, skip_caps=True)
    wps.getcapabilities()
    return dict( wps=wps, logged_in=authenticated_userid(request))
   
# jobs
# -------

@view_config(route_name='jobs',
             renderer='templates/jobs.pt',
             layout='default',
             permission='edit'
             )
def jobs(request):
    jobs = []

    for job in jobs_by_userid(request, user_id=authenticated_userid(request)):
        log.debug(job)
        log.debug('status_location = %s', job['status_location'])

        job['starttime'] = job['start_time'].strftime('%a, %d %h %Y %I:%M:%S %p')

        # TODO: handle different process status
        if job['status'] in ['ProcessAccepted', 'ProcessStarted', 'ProcessPaused']:
            job['errors'] = []
            try:
                wps = WebProcessingService(job['service_url'], verbose=False)
                execution = WPSExecution(url=wps.url)
                execution.checkStatus(url=job['status_location'], sleepSecs=0)
                job['status'] = execution.status
                job['percent_completed'] = execution.percentCompleted
                job['status_message'] = execution.statusMessage
                job['error_message'] = ''
                for err in execution.errors:
                    job['errors'].append( dict(code=err.code, locator=err.locator, text=err.text) )
               
            except:
                msg = 'could not access wps %s' % (job['status_location'])
                log.warn(msg)
                job['status'] = 'Exception'
                job['errors'].append( dict(code='', locator='', text=msg) )
            
            job['end_time'] = datetime.datetime.now()
            for err in job['errors']:
                job['error_message'] = err.get('text', '') + ';'

            # TODO: configure output delete time
            dd = 3
            job['output_delete_time'] = datetime.datetime.now() + datetime.timedelta(days=dd)
            percent = 45  # TODO: poll percent
            job['duration'] = str(job['end_time'] - job['start_time'])
            update_job(request, job)
        jobs.append(job)
        
        log.debug('leaving jobs')

    return dict(jobs=jobs)

# output_details
# --------------

@view_config(
     route_name='output_details',
     renderer='templates/output_details.pt',
     layout='default',
     permission='edit')
def output_details(request):
    title = u"Process Outputs"

    job = get_job(request, uuid=request.params.get('uuid'))
    wps = WebProcessingService(job['service_url'], verbose=False)
    execution = WPSExecution(url=wps.url)
    execution.checkStatus(url=job['status_location'], sleepSecs=0)

    form_info="Status: %s" % (execution.status)
    
    return( dict(
        title=execution.process.title, 
        form_info=form_info,
        outputs=execution.processOutputs) )

# form
# -----

@view_config(route_name='form',
             renderer='templates/form.pt',
             layout='default',
             permission='edit'
             )
class ExecuteView(FormView):
    log.debug('rendering execute')
    #form_info = "Hover your mouse over the widgets for description."
    buttons = ('submit',)
    title = u"Process Output"
    schema_factory = None
    wps = None
   
    def __call__(self):
        # build the schema if it not exist
        if self.schema is None:
            if self.schema_factory is None:
                self.schema_factory = WPSSchema
            
        try:
            identifier = self.request.params.get('identifier')
            self.wps = WebProcessingService(wps_url(self.request), verbose=False)
            process = self.wps.describeprocess(identifier)
            self.schema = self.schema_factory(
                title=process.title,
                process=process)
        except:
            raise
       
        return super(ExecuteView, self).__call__()

    def appstruct(self):
        return None

    def submit_success(self, appstruct):
        identifier = self.request.params.get("identifier")
        serialized = self.schema.serialize(appstruct)
      
        execution = execute_wps(self.wps, identifier, serialized)

        add_job(
            request = self.request, 
            user_id = authenticated_userid(self.request), 
            identifier = identifier, 
            wps_url = self.wps.url, 
            execution = execution)

        return HTTPFound(location=self.request.route_url('jobs'))

@view_config(route_name='monitor',
             renderer='templates/embedded.pt',
             layout='default',
             permission='edit'
             )
def monitor(request):
    log.debug('rendering monitor view')
    return dict(external_url='http://localhost:9001')


@view_config(route_name='catalog_wps_add',
             renderer='templates/catalog.pt',
             layout='default',
             permission='edit',
             )
class CatalogAddWPSView(FormView):
    #form_info = "Hover your mouse over the widgets for description."
    schema = None
    schema_factory = None
    buttons = ('add',)
    title = u"Catalog"

    def __call__(self):
        csw = CatalogueServiceWeb(csw_url(self.request))
        csw.getrecords2(maxrecords=100)
        wps_list = []
        for rec_id in csw.records:
            rec = csw.records[rec_id]
            if rec.format == 'WPS':
                wps_list.append((rec.references[0]['url'], rec.title))

        from .schema import CatalogAddWPSSchema
        # build the schema if it not exist
        if self.schema is None:
            if self.schema_factory is None:
                self.schema_factory = CatalogAddWPSSchema
            self.schema = self.schema_factory(title='Catalog').bind(
                wps_list = wps_list,
                readonly = True)

        return super(CatalogAddWPSView, self).__call__()

    def appstruct(self):
        return {'current_wps' : wps_url(self.request)}

    def add_success(self, appstruct):
        serialized = self.schema.serialize(appstruct)
        url = serialized['wps_url']

        csw = CatalogueServiceWeb(csw_url(self.request))
        csw.harvest(url, 'http://www.opengis.net/wps/1.0.0')

        return HTTPFound(location=self.request.route_url('catalog_wps_add'))

@view_config(route_name='catalog_wps_select',
             renderer='templates/catalog.pt',
             layout='default',
             permission='edit',
             )
class CatalogSelectWPSView(FormView):
    log.debug('rendering catalog select wps')
    #form_info = "Hover your mouse over the widgets for description."
    schema = None
    schema_factory = None
    buttons = ('submit',)
    title = u"Catalog"

    def __call__(self):
        csw = CatalogueServiceWeb(csw_url(self.request))
        csw.getrecords2(maxrecords=100)
        wps_list = []
        for rec_id in csw.records:
            rec = csw.records[rec_id]
            if rec.format == 'WPS':
                wps_list.append((rec.references[0]['url'], rec.title))

        from .schema import CatalogSelectWPSSchema
        # build the schema if it not exist
        if self.schema is None:
            if self.schema_factory is None:
                self.schema_factory = CatalogSelectWPSSchema
            self.schema = self.schema_factory(title='Catalog').bind(wps_list = wps_list)

        return super(CatalogSelectWPSView, self).__call__()

    def appstruct(self):
        return {'active_wps' : wps_url(self.request)}

    def submit_success(self, appstruct):
        serialized = self.schema.serialize(appstruct)
        wps_id = serialized['active_wps']
        log.debug('wps_id = %s', wps_id)
        update_wps_url(self.request, wps_id)        

        return HTTPFound(location=self.request.route_url('catalog_wps_select'))

@view_config(route_name='admin',
             renderer='templates/form.pt',
             layout='default',
             permission='edit',
             )
class AdminView(FormView):
    from .schema import AdminSchema

    log.debug('rendering admin view')
    #form_info = "Hover your mouse over the widgets for description."
    schema = AdminSchema(title="Administration")
    buttons = ('clear_database',)
    title = u"Administration"

    def appstruct(self):
        return {'jobs_count' : num_jobs(self.request)}

    def clear_database_success(self, appstruct):
        drop_jobs(self.request)
               
        return HTTPFound(location=self.request.route_url('admin'))


@view_config(route_name='help',
             renderer='templates/embedded.pt',
             layout='default',
             permission='view'
             )
def help(request):
    log.debug('rendering help view')
    return dict(external_url='/docs')

