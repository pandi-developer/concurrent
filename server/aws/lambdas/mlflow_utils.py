import json
import sys
import os
import tempfile
import subprocess
import time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def setup_for_subprocess(auth_info):
    modified_env = dict(os.environ)
    if 'mlflow_concurrent_uri' in auth_info and auth_info['mlflow_concurrent_uri']:
        modified_env['MLFLOW_CONCURRENT_URI'] = auth_info['mlflow_concurrent_uri']
    if 'mlflow_tracking_uri' in auth_info and auth_info['mlflow_tracking_uri']:
        modified_env['MLFLOW_TRACKING_URI'] = auth_info['mlflow_tracking_uri']
    if 'mlflow_tracking_token' in auth_info and auth_info['mlflow_tracking_token']:
        modified_env['MLFLOW_TRACKING_TOKEN'] = auth_info['mlflow_tracking_token']
    modified_env['PYTHONPATH'] = os.environ['PYTHONPATH'] + ':/opt/python'
    tmphome = tempfile.mkdtemp()
    modified_env['HOME'] = tmphome
    if 'custom_token' in auth_info and auth_info['custom_token']:
        os.makedirs(os.path.join(tmphome, ".concurrent"), exist_ok=True)
        with open(os.path.join(tmphome, ".concurrent", "token"), 'w') as fl:
            fl.write('Token=' + auth_info['custom_token'] + '\n')
            fl.write('ClientId=' + auth_info['cognito_client_id'] + '\n')
    return modified_env

def call_create_run(cognito_username, experiment_id, auth_info, run_name=None,
                    parent_run_id=None, source_name=None, tags=None):
    cmd = [sys.executable, os.getcwd() + '/create_run.py', '--experiment_id', str(experiment_id)]
    if tags:
        cmd.extend(['--tags', json.dumps(tags)])

    if run_name:
        cmd.append('--run_name')
        cmd.append(run_name)
    if parent_run_id:
        cmd.append('--parent_run_id')
        cmd.append(parent_run_id)
    if source_name:
        cmd.append('--source_name')
        cmd.append(source_name)

    modified_env = setup_for_subprocess(auth_info)

    run_id = None
    artifact_uri = None
    status = None
    lifecycle_stage = None
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=modified_env)
    full_out = ''
    for line in proc.stdout:
        fline = line.rstrip().decode("utf-8")
        full_out = full_out + fline + '\n'
    proc.wait()
    if proc.returncode != 0:
        print('Error calling create_run.py=' + full_out)
        return None, None, None, None
    else:
        run = json.loads(full_out)
        run_id = run['run_id']
        artifact_uri = run['artifact_uri']
        status = run['status']
        lifecycle_stage = run['lifecycle_stage']
        logger.debug('call_create_run: returning run_id=' +str(run_id)
                +', artifact_uri=' +str(artifact_uri) +', status=' +str(status)
                +', lifecycle_stage=' +str(lifecycle_stage))
        return run_id, artifact_uri, status, lifecycle_stage

def update_run(auth_info, run_id, state):
    cmd = [sys.executable, os.getcwd() + '/update_run.py', '--run_id', str(run_id),
            '--state', str(state)]
    modified_env = setup_for_subprocess(auth_info)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=modified_env)
    full_out = ''
    for line in proc.stdout:
        fline = line.rstrip().decode("utf-8")
        full_out = full_out + fline + '\n'
    proc.wait()
    if proc.returncode != 0:
        print('Error calling update_run.py=' + full_out)

def fetch_run_id_info(auth_info, run_id):
    cmd = [sys.executable, os.getcwd() + '/get_run_info.py', '--run_id', str(run_id)]
    modified_env = setup_for_subprocess(auth_info)

    run_id = None
    artifact_uri = None
    status = None
    lifecycle_stage = None
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=modified_env)
    full_out = ''
    for line in proc.stdout:
        fline = line.rstrip().decode("utf-8")
        full_out = full_out + fline + '\n'
    proc.wait()
    if proc.returncode != 0:
        print('Error calling get_run_info.py=' + full_out)
        return None
    else:
        run = json.loads(full_out)
        logger.debug('fetch_run_id_info: returning run_id=' +str(run['run_id'])
                +', artifact_uri=' +str(run['artifact_uri']) +', status=' +str(run['status'])
                +', lifecycle_stage=' +str(run['lifecycle_stage']))
        return run

def create_experiment(auth_info, experiment_name):
    cmd = [sys.executable, os.getcwd() + '/create_experiment.py',
            '--experiment_name', str(experiment_name)]
    modified_env = setup_for_subprocess(auth_info)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=modified_env)
    full_out = ''
    for line in proc.stdout:
        fline = line.rstrip().decode("utf-8")
        full_out = full_out + fline + '\n'
    proc.wait()
    if proc.returncode != 0:
        print('Error calling create_experiment.py=' + full_out)
        return None
    else:
        run = json.loads(full_out)
        experiment_id = run['experiment_id']
        print('call_create_experiment: returning experiment_id=' +str(experiment_id))
        return experiment_id

def log_mlflow_artifact(auth_info, run_id, artifact_object, path, file_name):
    modified_env = setup_for_subprocess(auth_info)
    local_file = os.path.join(modified_env['HOME'], file_name)
    with open(local_file, 'wb') as fl:
        fl.write(json.dumps(artifact_object).encode('utf-8'))
    cmd = [sys.executable, os.getcwd() + '/log_artifact.py',
            '--run_id', str(run_id), '--path', path,
            '--file_name', local_file]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=modified_env)
    full_out = ''
    for line in proc.stdout:
        fline = line.rstrip().decode("utf-8")
        full_out = full_out + fline + '\n'
    proc.wait()
    if proc.returncode != 0:
        print('Error calling log_artifact.py=' + full_out)


def download_mlflow_artifact(auth_info, run_id, artifact_path, dst_dir):
    modified_env = setup_for_subprocess(auth_info)
    cmd = [sys.executable, os.getcwd() + '/download_artifacts.py',
           '--run_id', str(run_id), '--path', artifact_path,
           '--dst_path', dst_dir]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=modified_env)
    full_out = ''
    for line in proc.stdout:
        fline = line.rstrip().decode("utf-8")
        full_out = full_out + fline + '\n'
    proc.wait()
    if proc.returncode != 0:
        print('Error calling download_artifacts.py=' + full_out)


def fetch_mlflow_artifact_file(auth_info, run_id, artifact_path):
    local_dir = tempfile.mkdtemp()
    num_attempts = 3
    while num_attempts > 0:
        num_attempts -= 1
        download_mlflow_artifact(auth_info, run_id, artifact_path, local_dir)
        local_path = os.path.join(local_dir, artifact_path)
        if os.path.exists(local_path):
            with open(local_path, 'rb') as inf:
                content = inf.read()
            return content
        else:
            print('Download failed, retrying {} more times'.format(num_attempts))
            if num_attempts > 0:
                time.sleep(10)


