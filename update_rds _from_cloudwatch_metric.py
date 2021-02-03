import psycopg2
import sys
import json
import boto3
import base64
import os
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

ENDPOINT=os.environ["ENDPOINT"]
PORT=os.environ["PORT"]
REGION=os.environ["REGION"]
DBNAME=os.environ["DBNAME"]
SECRET_NAME=os.environ["SECRET_NAME"]

session = boto3.session.Session()
client = session.client(service_name='secretsmanager',region_name=REGION)
cloudwatch = boto3.client('cloudwatch', region_name=REGION)

# def get_cloudwatch_metrics():
    
#     response = cloudwatch.get_metric_data(
#     MetricDataQueries=[
#         {
#             'Id': 'lambda',
#             'MetricStat': {
#                 'Metric': {
#                     'Namespace': 'Bitbucket',
#                     'MetricName': 'Bitbucket_cluster_nodes',
#                     'Dimensions': [
#                                 {
#                                     'Name': 'Bibucket',
#                                     'Value': 'nodes_count'
#                                 },
#                                 {
#                                     'Name': 'VERSION',
#                                     'Value': '1.0'
#                                 }
#                     ]
#                 },
#                 'Period': 60,
#                 'Stat': 'Average',
#                 'Unit': 'None'
#             },
#             'ReturnData': True,
#         },
#     ],
#     StartTime=datetime.now() - timedelta(hours=1),
#     EndTime=datetime.now(),
#     )
#     return response

def get_secret():

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=SECRET_NAME
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            raise e
    else:
        if 'SecretString' in get_secret_value_response:
            return get_secret_value_response['SecretString']
        else:
            return base64.b64decode(get_secret_value_response['SecretBinary'])

def postgres_login():
    
    secret = get_secret()
    # nodes_count = get_cloudwatch_metrics()
    # metric_nodes_count = nodes_count['MetricDataResults']
    # print("metric_values are    :")
    # print(metric_nodes_count)
    # for metric in nodes_count['MetricDataResults']:
    #     if 3 in (metric['Values']):
    #         print ("Bitbucket nodes count is less than 2")
            parsed = json.loads(secret)
            try:
                connection = psycopg2.connect(host=ENDPOINT, port=PORT, database=DBNAME, user=parsed['username'], password=parsed['password'])
                cursor = connection.cursor()
                sql = "Update databasechangeloglock set locked = ('true'), lockgranted = NULL, lockedby = NULL where id = ('1')"
                cursor.execute(sql)
                connection.commit()
                print ("Values were changed")
                cursor.execute("SELECT * FROM databasechangeloglock")
                query_results = cursor.fetchall()
                print(query_results)
            
            except Exception as e:
                print("Database connection failed due to {}".format(e))   
            finally:
                if (connection):
                    # conection.commit()
                    cursor.close()
                    connection.close()
                    print("PostgreSQL connection is closed")

def lambda_handler(event, context):
    
    # get_cloudwatch_metrics(),
    get_secret(),
    postgres_login()

    
    if __name__ == '__main__':
        lambda_handler(None, None)
