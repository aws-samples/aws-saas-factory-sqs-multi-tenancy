import cognito
import json
import boto3
from botocore.exceptions import ClientError
import time
import os
import logging
import time

#for logging
AWS_LAMBDA_FUNCTION_NAME = os.environ["AWS_LAMBDA_FUNCTION_NAME"]
AWS_LAMBDA_FUNCTION_VERSION = os.environ["AWS_LAMBDA_FUNCTION_VERSION"]
AWS_REGION = os.environ["AWS_REGION"]
ENVIRONMENT = os.environ["ENVIRONMENT"]
NAMESPACE = os.environ["NAMESPACE"]


"""
SSM is used to store which queue is used for a tenant for a specific service.  
In the case a Pool queue is used, its prefix is pool.  This entry is looked up
in SSM to get list of the pooled queues. Then the queue with the fewest number of messages is chosen
"""

def send_message(token, claims, account_id, service_name, message_body):
    sqs_client = boto3.client("sqs")

    tenant_id = claims["custom:tenant_id"]

    queues = get_queue_list(tenant_id, service_name)
    queue_list = queues.split(" ")
    queue_url = queue_list[0]
    if len(queue_list) > 1:
        None
        #find which queue has fewest messages to prevent noisy neighbor.  This could be made more elaborate
        i = 0
        start = time.time()
        while i < len(queue_list):
            response = sqs_client.get_queue_attributes(QueueUrl = queue_list[i], AttributeNames = ["All"])
            #print("response: " + json.dumps(response))
            numOfMessages = int(response["Attributes"]["ApproximateNumberOfMessages"])
            logging.info("Queue: {}, Num of Messages: {}".format(queue_list[i], numOfMessages))
            if i==0:
                maxNumMessages = numOfMessages
            else:
                if numOfMessages < maxNumMessages:
                    #print("IF 2")
                    maxNumMessages = numOfMessages
                    queue_url = queue_list[i]
                    #print("IF 2: queue_url: ", queue_url)
            i = i + 1
        end = time.time()
        logging.debug("Time spent to check queue is {}".format(end - start))
    

   # Get the session from the Cognito Identity to use for Sending Message
    start = time.time()
    session=cognito.get_session(token, claims, account_id)
    end = time.time()
    logging.debug("Session established for the identity in {}".format(end - start))

    # Get sqs resource using the new session  
    # This will fail if the role for the tenant does not have access to the queue
    logging.info("Send message to queue_url: " + queue_url)
    sqs_resource = session.resource('sqs')    
    sqs_queue = sqs_resource.Queue(queue_url)

    #send message
    response = sqs_queue.send_message( 
                    MessageBody = message_body,
                    #MessageDeduplicationId= str(milli_sec) + str(i),
                    #MessageGroupId=''
                    MessageAttributes=
                        {
                        'tenant_id': {
                            'StringValue': tenant_id,
                            'DataType': 'String'
                            },
                        'message_version': {
                            'StringValue': 'Version 1.0',
                            'DataType': 'String'
                            }
                        })

    #log entry for published message for metrics
    queue_name = queue_url.split("/")[-1]
    log({
        "operation": "send_message",
        "messageId": response["MessageId"],
        "tenantId": tenant_id,
        "messageCount" : "1",
        "queue" : queue_name,
    }, metrics=["messageCount"], dimensions=["operation", "tenantId"], context=None)    

    logging.info("Message sent to queue: " + queue_url)
    return response

def get_queue_list(tenant_id, service_name):
    ssm_client = boto3.client("ssm")
    #Get the queue name from SSM for this service using path of service_name/tenant_id
    path = "/{}/queue/{}".format(service_name,tenant_id)
    #print("Path: ", path)
    try:
        queue_ssm = ssm_client.get_parameter(Name = path)
    except ClientError as err:
        logging.error(err)
        raise ValueError("No SSM Parameter found for path: {}".format(path))

    #print("queue_ssm:", queue_ssm)
    ssm_value = queue_ssm["Parameter"]["Value"]
    #If queue name has pool then lookup the list of pool queue names
    if ssm_value.endswith("pool"):
        #get the list of queues for pool
        try:
            queue_ssm = ssm_client.get_parameter(Name = ssm_value)
        except ClientError as err:
            raise ValueError("No SSM Parameter found for path: {}".format(queue_ssm))
        #print("queue_ssm:", queue_ssm)
        ssm_value = queue_ssm["Parameter"]["Value"]

    #print("ssm value: ", ssm_value)
    return ssm_value

def log(item, metrics=None, dimensions=None, context=None):
    if not isinstance(item, dict):
        print(item)
        return

    if "loglevel" not in item:
        item["loglevel"] = "INFO"

    if metrics:
        item["_aws"] = {
            "Timestamp": int(time.time()*1000),
            "CloudWatchMetrics": [{
                "Namespace": NAMESPACE,
                "Dimensions": [(dimensions or [])+["environment"]],
                "Metrics": [{"Name": m, "Unit": "None"} for m in metrics]
            }]
        }

    # subsegment = xray_recorder.current_subsegment()
    # if subsegment:
    #     for dimension in dimensions or []:
    #         subsegment.put_annotation(dimension, item[dimension])

    item["environment"] = ENVIRONMENT
    item["functionName"] = AWS_LAMBDA_FUNCTION_NAME
    item["functionVersion"] = AWS_LAMBDA_FUNCTION_VERSION
    item["region"] = AWS_REGION

    # xray_trace_id = os.environ.get("_X_AMZN_TRACE_ID", "")

    # if xray_trace_id:
    #     item["xrayTraceId"] = xray_trace_id

    if context:
        item["requestId"] = context.aws_request_id

    print(json.dumps(item))


#to test functions locally
if __name__ == '__main__':
    # queues = get_queue_list("tenant2", "order")
    # print("Queues: ", queues)

    #you can use https://jwt.io to get the ciams from a token to build the Claims JSON
    tenant1_token = "eyJraWQiOiJlU1F5bmNaZERndFM4UnFzXC83K0ZcL3Q3Zlg1WWlRWHBOR2hLWkhQOU5cL1wvZz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZjY1OTczYS0xYjdmLTQ4Y2QtYTg1ZS1kYmEwMzYzZGE0MjUiLCJhdWQiOiIybG5iODZrb2xmcjBpZXM4M3JtcTNjczA2dCIsImN1c3RvbTppZGVudGl0eV9wb29sIjoidXMtd2VzdC0yOmI3OTVkNTllLTIwMmYtNGU1Yi1hZGY3LTQzZGNiMWQzZTQ5MCIsImV2ZW50X2lkIjoiNThmYzZmZWUtNDZmMy00ZDdkLTkwYzctYTFjYTY5YjdhZWFhIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE1OTExNTk2NDksImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy13ZXN0LTIuYW1hem9uYXdzLmNvbVwvdXMtd2VzdC0yX0dCaEtvU1BJaCIsImNvZ25pdG86dXNlcm5hbWUiOiJ1c2VyQHRlbmFudDEuY29tIiwiY3VzdG9tOnRlbmFudF9pZCI6InRlbmFudDEiLCJleHAiOjE1OTExNjMyNDksImlhdCI6MTU5MTE1OTY0OX0.kqjXllXBWePkfCNTJ-qV28JuDrn_VaCtPQmwxpp4fpjefrA3PzMU_TIBlWrnVqegkMSl2CCkMI1e5UcnNGr0KpCrsktykFMxxt1-pJAlq7KTCSaIGGDhXEdXdUOaan-wOBMzESXbpSqTRo_y64GCUMaKapfT677OH1y2_COok0KWkG0oLQapFY4__QH8md8hzqG28fEsljLFkKWlXhA6oiX7OK_VlWFWbjZkLL-IW7LFYPxBa76O5l0stsvl1Yrkw51wqWGkOECjocPRr3BMr6IQkkmG2ZgbcWU9PSvtO1TJ6kdAZXrlqP7_yvardxg79Zg6RRfMsL6xXWX-Ly3NfQ"
    claims1 = json.loads('{"custom:tenant_id":"tenant1", "custom:identity_pool":"us-west-2:b795d59e-202f-4e5b-adf7-43dcb1d3e490", "iss":"https://cognito-idp.us-west-2.amazonaws.com/us-west-2_GBhKoSPIh"}')
    send_message(tenant1_token,
        claims1, "094057127497", "order", "Test message")


    #you can use https://jwt.io to get the ciams from a token to build the Claims JSON
    tenant2_token = "eyJraWQiOiJxMGJFbU91c3hUM09TV0dQMFNCYWtoaDNhcE9XVWRnOVV4R3dhTXE4eEUwPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJjOGQ2Y2E4Yi1jMTkxLTQzZjQtOWIyNC0yYWVmMzBiNDNmMjgiLCJhdWQiOiI2OXB1a3U4NW1kcjlwaTNmc2xhZ3A1YjVldiIsImN1c3RvbTppZGVudGl0eV9wb29sIjoidXMtd2VzdC0yOmRlMTZhNzMzLTRmODYtNGU4OC04NGY3LWE0NTdjNDdiMDA5OCIsImV2ZW50X2lkIjoiZTYxYzRiNWQtODc4ZC00NTZiLWJmZWEtZGY2ZmNhYmYwN2Q2IiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE1OTExNjA4NDgsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy13ZXN0LTIuYW1hem9uYXdzLmNvbVwvdXMtd2VzdC0yX29STEwwN29xZCIsImNvZ25pdG86dXNlcm5hbWUiOiJ1c2VyQHRlbmFudDIuY29tIiwiY3VzdG9tOnRlbmFudF9pZCI6InRlbmFudDIiLCJleHAiOjE1OTExNjQ0NDgsImlhdCI6MTU5MTE2MDg0OH0.lbNTG4q6PNjIfsonDp4H3Puzaeltznt2ZuIqj4jyXWs1fyeVJkkGVOn9YJbtZSg5pCGBSGegZQ4pwcfAkpU_nTxSS8J2jxUMq0lL2Tr-lELfI-BsNZ-hri1pcNF_54ZUORcRO3eg0Qp1wkYMmOF_vJmwmeBNToICPULM0R-7jdibz0PmeXrvN2QhkRnR9_vLTCS2r9gG5i_E_OwvS4zHAxM1_uBM73tURmhmWdTG7-ml2mmqYCfioNHKx1G8nOiZwMNlojyhlnw-e1TzJYmZTR3HaNHxzBG8QTj_lG_eRAMDxGiayNaTMyeH9CX3vFjuTX5nyig2cmB1i3J7PrXTEw"
    claims2 = json.loads('{"custom:tenant_id":"tenant2", "custom:identity_pool":"us-west-2:de16a733-4f86-4e88-84f7-a457c47b0098", "iss":"https://cognito-idp.us-west-2.amazonaws.com/us-west-2_oRLL07oqd"}')
    send_message(tenant2_token,
        claims2, "094057127497", "order", "Test message tenant 2")
