#! /usr/bin/env python

import zeep
import click
import requests
import pdb
import json
import time
import lxml
import pprint
import sqlite3


AUTH_WSDL    = "https://search.webofknowledge.com/esti/wokmws/ws/WOKMWSAuthenticate?wsdl"
SERVICE_WSDL = "https://search.webofknowledge.com/esti/wokmws/ws/WokSearch?wsdl"
SQLITEDB = "results.db"

@click.command()
@click.option('--id', default='')
@click.option('--password', default='')
@click.option('--people', show_default=True, required=False,
               type=click.File('r', encoding='utf-8'), 
               help="Person export JSON file from Artudis.")
@click.option('--collections', show_default=True, required=False,
               type=click.File('r', encoding='utf-8'), 
               help="Collections export JSON file from Artudis.")
def main(id, password, people, collections):

    # History keeps track of requests sent to the SOAP API
    history = zeep.plugins.HistoryPlugin()

    # Session enables the auth, and keeps the cookie for subsequent requests 
    session = requests.Session()
    session.auth = requests.auth.HTTPBasicAuth(id, password)

    # Authenticate 
    auth_client = zeep.Client(wsdl=AUTH_WSDL, transport=zeep.transports.Transport(session=session), plugins=[history])
    auth_client.service.authenticate()

    service_client = zeep.Client(wsdl=SERVICE_WSDL, transport=zeep.transports.Transport(session=session), plugins=[history])

    conn = sqlite3.connect(SQLITEDB)

    # Process the artudis journals
    for line in collections:
        json_collection = json.loads(line)
        for identifier in json_collection['identifier']:
            if identifier['scheme'] == 'issn':
                issn = identifier['value']
                if issn[4] != "-":
                    issn = issn[0:4]+"-"+issn[4:8]

                # Is this issn in the db yet?
                cur = conn.cursor()
                cur.execute("SELECT issn FROM results WHERE issn = ?", (issn,))
                if not cur.fetchone():
   
                    queryParameters = {
                        'databaseId':'WOS',
                        'userQuery':'IS=({})'.format(issn),
                        'queryLanguage':'en',
                    }
                    retrieveParameters = {
                        'firstRecord': 1,
                        'count':1,
                        'viewField': {
                            'collectionName':'WOS',
                            'fieldName':'identifiers',
                        },
                    }
                    issn_lookup = service_client.service.search(queryParameters=queryParameters, retrieveParameters=retrieveParameters)
                    if issn_lookup['recordsFound'] == 0:
                        cur.execute("INSERT INTO results VALUES(?, 'False', 'True', ?)", (issn, json_collection['name']))
                        conn.commit()
                    else:
                        cur.execute("INSERT INTO results VALUES(?, 'True', 'True', ?)", (issn, json_collection['name']))
                        conn.commit()
                    
                    time.sleep(0.5)

    countperson = 0
    for line in people:

        countperson += 1
        print('Count:', countperson)
        json_person = json.loads(line)
       
        cur = conn.cursor()
        cur.execute("SELECT id FROM people_processed WHERE id = ?", (json_person['__id__'],))
        if cur.fetchone():
            continue
        
        identnums = []
        for identifier in json_person['identifier']:
            if identifier['scheme'] == 'orcid':
                identnums.append(identifier['value'])
            if identifier['scheme'] == 'thomson':
                identnums.append(identifier['value'])

        if identnums != []:

            firstRecord = 1
            queryParameters = {
                'databaseId':'WOS',
                'userQuery':'AI=({})'.format(" OR ".join(identnums)),
                'queryLanguage':'en',
            }
            retrieveParameters = {
                'firstRecord': firstRecord,
                'count':100,
                'viewField': {
                    'collectionName':'WOS',
                    'fieldName':['identifiers','title'],
                },
            }
            search = service_client.service.search(queryParameters=queryParameters, retrieveParameters=retrieveParameters)
            find_issn(conn, search, json_person)

            if search.recordsFound > 100:

                remaining = search.recordsFound - 100

                while remaining > 0:
                    count = min(remaining, 100)
                    firstRecord += count

                    retrieveParameters = {
                        'firstRecord': firstRecord,
                        'count':count,
                        'viewField': {
                            'collectionName':'WOS',
                            'fieldName':'identifiers',
                            'fieldName':'title',
                        },
                    }

                    retrieve = service_client.service.retrieve(queryId=search.queryId, retrieveParameters=retrieveParameters)
                    find_issn(conn, retrieve, json_person)
                           
                    remaining = remaining - 100

        cur.execute("INSERT INTO people_processed VALUES(?)", (json_person['__id__'],))
        conn.commit()

    print("Done!")
    conn.close()

def find_issn(conn, request, person):
    time.sleep(1)
    cur = conn.cursor()
    tree = lxml.etree.fromstring(request.records)
    for record in tree.iterfind('.//{http://scientific.thomsonreuters.com/schema/wok5.4/public/Fields}REC'):
        journalTitle = ""
        for title in record.iterfind('.//{http://scientific.thomsonreuters.com/schema/wok5.4/public/Fields}title'):
            if title.get('type') == 'source':
                journalTitle = title.text
        for identifier in record.iterfind('.//{http://scientific.thomsonreuters.com/schema/wok5.4/public/Fields}identifier'):
            if identifier.get('type') == 'issn':
                issn = identifier.get('value')
                if issn[4] != "-":
                    issn = issn[0:4]+"-"+issn[4:8]
                cur.execute("SELECT issn FROM results WHERE issn = ?", (issn,))
                if cur.fetchone():
                    cur.execute("UPDATE results SET in_wos = 'True' WHERE issn = ?", (issn,))
                else:
                    cur.execute("INSERT INTO results VALUES(?, 'True', 'False', ?)", (issn, journalTitle))

                cur.execute("INSERT INTO people_to_results VALUES(?, ?, ?)", (issn, str(person['__id__']), person['family_name']+", "+person['given_name']))

if __name__ == "__main__":
    main()

