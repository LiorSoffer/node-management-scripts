"""
Web UI to create and manage VMs for assisted-ui-lib testing.
Audience: UX designers/researchers. Resulting clusters are not for production.
"""

import os
import re
import subprocess

import validators
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash

# dependencies: pip install flask flask-httpauth validators

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {}

def init_users():
    with open("../users", "r") as usersfile:
        users_and_pass = usersfile.readlines()
        for user_and_pass in users_and_pass:
            (user, password) = user_and_pass.strip().split('=', 1)
            users[user] = password

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
init_users()

# Hosts that should not be deleted (e.g. shared masters); read from .env PROTECTED_HOSTS
_raw = os.environ.get('PROTECTED_HOSTS', '')
PROTECTED_HOSTS = frozenset(name.strip() for name in _raw.split(',') if name.strip())

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

@app.route('/logout', methods=['GET'])
def logout():
    return redirect(f'http://.:.@{request.host}')

@app.route('/', methods=['GET', 'POST'])
@auth.login_required
def create_vms():
    def get_running_vms():
        out = subprocess.check_output(['./host_scripts/get_running_vms.sh']).decode("utf-8").strip()
        return out.split() if out else []

    def get_status():
        wget = subprocess.check_output(['./host_scripts/get_running_process_count.sh', 'wget']).decode('utf-8').strip()
        virt_install = subprocess.check_output(['./host_scripts/get_running_process_count.sh', 'virt-install']).decode('utf-8').strip()
        if wget != '2':
            return 'An image is being downloaded.'
        if virt_install != '2':
            return 'The VM(s) are being created.'
        return ''

    def start_vms_on_background(url, num_of_nodes, prefix):
        subprocess.Popen(['./host_scripts/create_vms_from_iso_path.sh', url, num_of_nodes, prefix])

    running = get_running_vms()
    status = get_status()
    auto_refresh = bool(status)
    message = None
    message_type = 'info'  # default when message is set; overridden for validation/success
    hide_form = False
    num_of_nodes = '3'
    node_prefix = ''

    if request.method == 'POST':
        if status:
            return render_template(
                'create.html',
                message='Host creation in progress. Please wait before submitting again. ' + status,
                message_type='info',
                hide_form=True,
                running_count=len(running),
                auto_refresh=True,
                num_of_nodes=request.form.get('numofnodes', '3').strip() or '3',
                node_prefix=request.form.get('node-prefix', '').strip(),
            )
        num_of_nodes = request.form.get('numofnodes', '').strip() or '3'
        if not num_of_nodes.isnumeric():
            message = 'The number of nodes must be a number.'
            message_type = 'warning'
        else:
            url = request.form.get('url', '').strip()
            if url.startswith('wget'):
                url = re.sub(r'wget -O .*\.iso \'', '', url).rstrip("'")
            if not url:
                message = 'The URL cannot be empty.'
                message_type = 'warning'
            elif not validators.url(url):
                message = 'The provided URL is not valid.'
                message_type = 'warning'
            else:
                prefix = request.form.get('node-prefix', '').strip().replace(' ', '') or 'unset'
                start_vms_on_background(url, num_of_nodes, prefix)
                status = get_status()
                auto_refresh = True
                message = 'Host creation has been submitted. Hosts should appear in the wizard in a few minutes. ' + (status or '')
                message_type = 'success'
                hide_form = True

    if message is None and status:
        message = 'Host creation in progress. Please wait. ' + status
        message_type = 'info'
        hide_form = True

    return render_template(
        'create.html',
        message=message,
        message_type=message_type,
        hide_form=hide_form,
        running_count=len(running),
        auto_refresh=auto_refresh,
        num_of_nodes=num_of_nodes or '3',
        node_prefix=node_prefix,
    )

@app.route('/manage', methods=['GET', 'POST'])
@auth.login_required
def manage_vms():
    def get_running_vms():
        out = subprocess.check_output(['./host_scripts/get_running_vms.sh']).decode('utf-8').strip()
        return out.split() if out else []

    if request.method == 'POST':
        to_delete = request.form.getlist('vmname')
        if to_delete:
            subprocess.run(['./host_scripts/delete_vms.sh'] + to_delete)

    return render_template('manage.html', vm_list=get_running_vms(), protected_hosts=PROTECTED_HOSTS)
