import io
import json
import boto3
import paramiko
import os
import time
from multiprocessing import Process, Pipe



# Lambda environment variables
REGION = os.environ['REGION']
SECRET_NAME = os.environ['SECRET_NAME']
# Connect EC2 client
ec2_client = boto3.client('ec2', region_name=REGION)
# Get secrets from Secrets Manager
session = boto3.session.Session()
client = session.client(service_name='secretsmanager', region_name=REGION)
get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
secret = get_secret_value_response['SecretString']
secret_dict = json.loads(secret)
private_key = secret_dict['privatekey']
private_key_str = io.StringIO()
private_key_str.write(private_key)
private_key_str.seek(0)


class AgentsParallel(object):
    
    def check_agent(self, ssh):
        stdin, stdout, stderr = ssh.exec_command('ps -acx|grep "node_exporter"|wc -l');
        data = stdout.read().splitlines();
        stdin.flush();
        stdin.close();
        return data[0].decode('UTF-8');
        
    def install_agent(self, ssh):
        # Setup sftp connection and transmit this script
        sftp = ssh.open_sftp()
        sftp.put('exporters.sh', '/tmp/exporters.sh')
        sftp.close()

        stdin, stdout, stderr = ssh.exec_command('sudo sh /tmp/exporters.sh')
        data = stdout.read();
        stdin.flush();
        stdin.close();
        return data;
        
    def run_remote_commmand(self, host, conn, func):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key = paramiko.RSAKey.from_private_key(private_key_str)

        _e: Exception
        try:
            ssh.connect(hostname=host['ip'], username='ubuntu', pkey=key, timeout=1)
            data = func(ssh);
            ssh.close()
            conn.send([host, data])
            conn.close()
        except KeyboardInterrupt:
            conn.send([f'Operation cancelled by user'])
            conn.close();
        except Exception as _e:
            conn.send([f'{host} Could not connect {_e}'])
            conn.close();

    def get_instance_ip(self):
        running_instances = ec2_client.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'pending']}, ]).get("Reservations")
        ec2_instances_list = []
        for reservation in running_instances:
            for instance in reservation['Instances']:
                private_ip = instance['PrivateIpAddress'];
                instance_id = instance['InstanceId'];
                private_ip_running_instances = f'{private_ip}'
                ec2_instances_list.append(
                    { 
                        'ip': private_ip_running_instances,
                        'instanceId': instance_id
                    })
        return ec2_instances_list

    def check_agents(self):
        """
        Lists all EC2 instances in the default region
        and sums result of instance_volumes
        """
       
        # get all EC2 instances
        instances = self.get_instance_ip()
        instances_len = len(instances)
        print (f'Check {instances_len} instances')
        # for i in range(0,instances_len,5):
            # print(min([i+5, instances_len]))
            # self.run_in_parralel(list(map(lambda i: instances[i], range(i, min([i+5, instances_len])))));
        instances_to_install = self.run_in_parralel(instances, self.check_agent);
        print (f'Install {len(instances_to_install)} instances')
        self.run_in_parralel(instances_to_install, self.install_agent);
        
    def run_in_parralel(self, instances, func):
        # create a list to keep all processes
        processes = []

        # create a list to keep connections
        parent_connections = []
        # create a process per instance
        for instance in instances:            
            # create a pipe for communication
            parent_conn, child_conn = Pipe()
            parent_connections.append(parent_conn)

            # create the process, pass instance and connection
            process = Process(target=self.run_remote_commmand, args=(instance, child_conn, func))
            processes.append(process)

        # start all processes
        for process in processes:
            process.start()

        # make sure that all processes have finished
        for process in processes:
            process.join()
        result = []
        instances_total = 0
        for parent_connection in parent_connections:
            resp = parent_connection.recv()
            if len(resp) == 2 and resp[1] == '0':
                result.append(resp[0]);
            else:
                print(resp);
        return result;


def lambda_handler(event, context):
    volumes = AgentsParallel()
    _start = time.time()
    volumes.check_agents()
    print(f'Parallel execution time: {(time.time() - _start)} seconds')
    
    file1 = open('exporters.sh', 'r')
    

if __name__ == '__main__':
    lambda_handler(None, None)
