
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
import os
import time
import urllib.request

from jose import jwk, jwt
from jose.utils import base64url_decode
import logging
import message_helper


#This is for SSL certiticate error in Python when running locally
#ssl._create_default_https_context = ssl._create_unverified_context
# Had to run the Install Certificats.command from the Python 3.7 folder

# instead of re-downloading the public keys every time
# we download them only on cold start
# https://aws.amazon.com/blogs/compute/container-reuse-in-lambda/

""" region = 'us-west-2'
userpool_id = 'us-west-2_ujo3liqS5'
app_client_id = 'f7u94ger0vvskunbt50p3j1tb'
keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(region, userpool_id)

print (keys_url)


with urllib.request.urlopen(keys_url) as f:
response = f.read()
keys = json.loads(response.decode('utf-8'))['keys'] 
"""
keys_map = dict()

def process_token(header):
    logging.debug(header)

    if str(header).__contains__('Authorization'):
        authorization = header['Authorization']
    elif str(header).__contains__('authorization'):
        authorization = header['authorization']
    else:
        raise ValueError("Missing Authorization in Header")
        # return {
        #     "statusCode": 500,
        #     "body": json.dumps({
        #         "message": "Missing Authorization in Header",
        #     }),
        #  }    

    #print('Authorization: {}'.format(authorization))
    if authorization:
      bearer = authorization.split()
      token = bearer[1]
      #print ('Token {}'.format(token))
    else: 
        raise ValueError("Missing Authorization in Header")  


    #get the pool id from the issuer in unverified claims to get signature key for token
    claims = jwt.get_unverified_claims(token)
    logging.debug('Claims {}'.format(claims))
    issuer = str(claims['iss'])
    lastIndex = issuer.rfind('/') + 1
    userPoolId = issuer[lastIndex:]
    logging.debug('UserPoolId: {}'.format(userPoolId))

    # The issuer named in the token decides nothing until it has been checked against the
    # pools this deployment actually owns.
    #
    # Previously the JWKS URL was built straight from claims['iss'], which is an unverified
    # value under the caller's control. Cognito's JWKS endpoints are public and
    # account-agnostic, so a caller could create a user pool in their own AWS account, mint
    # a token with any custom:tenant_id they liked, and this function would fetch that
    # pool's public keys and verify the signature successfully. Pinning the region would not
    # have helped: the attacker's pool can be in the same region. Only an allowlist of this
    # deployment's own pool ids distinguishes our issuer from anyone else's.
    allowed_pool_ids = [
        p.strip() for p in os.environ.get('ALLOWED_USER_POOL_IDS', '').split(',') if p.strip()
    ]
    if not allowed_pool_ids:
        # Fail closed. An unset variable must not silently restore issuer trust.
        raise ValueError(
            'ALLOWED_USER_POOL_IDS is not configured; refusing to verify a token against '
            'an issuer named by the token itself'
        )
    if userPoolId not in allowed_pool_ids:
        raise ValueError(
            'Token issuer names user pool {} which is not one of this deployment\'s '
            'pools'.format(userPoolId)
        )

    # Rebuild the JWKS URL from the validated pool id rather than reusing the token's own
    # issuer string, so a token cannot influence the URL even in part.
    region = userPoolId.split('_')[0]
    keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(
        region, userPoolId
    )
    if keys_url in keys_map:
        keys = keys_map[keys_url]
        logging.info("Key found for keys_url: " + keys_url)
    else:
        #we store the key in map using the keys_url to reduce calls
        with urllib.request.urlopen(keys_url) as f:
            response = f.read()
        keys = json.loads(response.decode('utf-8'))['keys']
        keys_map[keys_url] = keys
        logging.info("Add key for keys_url: " + keys_url)


    # get the kid from the headers prior to verification
    headers = jwt.get_unverified_headers(token)
    #print('headers {}'.format(headers))
    kid = headers['kid']
    # search for the kid in the downloaded public keys
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    if key_index == -1:
        raise ValueError('Public key not found in jwks.json')
        # return {
        #     "statusCode": 500,
        #     "body": json.dumps({
        #         "message": "Public key not found in jwks.json",
        #     }),
        #  }
    # construct the public key
    public_key = jwk.construct(keys[key_index])
    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = str(token).rsplit('.', 1)
    # decode the signature
    decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
    # verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        raise ValueError('Signature verification failed')
        # return {
        #     "statusCode": 500,
        #     "body": json.dumps({
        #         "message": "Signature verification failed",
        #     }),
        #  }

    logging.debug('Signature of token successfully verified')
    # since we passed the verification, we can now safely use the claims

    # additionally we can verify the token expiration
    if time.time() > claims['exp']:
        message_helper.log({
            "operation": "send_message",
            "messageId": "none",
#            "tenantId": tenant_id,
            "messageCount" : "1",
            "loglevel" : "ERR",
#            "queue" : queue_name,
        }, metrics=["messageCount"], dimensions=["operation", "tenantId"], context=None)    
        raise ValueError('Token is expired')
        # return {
        #     "statusCode": 500,
        #     "body": json.dumps({
        #         "message": "Token is expired",
        #     }),
        #  }


    return token, claims
 

# the following is useful to make this script executable in both
# AWS Lambda and any other local environments
if __name__ == '__main__':
    # for testing locally you can enter the JWT ID Token here
    event = {'httpMethod': 'GET', 'body': None, 'resource': '/hello', 'requestContext': {'resourceId': '123456', 'apiId': '1234567890', 'resourcePath': '/hello', 'httpMethod': 'GET', 'requestId': 'c6af9ac6-7b61-11e6-9a41-93e8deadbeef', 'accountId': '123456789012', 'stage': 'Prod', 'identity': {'apiKey': None, 'userArn': None, 'cognitoAuthenticationType': None, 'caller': None, 'userAgent': 'Custom User Agent String', 'user': None, 'cognitoIdentityPoolId': None, 'cognitoAuthenticationProvider': None, 'sourceIp': '127.0.0.1', 'accountId': None}, 'extendedRequestId': None, 'path': '/hello'}, 'queryStringParameters': None, 'multiValueQueryStringParameters': None, 
'headers': {'Host': '127.0.0.1:3000', 'User-Agent': 'curl/7.54.0', 'Accept': '*/*', 
'Authorization': 'Bearer <token>', 'X-Forwarded-Proto': 'http', 'X-Forwarded-Port': '3000'}, 'multiValueHeaders': {'Host': ['127.0.0.1:3000'], 'User-Agent': ['curl/7.54.0'], 'Accept': ['*/*'], 
'Authorization': ['Bearer <token>'], 'X-Forwarded-Proto': ['http'], 'X-Forwarded-Port': ['3000']}, 'pathParameters': None, 'stageVariables': None, 'path': '/hello', 'isBase64Encoded': False}
  
    ret = process_token(event['headers'])
    print(ret)