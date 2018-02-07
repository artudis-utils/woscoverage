#! /usr/bin/env python

import zeep
import click
import requests
import pdb
import json
import time
from lxml import objectify
import pprint

AUTH_WSDL = "https://search.webofknowledge.com/esti/wokmws/ws/WOKMWSAuthenticate?wsdl"
SERVICE_WSDL = "https://search.webofknowledge.com/esti/wokmws/ws/WokSearch?wsdl"

@click.command()
@click.option('--id', default='')
@click.option('--password', default='')
def main(id, password):
    history = zeep.plugins.HistoryPlugin()
    session = requests.Session()
    session.auth = requests.auth.HTTPBasicAuth(id, password)

    auth_client = zeep.Client(wsdl=AUTH_WSDL, transport=zeep.transports.Transport(session=session), plugins=[history])
    auth_client.service.authenticate()

    service_client = zeep.Client(wsdl=SERVICE_WSDL, transport=zeep.transports.Transport(session=session), plugins=[history])

    firstRecord = 1

    queryParameters = {
        'databaseId':'WOS',
        'userQuery':'IS=(0003-7087)',
        'queryLanguage':'en',
    }
    retrieveParameters = {
        'firstRecord': firstRecord,
        'count':100,
        'viewField': {
            'collectionName':'WOS',
            'fieldName':'identifiers',
            'fieldName':'title',
        },
    }
    search = service_client.service.search(queryParameters=queryParameters, retrieveParameters=retrieveParameters)

    pprint.pprint(search)

if __name__ == "__main__":
    main()
