
import json
import os
import logging
import uuid
from urllib.parse import urlparse
import datetime

from utils import get_cognito_user
from os.path import sep
import boto3
from storage_credentials import query_storage_credentials

import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': str(err) if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Credentials': '*'
        },
    }

def get_presigned_url(event, context):
    logger.info('## ENVIRONMENT VARIABLES')
    logger.info(os.environ)
    logger.info('## EVENT')
    logger.info(event)

    operation = event['httpMethod']
    if (operation != 'GET'):
        return respond(ValueError('Unsupported method ' + str(operation)))

    cognito_username, groups = get_cognito_user(event)

    qs = event['queryStringParameters']
    logger.info(qs)

    bucket = None
    path = None
    if 'bucket' in qs:
        bucket = qs['bucket']
    if 'path' in qs:
        path = qs['path']

    if not path or not bucket:
        logger.info('bucket and path are required')
        return respond(ValueError('bucket and path are required'))

    if ('method' in qs):
        method = qs['method']
    else:
        method = 'get_object'

    creds = query_storage_credentials(cognito_username, bucket)

    if not creds:
        msg = "No credentials available for bucket {} for user {}".format(bucket, cognito_username)
        logger.warning(msg)
        return respond(msg)

    if method == 'list_objects_v2':
        params = {'Bucket': bucket, 'Prefix': path, 'Delimiter': '/'}
    else:
        params = {'Bucket': bucket, 'Key': path}

    sts_client = boto3.client('sts')
    assumed_role_object = sts_client.assume_role(
        RoleArn=creds['iam_role'],
        ExternalId=creds['external_id'],
        RoleSessionName=str(uuid.uuid4()))

    credentials = assumed_role_object['Credentials']
    client = boto3.client("s3",
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )

    ps_url = client.generate_presigned_url(method, Params=params, ExpiresIn = (24*60*60))
    logger.info('Presigned URL is ' + str(ps_url))

    if (ps_url == None):
        return respond(ValueError('Failed to create presigned URL'))
    else:
        rv = {"presigned_url": ps_url}
        logger.info(json.dumps(rv))
        return respond(None, rv)
