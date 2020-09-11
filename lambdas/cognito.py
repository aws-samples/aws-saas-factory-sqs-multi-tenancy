
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

# 
# instead of re-downloading the public keys every time
# we could download them only on cold start
# https://aws.amazon.com/blogs/compute/container-reuse-in-lambda/
"""
  keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(region, userpool_id) 
  with urllib.request.urlopen(keys_url) as f:
  response = f.read()
  keys = json.loads(response.decode('utf-8'))['keys'] 
  print (keys_url)
"""

import boto3
from jose import jwk, jwt
from jose.utils import base64url_decode
from boto3.session import Session
import logging


def get_session(token, claims, account_id):

    #get login key from the iss(uer) and replace https://
    issuer = str(claims['iss'])
    issuer=issuer.replace('https://','')

    #get the pool id from custom:identity_pool in claims

    identityPoolId=str(claims['custom:identity_pool'])
    AWS_REGION=identityPoolId.split(':')[0]

    client = boto3.client('cognito-identity', AWS_REGION)
    cognito_identity_id = client.get_id(AccountId=account_id,
    IdentityPoolId=identityPoolId,
    Logins={
        issuer : token
    })

    logging.debug('Cognito Identity Id:{}\n'.format(cognito_identity_id))

    resp = client.get_credentials_for_identity(
                IdentityId=cognito_identity_id['IdentityId'], 
                Logins={issuer : token
            })

    # The resp contains the actual temporary AWS secret/access codes and a session token, to be
    # used with the rest of the AWS APIs
    secretKey = resp['Credentials']['SecretKey']
    accessKey = resp['Credentials']['AccessKeyId']
    sessionToken = resp['Credentials']['SessionToken']

    # Now you can use Boto3 like you would if you were using your own secret keys
    # what you will see in any Boto3 example on the web
    session = Session(aws_access_key_id=accessKey,
                        aws_secret_access_key=secretKey,
                        aws_session_token=sessionToken,
                        region_name=AWS_REGION)
    return session

# the following is useful to make this script executable in both
# AWS Lambda and any other local environments
if __name__ == '__main__':
    account_id='<account>'
    token = '<sometoken>'
    claims = jwt.get_unverified_claims(token)
    print('Claims {}'.format(claims))

    session = get_session(token, claims, account_id)
    sqs_resource = session.resource('sqs')

    # get queue for the Tenant from the custom:sqs attribute
    queue=sqs_resource.Queue('https://sqs.us-west-2.amazonaws.com/<account>/sampleQueue')

    #send message
    response = queue.send_message( MessageBody= 'Test Message #1',
                    #MessageDeduplicationId= str(milli_sec) + str(i),
                    #MessageGroupId=''
                    MessageAttributes=
                        {
                        'tenant_id': {
                            'StringValue': 'tenant123',
                            'DataType': 'String'
                            },
                        'message_version': {
                            'StringValue': 'Version 1.0',
                            'DataType': 'String'
                            }
                        })




