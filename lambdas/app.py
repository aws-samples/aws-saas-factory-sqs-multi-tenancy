
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

import json
import time
import urllib.request
import cognito
import token_handler
import message_helper
import logging
from botocore.exceptions import ClientError

#This is for SSL certiticate error in Python
#ssl._create_default_https_context = ssl._create_unverified_context
# Had to run the Install Certificats.command from the Python 3.7 folder

""" region = 'us-west-2'
userpool_id = 'us-west-2_ujo3liqS5'
app_client_id = 'f7u94ger0vvskunbt50p3j1tb'
"""

def lambda_handler(event, context):
    #logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info(event)
    if not str(event).__contains__('headers'):
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Missing headers",
            }),
        }

    data = json.loads(event['body'])
    if 'message' not in data:
        logging.error("Validation Failed")
        raise Exception("Couldn't create the message.")

    logging.info("message: " + data['message'])
    message = data['message']

    try:
        start = time.time()
        #verify token and get the claims and tenant_id from the token
        token, claims = token_handler.process_token(event['headers'])
        end = time.time()
        logging.debug("Verify token execution time: {}".format(end - start))
    except ClientError as err:
        logging.error("Error with token" + err)
        return {
                "statusCode": 500,
                "body": json.dumps({
                    "message": "Invalid token"
                })
            }

    logging.debug('Token is valid, now get Identity')
    # now we can use the claims
    if not claims['custom:tenant_id']:
       logging.error('No tenant_id attribute found in claims')
       return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "No tenant_id attribute found in claims"
            })
        }


    # Send the message using the message helper
    
    # Get Account ID from lambda function arn in the context
    account_id = context.invoked_function_arn.split(":")[4]
    #logger.debug ('Account ID=', account_id)

    try:
        # construct message and use function in layer to send the message.
        start = time.time()
        message_helper.send_message(token, claims, account_id, "order", message)
        end = time.time()
        logging.debug("Message send time: {}".format(end - start))
    except ClientError as err:
        logging.error("Error with sending message" + err)
        return {
            "statusCode": 200,
            "body": json.dumps({
                    "message": "Could not send message"
                })
            }

    return {
        "statusCode": 200,
        "body": json.dumps({
                "message": "message sent to queue",
                "claims" : claims
            })
        }


# the following is useful to make this script executable in both
# AWS Lambda and any other local environments
if __name__ == '__main__':
    # for testing locally you can enter the JWT ID Token here
    event = {'httpMethod': 'GET', 'body': None, 'resource': '/hello', 'requestContext': {'resourceId': '123456', 'apiId': '1234567890', 'resourcePath': '/hello', 'httpMethod': 'GET', 'requestId': 'c6af9ac6-7b61-11e6-9a41-93e8deadbeef', 'accountId': '123456789012', 'stage': 'Prod', 'identity': {'apiKey': None, 'userArn': None, 'cognitoAuthenticationType': None, 'caller': None, 'userAgent': 'Custom User Agent String', 'user': None, 'cognitoIdentityPoolId': None, 'cognitoAuthenticationProvider': None, 'sourceIp': '127.0.0.1', 'accountId': None}, 'extendedRequestId': None, 'path': '/hello'}, 'queryStringParameters': None, 'multiValueQueryStringParameters': None, 
    'headers': {'Host': '127.0.0.1:3000', 'User-Agent': 'curl/7.54.0', 'Accept': '*/*', 
    'Authorization': 'Bearer <token>', 'X-Forwarded-Proto': 'http', 'X-Forwarded-Port': '3000'}, 'multiValueHeaders': {'Host': ['127.0.0.1:3000'], 'User-Agent': ['curl/7.54.0'], 'Accept': ['*/*'], 
    'Authorization': ['Bearer <token>'], 'X-Forwarded-Proto': ['http'], 'X-Forwarded-Port': ['3000']}, 'pathParameters': None, 'stageVariables': None, 'path': '/hello', 'isBase64Encoded': False}
  
  
   # print(event)
    #authorization = event['token']
    #print(authorization)
    #print('authorization: {}'.format(authorization))
    ret = lambda_handler(event, None)
    print(ret)