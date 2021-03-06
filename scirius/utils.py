"""
Copyright(C) 2014,2015,  Stamus Networks
Written by Eric Leblond <eleblond@stamus-networks.com>

This file is part of Scirius.

Scirius is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Scirius is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Scirius.  If not, see <http://www.gnu.org/licenses/>.
"""

from importlib import import_module
from time import time

from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.contrib import messages

import django_tables2 as tables

from rules.tables import *
from accounts.tables import UserTable
from accounts.models import SciriusUser
from rules.models import get_system_settings

def build_path_info(request):
    splval = request.path_info.strip('/ ').split('/')
    if splval[0] == 'rules':
        try:
            splval.remove('pk')
        except ValueError:
            pass
        splval = splval[1:]
    if len(splval):
        return " - ".join(splval)
    else:
        return "home"

class TimezoneMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated():
            try:
                user = SciriusUser.objects.get(user = request.user)
            except:
                return self.get_response(request)
            if user:
                timezone.activate(user.timezone)
        return self.get_response(request)

def complete_context(request, context):
    if get_system_settings().use_elasticsearch:
        if request.GET.__contains__('duration'):
            duration = int(request.GET.get('duration', '24'))
            if duration > 24 * 30:
                duration = 24 * 30
            request.session['duration'] = duration
        else:
            duration = int(request.session.get('duration', '24'))
        from_date = int((time() - (duration * 3600)) * 1000)
        if duration <= 24:
            date = str(duration) + "h"
        else:
            date = str(duration / 24) + "d"
        if request.GET.__contains__('graph'):
            graph = request.GET.get('graph', 'sunburst')
            if not graph in ['sunburst', 'circles']:
                graph = 'sunburst'
            request.session['graph'] = graph
        else:
            graph = 'sunburst'
        if graph == 'sunburst':
            context['draw_func'] = 'draw_sunburst'
            context['draw_elt'] = 'path'
        else:
            context['draw_func'] = 'draw_circle'
            context['draw_elt'] = 'circle'
        context['date'] = date
        context['from_date'] = from_date
        context['time_range'] = duration * 3600

def scirius_render(request, template, context):
    context['generator'] = settings.RULESET_MIDDLEWARE
    context['path_info'] = build_path_info(request)
    context['scirius_release'] = settings.SCIRIUS_FLAVOR + " v" + settings.SCIRIUS_VERSION
    gsettings = get_system_settings()
    if settings.USE_INFLUXDB:
        context['influxdb'] = 1
    if settings.USE_SURICATA_STATS:
        context['suricata_stats'] = 1
    if settings.USE_LOGSTASH_STATS:
        context['logstash_stats'] = 1
    if gsettings.use_elasticsearch:
        context['elasticsearch'] = 1
        if settings.USE_KIBANA:
            context['kibana'] = 1
            if settings.KIBANA_PROXY:
                context['kibana_url'] = "/kibana"
            else:
                context['kibana_url'] = settings.KIBANA_URL
            context['kibana_version'] = settings.KIBANA_VERSION
    if settings.ELASTICSEARCH_VERSION >= 2:
        context['es2x'] = 1
    else:
        context['es2x'] = 0
    if settings.USE_EVEBOX:
        context['evebox'] = 1
        context['evebox_url'] = "/evebox"

    context['toplinks'] = [{
        'id': 'suricata',
        'url': '/suricata/',
        'icon': 'eye-open',
        'label': 'Suricata'
    }]
    try:
        links = get_middleware_module('links')
        context['toplinks'] = links.TOPLINKS
        context['links'] = links.links(request)
    except:
        pass
    try:
        context['middleware_status'] = get_middleware_module('common').block_status(request)
    except:
        pass

    context['messages'] = messages.get_messages(request)
    complete_context(request, context)
    return render(request, template, context)

def scirius_listing(request, objectname, name, template = 'rules/object_list.html', table = None, adduri = None):
    # FIXME could be improved by generating function name
    assocfn = { 'Categories': CategoryTable, 'Users': UserTable }
    olist = objectname.objects.all()
    if olist:
        if table == None:
            data = assocfn[name](olist)
        else:
            data = table(olist)
        tables.RequestConfig(request).configure(data)
        data_len = len(olist)
    else:
        data = None
        data_len = 0

    context = {'objects': data, 'name': name, 'objects_len': data_len}
    try:
        objectname.editable
        context['action'] = objectname.__name__.lower()
    except:
        pass
    if adduri:
        context['action'] = True
        context['adduri'] = adduri
    return scirius_render(request, template, context)

def get_middleware_module(module):
    return import_module('%s.%s' % (settings.RULESET_MIDDLEWARE, module))
