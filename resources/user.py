
# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#create user and login then return token
import boto3
import json
import functools
import sys
import uuid
import os
import argparse

#this is a decorator used for error logging
def log_event_on_error(handler):
    @functools.wraps(handler)
    def wrapper(event, context):
        try:
            return handler(event, context)
        except Exception:
            print('event = %r' % event)
            raise

    return wrapper

@log_event_on_error
def user_handler(event, context):
    #print (event)
    if not str(event).__contains__('body'):
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Missing body",
            }),
         }
    
    #get body to read params
    body=event['body']
    if ( not body['stackName'] ):
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Body missing stackName",
            }),
         }

    stackName = body['stackName']
    keyPrefix = body['keyPrefix']

    cloudformation = boto3.resource('cloudformation')
    # current_session =  boto3.session.Session()
    stack = cloudformation.Stack(stackName)
    if not stack :
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Stack " + stackName + " not found!",
            }),
         }
    
    # default_region = os.environ.get('AWS_DEFAULT_REGION')
    # if not region:
    #     region = 'us-east-2'

    outputs = stack.outputs
    # print("Outputs: " + str(outputs))
    userPoolId = ""
    for export in outputs :
        if export['OutputKey'] == keyPrefix + 'UserPool' :
            userPoolId = export['OutputValue']
        elif export['OutputKey'] == keyPrefix + 'UserPoolClient' :
            poolClientlId = export['OutputValue']
        elif export['OutputKey'] == keyPrefix + 'IdentityPool' :
            identityPoolId = export['OutputValue']

    if userPoolId == "" :
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "{}UserPool output not found in {}".format(keyPrefix,stackName),
            }),
        }

    tenantId = keyPrefix.lower()
    idpclient = boto3.client('cognito-idp')
    #now create all the pieces
    tenantUserName = "user@{}.com".format(tenantId)

    if not body['tokenOnly'] or body['tokenOnly'] == 'N' :
        #create user
        create_cognito_user(idpclient, userPoolId, identityPoolId, tenantUserName, tenantId)
        #print("Cognito user {} created".format(tenantUserName))

        #set password for user
        update_user_password(idpclient, userPoolId, tenantUserName)
        #print("User password updated")

    response = idpclient.admin_initiate_auth(
        UserPoolId=userPoolId,
        ClientId=poolClientlId,
        AuthFlow='ADMIN_NO_SRP_AUTH',
        AuthParameters={
            'USERNAME': tenantUserName,
            'PASSWORD': 'ABCdef123'
        })
    jwt_token = response['AuthenticationResult']['IdToken']

    ret_body = {
        "userPoolId" : userPoolId,
 #       "userPoolName" : userPoolName,
        "poolClientId" : poolClientlId,
        "userName" : tenantUserName,
        "token" : jwt_token
    }
    
  #  print("return: " + json.dumps(ret_body))
    return ret_body
    #return user pool id, appclient id, and token

#create a user for the tenant
def create_cognito_user(client, userPoolId, identityPoolId, tenantUserName, tenantId,):
    #COGNITO_USER=$(aws cognito-idp admin-create-user --user-pool-id "$USER_POOL_ID" --username "$TENANT_USERNAME" --message-action SUPPRESS --user-attributes "[{\"Name\":\"custom:tenant_id\",\"Value\":\"$TENANT_ID\"},{\"Name\":\"custom:identity_pool\",\"Value\":\"$IDENTITY_POOL_ID\"},{\"Name\":\"custom:queue_url\",\"Value\":\"$QUEUE_URL\"}]")
    client.admin_create_user(
        UserPoolId=userPoolId,
        Username=tenantUserName,
        UserAttributes=[
            {
                'Name': 'custom:identity_pool',
                'Value': identityPoolId
            },
            {
                'Name': 'custom:tenant_id',
                'Value': tenantId
            }
        ],
        #TemporaryPassword='string',
        #ForceAliasCreation=True|False,
        MessageAction='SUPPRESS',
    )

#update the user password to set permanent password
def update_user_password(client, userPoolId, tenantUserName):
    #aws cognito-idp admin-set-user-password --user-pool-id "$USER_POOL_ID" --username "$TENANT_USERNAME" --password ABCdef123 --permanent
    client.admin_set_user_password(
        UserPoolId=userPoolId,
        Username=tenantUserName,
        Password='ABCdef123',
        Permanent=True
    )

# the following is useful to make this script executable in both
# AWS Lambda and any other local environments
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("tenant")
    parser.add_argument("tokenOnly", default="Y", type=str)

    args = parser.parse_args()
    event = {'httpMethod': 'GET', 
                'body': {
                    'stackName' : 'sqs-app',
                    'tokenOnly' : args.tokenOnly,
                    'keyPrefix' : args.tenant
                }
            }

    ret = user_handler(event, None)
    print(json.dumps(ret))