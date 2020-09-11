from __future__ import print_function
import message_helper
from time import sleep
import logging

def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.DEBUG)
    for record in event['Records']:
        logging.debug("record: " + str(record))
        #payload=record["body"]
        attributes=record["messageAttributes"]
        tenant_id = attributes["tenant_id"]["stringValue"]
        message_id = record["messageId"]
        source_arn = record["eventSourceARN"]
        queue_name = source_arn.split(":")[-1]
        #print(str(payload))
           #log entry for published message for metrics
          
        message_helper.log({
            "operation": "receive_message",
            "messageId": message_id,
            "tenantId": tenant_id,
            "messageCount" : "1",
            "queue" : queue_name,
        }, metrics=["messageCount"], dimensions=["operation", "tenantId"], context=None)  
        #sleep to slowdown consumer so we can see messages going to both queues.  
        sleep(1.0)

 
