# -*- coding: utf-8 -*-

# Copyright (c) 2013 CoNWeT Lab., Universidad Politécnica de Madrid

# This file is part of WStore.

# WStore is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL)
# as published by the European Commission, either version 1.1
# of the License, or (at your option) any later version.

# WStore is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.

# You should have received a copy of the European Union Public Licence
# along with WStore.
# If not, see <https://joinup.ec.europa.eu/software/page/eupl/licence-eupl>.

import json
import urllib2
from urllib2 import HTTPError

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.contrib.sites.models import get_current_site

from wstore.store_commons.resource import Resource
from wstore.store_commons.utils.http import build_response, get_content_type, supported_request_mime_types, \
authentication_required
from wstore.models import Offering, Organization
from wstore.models import Context
from wstore.offerings.offerings_management import create_offering, get_offerings, get_offering_info, delete_offering,\
publish_offering, bind_resources, count_offerings, update_offering, comment_offering
from wstore.offerings.resources_management import register_resource, get_provider_resources, delete_resource
from wstore.store_commons.utils.method_request import MethodRequest



class OfferingCollection(Resource):

    # Creates a new offering associated with the user
    # that is create a new application model
    @authentication_required
    @supported_request_mime_types(('application/json', 'application/xml'))
    def create(self, request):

        # Obtains the user profile of the user
        user = request.user
        content_type = get_content_type(request)[0]

        # Get the provider roles in the current organization
        roles = user.userprofile.get_current_roles()

        # Checks the provider role
        if 'provider' in roles:

            if content_type == 'application/json':
                try:
                    json_data = json.loads(request.raw_post_data)
                    create_offering(user, json_data)
                except HTTPError:
                    return build_response(request, 502, 'Bad Gateway')
                except Exception, e:
                    return build_response(request, 400, e.message)
            else:
                pass  # TODO xml parsed
        else:
            return build_response(request, 403, 'Forbidden')

        return build_response(request, 201, 'Created')

    @authentication_required
    def read(self, request):

        # Read the query string in order to know the filter and the page
        filter_ = request.GET.get('filter', 'published')
        user = User.objects.get(username=request.user)
        action = request.GET.get('action', None)
        sort = request.GET.get('sort', None)

        # Check sorting values
        if sort != None:
            if sort != 'date' and sort != 'rating' and sort != 'name':
                return build_response(request, 400, 'Invalid sorting')

        pagination = {
            'skip': request.GET.get('start', None),
            'limit': request.GET.get('limit', None)
        }

        if action != 'count':
            if pagination['skip'] and pagination['limit']:
                if filter_ == 'provided':
                    result = get_offerings(user, request.GET.get('state'), owned=True, pagination=pagination, sort=sort)

                elif filter_ == 'published':
                    result = get_offerings(user, pagination=pagination, sort=sort)

                elif filter_ == 'purchased':
                    result = get_offerings(user, 'purchased', owned=True, pagination=pagination, sort=sort)
            else:
                if filter_ == 'provided':
                    result = get_offerings(user, request.GET.get('state'), owned=True, sort=sort)

                elif filter_ == 'published':
                    result = get_offerings(user, sort=sort)

                elif filter_ == 'purchased':
                    result = get_offerings(user, 'purchased', owned=True, sort=sort)

        else:
            if filter_ == 'provided':
                result = count_offerings(user, request.GET.get('state'), owned=True)

            elif filter_ == 'published':
                result = count_offerings(user)

            elif filter_ == 'purchased':
                result = count_offerings(user, 'purchased', owned=True)

        mime_type = 'application/JSON; charset=UTF-8'
        return HttpResponse(json.dumps(result), status=200, mimetype=mime_type)


class OfferingEntry(Resource):

    @authentication_required
    def read(self, request, organization, name, version):
        user = request.user
        try:
            org = Organization.objects.get(name=organization)
            offering = Offering.objects.get(name=name, owner_organization=org, version=version)
        except:
            return build_response(request, 404, 'Not found')

        try:
            result = get_offering_info(offering, user)
        except Exception, e:
            return build_response(request, 400, e.message)

        return HttpResponse(json.dumps(result), status=200, mimetype='application/json; charset=UTF-8')

    @authentication_required
    @supported_request_mime_types(('application/json', 'application/xml'))
    def update(self, request, organization, name, version):

        user = request.user
        # Get the offering
        try:
            org = Organization.objects.get(name=organization)
            offering = Offering.objects.get(owner_organization=org, name=name, version=version)
        except:
            return build_response(request, 404, 'Not found')

        # Update the offering
        try:
            # Check if the user is the owner of the offering or if is a manager of the
            # owner organization
            if not offering.is_owner(user) and user.pk not in org.managers:
                return build_response(request, 403, 'Forbidden')

            data = json.loads(request.raw_post_data)

            update_offering(offering, data)
        except Exception, e:
            return build_response(request, 400, e.message)

        return build_response(request, 200, 'OK')

    @authentication_required
    def delete(self, request, organization, name, version):
        # If the offering has been purchased it is not deleted
        # it is marked as deleted in order to allow customers that
        # have purchased the offering to install it if needed

        # Get the offering
        try:
            org = Organization.objects.get(name=organization)
            offering = Offering.objects.get(name=name, owner_organization=org, version=version)
        except:
            return build_response(request, 404, 'Not found')

        # Check if the user can delete the offering
        if not offering.is_owner(request.user) and request.user.pk not in org.managers:
            return build_response(request, 403, 'Forbidden')

        # Delete the offering
        try:
            delete_offering(offering)
        except Exception, e:
            return build_response(request, 400, e.message)

        return build_response(request, 204, 'No content')


class ResourceCollection(Resource):

    # Creates a new resource associated with an user
    @supported_request_mime_types(('application/json', 'multipart/form-data'))
    @authentication_required
    def create(self, request):

        user = request.user
        profile = user.userprofile
        content_type = get_content_type(request)[0]

        if 'provider' in profile.get_current_roles():

            if content_type == 'application/json':
                try:
                    data = json.loads(request.raw_post_data)
                    register_resource(user, data)
                except Exception, e:
                    return build_response(request, 400, e.message)
            elif content_type == 'multipart/form-data':
                try:
                    data = json.loads(request.POST['json'])
                    f = request.FILES['file']
                    register_resource(user, data, file_=f)
                except Exception, e:
                    return build_response(request, 400, e.message)
        else:
            return build_response(request, 403, 'Forbidden')

        return build_response(request, 201, 'Created')

    @authentication_required
    def read(self, request):
        profile = request.user.userprofile
        if 'provider' in profile.get_current_roles():
            try:
                response = get_provider_resources(request.user)
            except Exception, e:
                return build_response(request, 400, e.message)
        else:
            return build_response(request, 403, 'Forbidden')

        return HttpResponse(json.dumps(response), status=200, mimetype='application/json; charset=utf-8')


class ResourceEntry(Resource):

    @authentication_required
    def delete(self, request, provider, name, version):

        response = build_response(request, 204, 'No Content')
        error = False
        try:
            # Get the resource
            resource = Resource.objects.get(provider=provider_org, name=name, version=version)
        except:
            # set error response
            response = build_response(request, 404, 'Resource not found')
            error = True

        # Try to delete the resource
        if not error:
            try:
                delete_resource(resource)
            except Exception, e:
                response = build_response(request, 400, e.message)

        # Return the response
        return response


class PublishEntry(Resource):

    # Publish the offering is some marketplaces
    @authentication_required
    @supported_request_mime_types(('application/json', 'application/xml'))
    def create(self, request, organization, name, version):
        # Obtains the offering
        offering = None
        content_type = get_content_type(request)[0]
        try:
            org = Organization.objects.get(name=organization)
            offering = Offering.objects.get(name=name, owner_organization=org, version=version)
        except:
            return build_response(request, 404, 'Not found')

        # Check that the user can publish the offering
        if not offering.is_owner(request.user) and request.user.pk not in org.managers:
            return build_response(request, 403, 'Forbidden')

        if content_type == 'application/json':
            try:
                data = json.loads(request.raw_post_data)
                publish_offering(offering, data)
            except HTTPError:
                return build_response(request, 502, 'Bad gateway')
            except Exception, e:
                return build_response(request, 400, e.message)

        # Append the new offering to the newest list
        site = get_current_site(request)
        context = Context.objects.get(site=site)

        if len(context.newest) < 8:
            context.newest.insert(0, offering.pk)
        else:
            context.newest.pop()
            context.newest.insert(0, offering.pk)

        context.save()

        return build_response(request, 200, 'OK')


class BindEntry(Resource):

    # Binds resources with offerings
    @authentication_required
    @supported_request_mime_types(('application/json', 'application/xml'))
    def create(self, request, organization, name, version):
        # Obtains the offering
        offering = None
        content_type = get_content_type(request)[0]
        try:
            org = Organization.objects.get(name=organization)
            offering = Offering.objects.get(name=name, owner_organization=org, version=version)
        except:
            return build_response(request, 404, 'Not found')

        # Check that the user can bind resources to the offering
        if not offering.is_owner(request.user) and request.user.pk not in org.managers:
            return build_response(request, 403, 'Forbidden')

        if content_type == 'application/json':
            try:
                data = json.loads(request.raw_post_data)
                bind_resources(offering, data, request.user)
            except:
                build_response(request, 400, 'Invalid JSON content')

        return build_response(request, 200, 'OK')


class CommentEntry(Resource):

    @authentication_required
    @supported_request_mime_types(('application/json', ))
    def create(self, request, organization, name, version):

        # Get the offering
        try:
            org = Organization.objects.get(name=organization)
            offering = Offering.objects.get(name=name, owner_organization=org, version=version)
        except:
            return build_response(request, 404, 'Not found')

        # Check offering state
        if offering.state != 'published':
            return build_response(request, 403, 'Forbidden')

        # Comment the offering
        try:
            data = json.loads(request.raw_post_data)
            comment_offering(offering, data, request.user)
        except Exception as e:
            return build_response(request, 400, unicode(e))

        return build_response(request, 201, 'Created')


class NewestCollection(Resource):

    @authentication_required
    def read(self, request):

        site = get_current_site(request)
        context = Context.objects.get(site=site)

        response = []
        for off in context.newest:
            offering = Offering.objects.get(pk=off)
            response.append(get_offering_info(offering, request.user))

        return HttpResponse(json.dumps(response), status=200, mimetype='application/json')


class TopRatedCollection(Resource):

    @authentication_required
    def read(self, request):

        site = get_current_site(request)
        context = Context.objects.get(site=site)

        response = []
        for off in context.top_rated:
            offering = Offering.objects.get(pk=off)
            response.append(get_offering_info(offering, request.user))

        return HttpResponse(json.dumps(response), status=200, mimetype='application/json;charset=UTF-8')


class ApplicationCollection(Resource):

    # Get idm applications
    @authentication_required
    def read(self, request):

        # Check user roles
        if not 'provider' in request.user.userprofile.get_current_roles():
            return build_response(request, 403, 'Forbidden')

        # Make idm request
        from wstore.social_auth_backend import FIWARE_APPLICATIONS_URL
        url = FIWARE_APPLICATIONS_URL

        if request.user.userprofile.is_user_org():
            actor_id = request.user.userprofile.actor_id
        else:
            actor_id = request.user.userprofile.current_organization.actor_id

        token = request.user.userprofile.access_token

        url += '?actor_id=' + str(actor_id)
        url += '&access_token=' + token

        req = MethodRequest('GET', url)

        # Call idm
        opener = urllib2.build_opener()

        resp = []
        try:
            response = opener.open(req)
            # Make the response
            resp = response.read()
        except Exception, e:

            if e.code == 401:
                try:
                    # Try to refresh the access token
                    social = request.user.social_auth.filter(provider='fiware')[0]
                    social.refresh_token()

                    # Update credentials
                    social = request.user.social_auth.filter(provider='fiware')[0]
                    credentials = social.extra_data

                    request.user.userprofile.access_token = credentials['access_token']
                    request.user.userprofile.refresh_token = credentials['refresh_token']
                    request.user.userprofile.save()

                    # Try to connect again
                    token = request.user.userprofile.access_token
                    url += '?actor_id=' + str(actor_id)
                    url += '&access_token=' + token

                    req = MethodRequest('GET', url)
                
                    response = opener.open(req)
                    # Make the response
                    resp = response.read()
                except:
                    resp = json.dumps([])
            else:
                resp = json.dumps([])

        return HttpResponse(resp, status=200, mimetype='application/json;charset=UTF-8')

